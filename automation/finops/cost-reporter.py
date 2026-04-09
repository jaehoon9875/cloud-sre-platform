"""
cost-reporter.py
전일 GCP 비용을 BigQuery에서 조회하여 Slack으로 전송하는 일별 비용 리포트.

실행 방식: GitHub Actions scheduled workflow (매일 KST 09:00)
필요 환경변수:
  - GCP_PROJECT_ID       : GCP 프로젝트 ID
  - BIGQUERY_DATASET     : billing export 데이터셋 이름 (기본: billing_export)
  - SLACK_WEBHOOK_URL    : Slack Incoming Webhook URL
  - GOOGLE_APPLICATION_CREDENTIALS : GCP SA 키 파일 경로 (로컬 실행 시)
"""

import json
import os
import sys
import urllib.request
from datetime import date, timedelta

from google.cloud import bigquery


# ── 환경변수 로드 ──────────────────────────────────────────────────────────────
GCP_PROJECT_ID  = os.environ["GCP_PROJECT_ID"]
BQ_DATASET      = os.environ.get("BIGQUERY_DATASET", "billing_export")
SLACK_WEBHOOK   = os.environ["SLACK_WEBHOOK_URL"]

# 무료 체험 크레딧 총액 (KRW)
# GCP 무료 체험은 $300 USD 기준으로 제공되며, 가입 시점의 환율로 원화 금액이 확정된다.
# 이후 환율이 변동되어도 이 금액은 변하지 않는다.
# 값 확인: GCP 콘솔 → 결제 → 결제 계정 개요 → 무료 체험판 크레딧 → 총 크레딧
FREE_TRIAL_BUDGET_KRW = 453_008

MONTH_START = date.today().replace(day=1).isoformat()


def fetch_latest_date(client: bigquery.Client) -> str | None:
    """
    BigQuery에 데이터가 존재하는 가장 최근 날짜를 조회한다.
    이번 달 데이터가 없으면 최근 30일로 범위를 확장한다.
    데이터가 전혀 없으면 None을 반환한다.
    """
    lookback_start = (date.today() - timedelta(days=30)).isoformat()
    query = f"""
        SELECT MAX(DATE(usage_start_time)) AS latest_date
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{lookback_start}'
    """
    result = list(client.query(query).result())
    latest = result[0].latest_date
    if latest is None:
        print("[cost-reporter] BigQuery에 최근 30일 비용 데이터가 없습니다.")
        return None
    latest_str = latest.isoformat()
    print(f"[cost-reporter] BigQuery 최신 데이터 기준일: {latest_str}")
    return latest_str


def fetch_daily_cost_by_service(client: bigquery.Client, target_date: str) -> list[dict]:
    """
    서비스별 특정일 실제 사용량(gross) 조회.
    credits 배열에서 FREE_TRIAL 타입만 합산하여 소진된 크레딧을 정확히 계산한다.
    환율 계산 없이 BigQuery에 저장된 원화(KRW) 금액을 그대로 사용한다.
    """
    query = f"""
        SELECT
            service.description AS service,
            SUM(cost) AS gross,
            ABS(SUM(
                (SELECT IFNULL(SUM(c.amount), 0)
                 FROM UNNEST(credits) AS c
                 WHERE c.type = 'FREE_TRIAL')
            )) AS free_trial_used
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) = '{target_date}'
            AND cost > 0
        GROUP BY
            service
        ORDER BY
            gross DESC
    """
    rows = [
        {
            "service":         r.service,
            "gross":           float(r.gross),
            "free_trial_used": float(r.free_trial_used),
        }
        for r in client.query(query).result()
    ]
    print(f"[cost-reporter] 서비스별 비용 조회 완료: {len(rows)}개")
    return rows


def fetch_monthly_gross(client: bigquery.Client) -> float:
    """이번 달 누적 실제 사용량(gross)을 조회한다."""
    query = f"""
        SELECT SUM(cost) AS monthly_gross
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{MONTH_START}'
          AND cost > 0
    """
    result = list(client.query(query).result())
    gross = float(result[0].monthly_gross or 0.0)
    print(f"[cost-reporter] 이번 달 누적 사용량: ₩{gross:,.0f}")
    return gross


