"""
incident-collector.py
GKE 클러스터의 장애 진단 정보를 자동 수집하여 Slack으로 전송한다.

실행 방식: GitHub Actions workflow_dispatch (수동 트리거)
필요 환경변수:
  - SLACK_WEBHOOK_URL : Slack Incoming Webhook URL
  - NAMESPACE         : 조회할 네임스페이스 (기본: all — 전체 네임스페이스)
  - LOG_TAIL_LINES    : 비정상 Pod 로그 최대 줄 수 (기본: 30)

사전 조건:
  - kubeconfig가 설정되어 있어야 함
    (GitHub Actions에서는 gcloud container clusters get-credentials로 설정)
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

from kubernetes import client, config
from kubernetes.client.rest import ApiException


# ── 환경변수 로드 ──────────────────────────────────────────────────────────────
SLACK_WEBHOOK   = os.environ["SLACK_WEBHOOK_URL"]
TARGET_NS       = os.environ.get("NAMESPACE", "all")   # "all" 이면 전체 네임스페이스
LOG_TAIL_LINES  = int(os.environ.get("LOG_TAIL_LINES", "30"))

# KST 기준 현재 시각
KST = timezone(timedelta(hours=9))


# ── 비정상 Pod 판별 기준 상태 ────────────────────────────────────────────────
UNHEALTHY_REASONS = {
    "CrashLoopBackOff",
    "OOMKilled",
    "Error",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "InvalidImageName",
}


def load_kube_config() -> None:
    """클러스터 내부 또는 로컬 kubeconfig로 Kubernetes 클라이언트를 초기화한다."""
    try:
        # GitHub Actions / 로컬: kubeconfig 파일 사용
        config.load_kube_config()
        print("[incident-collector] kubeconfig로 인증 완료")
    except Exception:
        # K8s 클러스터 내부에서 실행 시 (Pod 등)
        config.load_incluster_config()
        print("[incident-collector] in-cluster 인증 완료")


def get_unhealthy_pods(v1: client.CoreV1Api) -> list[dict]:
    """
    전체(또는 지정) 네임스페이스에서 비정상 상태의 Pod를 수집한다.
    반환: [{"namespace", "name", "phase", "reason", "restarts", "message"}]
    """
    if TARGET_NS == "all":
        pods = v1.list_pod_for_all_namespaces(watch=False).items
    else:
        pods = v1.list_namespaced_pod(namespace=TARGET_NS, watch=False).items

    unhealthy = []
    for pod in pods:
        ns   = pod.metadata.namespace
        name = pod.metadata.name
        phase = pod.status.phase or "Unknown"

        # 컨테이너 상태에서 비정상 reason 추출
        reason   = ""
        restarts = 0
        message  = ""

        container_statuses = pod.status.container_statuses or []
        for cs in container_statuses:
            restarts += cs.restart_count or 0
            waiting = cs.state.waiting if cs.state else None
            terminated = cs.state.terminated if cs.state else None

            if waiting and waiting.reason in UNHEALTHY_REASONS:
                reason  = waiting.reason
                message = waiting.message or ""
                break
            if terminated and terminated.reason in UNHEALTHY_REASONS:
                reason  = terminated.reason
                message = terminated.message or ""
                break

        # phase가 Failed 이거나 비정상 reason이 있으면 수집
        if phase == "Failed" or reason:
            unhealthy.append({
                "namespace": ns,
                "name":      name,
                "phase":     phase,
                "reason":    reason or phase,
                "restarts":  restarts,
                "message":   message[:200] if message else "",
            })

    print(f"[incident-collector] 비정상 Pod 수: {len(unhealthy)}")
    return unhealthy


def get_pod_logs(v1: client.CoreV1Api, namespace: str, pod_name: str) -> str:
    """
    비정상 Pod의 최근 로그를 가져온다.
    이전 컨테이너(재시작 직전) 로그도 함께 시도한다.
    """
    logs = []
    for previous in (False, True):
        try:
            log = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=LOG_TAIL_LINES,
                previous=previous,
                timestamps=False,
            )
            label = "(이전 컨테이너)" if previous else "(현재)"
            logs.append(f"--- 로그 {label} ---\n{log.strip()}")
            break  # 현재 로그 성공 시 이전 로그는 생략
        except ApiException:
            continue

    return "\n".join(logs) if logs else "(로그 없음)"


def get_warning_events(v1: client.CoreV1Api) -> list[dict]:
    """
    최근 Warning 이벤트를 수집한다 (최대 15개).
    반환: [{"namespace", "name", "reason", "message", "last_time"}]
    """
    if TARGET_NS == "all":
        events = v1.list_event_for_all_namespaces(
            watch=False,
            field_selector="type=Warning",
        ).items
    else:
        events = v1.list_namespaced_event(
            namespace=TARGET_NS,
            watch=False,
            field_selector="type=Warning",
        ).items

    # 최근 시각 기준 내림차순 정렬 후 상위 15개
    def event_time(e):
        t = e.last_timestamp or e.event_time
        return t if t else datetime.min.replace(tzinfo=timezone.utc)

    sorted_events = sorted(events, key=event_time, reverse=True)[:15]

    result = []
    for e in sorted_events:
        t = e.last_timestamp or e.event_time
        last_time = t.astimezone(KST).strftime("%H:%M") if t else "?"
        result.append({
            "namespace": e.metadata.namespace,
            "name":      e.involved_object.name,
            "reason":    e.reason or "",
            "message":   (e.message or "")[:150],
            "last_time": last_time,
        })

    print(f"[incident-collector] Warning 이벤트 수: {len(result)}")
    return result


def get_node_status(v1: client.CoreV1Api) -> list[dict]:
    """
    노드 상태 및 Condition(Ready 여부)을 수집한다.
    반환: [{"name", "ready", "cpu_capacity", "mem_capacity"}]
    """
    nodes = v1.list_node(watch=False).items
    result = []
    for node in nodes:
        # Ready condition 확인
        ready = "Unknown"
        for cond in (node.status.conditions or []):
            if cond.type == "Ready":
                ready = "Ready" if cond.status == "True" else "NotReady"
                break

        cpu = node.status.capacity.get("cpu", "?")
        mem = node.status.capacity.get("memory", "?")

        result.append({
            "name":         node.metadata.name,
            "ready":        ready,
            "cpu_capacity": cpu,
            "mem_capacity": mem,
        })

    print(f"[incident-collector] 노드 수: {len(result)}")
    return result


def build_slack_message(
    unhealthy_pods: list[dict],
    pod_logs: dict[str, str],
    warning_events: list[dict],
    node_status: list[dict],
) -> dict:
    """Slack Block Kit 형식의 장애 진단 리포트 메시지를 생성한다."""
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    blocks = []

    # ── 헤더 ──────────────────────────────────────────────────────────────────
    header_emoji = "🚨" if unhealthy_pods else "✅"
    header_text  = f"{header_emoji} GKE 장애 진단 리포트 ({now_kst})"
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header_text}
    })

    # ── 비정상 Pod ─────────────────────────────────────────────────────────────
    if unhealthy_pods:
        pod_lines = "\n".join(
            f"  • {p['namespace']}/{p['name']}"
            f"   상태: {p['reason']}"
            f"   재시작: {p['restarts']}회"
            + (f"\n    └ {p['message']}" if p["message"] else "")
            for p in unhealthy_pods
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*비정상 Pod ({len(unhealthy_pods)}개)*\n```{pod_lines}```"
            }
        })

        # ── 각 Pod 로그 ────────────────────────────────────────────────────────
        for pod in unhealthy_pods:
            key  = f"{pod['namespace']}/{pod['name']}"
            log  = pod_logs.get(key, "(로그 없음)")
            # Slack 메시지 블록 1개 최대 3000자 제한 고려하여 자름
            log_trimmed = log[:1500] + "\n...(생략)" if len(log) > 1500 else log
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*로그 — {key}*\n"
                        f"```{log_trimmed}```"
                    )
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "✅ 비정상 Pod 없음 — 모든 Pod가 정상 상태입니다."
            }
        })

    blocks.append({"type": "divider"})

    # ── Warning 이벤트 ─────────────────────────────────────────────────────────
    if warning_events:
        event_lines = "\n".join(
            f"  [{e['last_time']}] {e['reason']} — {e['namespace']}/{e['name']}\n"
            f"    {e['message']}"
            for e in warning_events
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*최근 Warning 이벤트 (최대 15개)*\n```{event_lines}```"
            }
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Warning 이벤트 없음*"}
        })

    blocks.append({"type": "divider"})

    # ── 노드 상태 ──────────────────────────────────────────────────────────────
    node_lines = "\n".join(
        f"  • {n['name']}   {n['ready']}   CPU: {n['cpu_capacity']}   Mem: {n['mem_capacity']}"
        for n in node_status
    )
    if not node_lines:
        node_lines = "  (노드 정보 없음)"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*노드 상태*\n```{node_lines}```"
        }
    })

    return {"blocks": blocks}


def send_slack(message: dict) -> None:
    """Slack Incoming Webhook으로 메시지를 전송한다."""
    payload = json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
    if body != "ok":
        raise RuntimeError(f"Slack 전송 실패: {body}")
    print("[incident-collector] Slack 전송 완료")


def main() -> None:
    load_kube_config()

    v1 = client.CoreV1Api()

    # 비정상 Pod 수집
    unhealthy_pods = get_unhealthy_pods(v1)

    # 비정상 Pod별 로그 수집
    pod_logs: dict[str, str] = {}
    for pod in unhealthy_pods:
        key = f"{pod['namespace']}/{pod['name']}"
        print(f"[incident-collector] 로그 수집: {key}")
        pod_logs[key] = get_pod_logs(v1, pod["namespace"], pod["name"])

    # Warning 이벤트 수집
    warning_events = get_warning_events(v1)

    # 노드 상태 수집
    node_status = get_node_status(v1)

    # Slack 메시지 생성 및 전송
    message = build_slack_message(unhealthy_pods, pod_logs, warning_events, node_status)
    send_slack(message)


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"[incident-collector] 환경변수 누락: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[incident-collector] 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
