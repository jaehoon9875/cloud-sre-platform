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

# 예산 기준 (USD)
BUDGET_USD = 300.0

# 조회 기준일: 어제
TARGET_DATE  = (date.today() - timedelta(days=1)).isoformat()
MONTH_START  = date.today().replace(day=1).isoformat()


def fetch_daily_cost_by_service(client: bigquery.Client) -> list[dict]:
    """서비스별 전일 비용 조회. 반환: [{"service": ..., "cost_usd": ...}, ...]"""
    query = f"""
        SELECT
            service.description AS service,
            SUM(cost)           AS cost_usd
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) = '{TARGET_DATE}'
            AND cost > 0
        GROUP BY
            service
        ORDER BY
            cost_usd DESC
    """
    rows = [{"service": r.service, "cost_usd": float(r.cost_usd)}
            for r in client.query(query).result()]
    print(f"[cost-reporter] 서비스별 전일 비용 조회 완료: {len(rows)}개")
    return rows


def fetch_monthly_total(client: bigquery.Client) -> float:
    """이번 달 누적 총 비용 조회."""
    query = f"""
        SELECT SUM(cost) AS total
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{MONTH_START}'
    """
    result = list(client.query(query).result())
    total = float(result[0].total or 0.0)
    print(f"[cost-reporter] 이번 달 누적 비용: ${total:.2f}")
    return total


def build_slack_message(daily_rows: list[dict], monthly_total: float) -> dict:
    """Slack Block Kit 형식의 메시지를 생성한다."""
    daily_total = sum(r["cost_usd"] for r in daily_rows)
    budget_pct  = monthly_total / BUDGET_USD * 100

    # 예산 소진율에 따른 이모지 결정
    if budget_pct >= 90:
        status_emoji = "🔴"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 즉시 비용 절감이 필요합니다."
    elif budget_pct >= 66:
        status_emoji = "🟡"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 비용 추이를 주의 깊게 모니터링하세요."
    else:
        status_emoji = "🟢"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 정상 범위입니다."

    # 서비스별 내역 텍스트 생성
    service_lines = "\n".join(
        f"  • {r['service']:<30} ${r['cost_usd']:.2f}"
        for r in daily_rows
    )
    if not service_lines:
        service_lines = "  • 전일 비용 데이터 없음 (BigQuery export 지연 가능)"

    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 GCP 일별 비용 리포트 ({TARGET_DATE})"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*어제 총 비용*\n${daily_total:.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*이번 달 누적*\n${monthly_total:.2f} / ${BUDGET_USD:.0f}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*서비스별 내역*\n```{service_lines}```"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} {status_text}"
                }
            },
            {
                "type": "divider"
            }
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


def main() -> None:
    client = bigquery.Client(project=GCP_PROJECT_ID)

    # 서비스별 전일 비용 조회
    daily_rows    = fetch_daily_cost_by_service(client)
    # 이번 달 누적 총 비용 조회
    monthly_total = fetch_monthly_total(client)

    # Slack 메시지 생성 및 전송
    message = build_slack_message(daily_rows, monthly_total)
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