def fetch_cumulative_free_trial_used(client: bigquery.Client) -> float:
    """
    전체 기간 누적 FREE_TRIAL 크레딧 소진량을 조회한다.
    BigQuery credits 배열의 type='FREE_TRIAL' 항목만 합산하므로
    환율 계산 없이 정확한 원화(KRW) 금액이 반환된다.
    """
    query = f"""
        SELECT
            ABS(SUM(c.amount)) AS total_free_trial_used
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`,
            UNNEST(credits) AS c
        WHERE
            c.type = 'FREE_TRIAL'
    """
    result = list(client.query(query).result())
    used = float(result[0].total_free_trial_used or 0.0)
    print(f"[cost-reporter] 누적 크레딧 소진량: ₩{used:,.0f}")
    return used


def build_slack_message(
    target_date: str,
    daily_rows: list[dict],
    monthly_gross: float,
    cumulative_used: float,
) -> dict:
    """Slack Block Kit 형식의 메시지를 생성한다. 무료 크레딧 소진 현황을 중심으로 표시한다."""
    daily_gross = sum(r["gross"] for r in daily_rows)

    # 잔여 크레딧 및 소진율 계산
    credit_remaining = FREE_TRIAL_BUDGET_KRW - cumulative_used
    credit_used_pct  = cumulative_used / FREE_TRIAL_BUDGET_KRW * 100

    # 소진율에 따른 상태 표시
    if credit_used_pct >= 90:
        status_emoji = "🔴"
        status_text  = f"무료 크레딧의 {credit_used_pct:.1f}%를 소진했습니다. 즉시 사용량을 줄이세요."
    elif credit_used_pct >= 66:
        status_emoji = "🟡"
        status_text  = f"무료 크레딧의 {credit_used_pct:.1f}%를 소진했습니다. 추이를 주의하세요."
    else:
        status_emoji = "🟢"
        status_text  = f"무료 크레딧의 {credit_used_pct:.1f}%를 소진했습니다. 정상 범위입니다."

    # 서비스별 사용량 내역
    service_lines = "\n".join(
        f"  • {r['service']:<28} ₩{r['gross']:>10,.0f}"
        for r in daily_rows
    )
    if not service_lines:
        service_lines = "  • 해당 날짜 사용량 데이터 없음"

    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 GCP 비용 리포트 ({target_date})"
                }
            },
            # ── 무료 크레딧 현황 (핵심 지표) ──────────────────────────────
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*🎁 무료 체험 크레딧 현황*"}
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*소진된 크레딧 (누적)*\n₩{cumulative_used:,.0f}  ({credit_used_pct:.1f}%)"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*잔여 크레딧*\n₩{credit_remaining:,.0f}"
                    }
                ]
            },
            {"type": "divider"},
            # ── 사용량 요약 ────────────────────────────────────────────────
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*📈 실제 사용량 (크레딧 차감 전)*"}
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{target_date} 사용량*\n₩{daily_gross:,.0f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*{MONTH_START[:7]} 이번 달 누적*\n₩{monthly_gross:,.0f}"
                    }
                ]
            },
            # ── 서비스별 내역 ──────────────────────────────────────────────
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*서비스별 사용량 ({target_date})*\n```{service_lines}```"
                }
            },
            # ── 상태 요약 ──────────────────────────────────────────────────
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{status_emoji} {status_text}"}
            },
            {"type": "divider"}
        ]
    }
    return message


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
    print("[cost-reporter] Slack 전송 완료")


def build_no_data_message() -> dict:
    """BigQuery에 데이터가 없을 때 Slack에 보낼 안내 메시지를 생성한다."""
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 GCP 비용 리포트"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "⚠️ BigQuery에 최근 30일 비용 데이터가 없습니다.\n"
                        "GCP 콘솔 → 결제 → 결제 내보내기에서 BigQuery export 활성화 여부를 확인하세요.\n"
                        "활성화 후 데이터 수집까지 최대 48시간이 소요될 수 있습니다."
                    )
                }
            }
        ]
    }


def main() -> None:
    client = bigquery.Client(project=GCP_PROJECT_ID)

    # BigQuery에 데이터가 있는 가장 최근 날짜 조회 (export 지연 대응)
    target_date = fetch_latest_date(client)

    # 데이터가 없으면 안내 메시지만 전송하고 정상 종료
    if target_date is None:
        send_slack(build_no_data_message())
        return

    # 각종 비용 데이터 조회
    daily_rows      = fetch_daily_cost_by_service(client, target_date)
    monthly_gross   = fetch_monthly_gross(client)
    cumulative_used = fetch_cumulative_free_trial_used(client)

    # Slack 메시지 생성 및 전송
    message = build_slack_message(target_date, daily_rows, monthly_gross, cumulative_used)
    send_slack(message)


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"[cost-reporter] 환경변수 누락: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[cost-reporter] 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
