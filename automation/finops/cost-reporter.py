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

MONTH_START  = date.today().replace(day=1).isoformat()


def fetch_latest_date(client: bigquery.Client) -> str:
    """BigQuery에 데이터가 존재하는 가장 최근 날짜를 조회한다."""
    query = f"""
        SELECT MAX(DATE(usage_start_time)) AS latest_date
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{MONTH_START}'
    """
    result = list(client.query(query).result())
    latest = result[0].latest_date
    if latest is None:
        raise RuntimeError("BigQuery에 이번 달 비용 데이터가 없습니다.")
    latest_str = latest.isoformat()
    print(f"[cost-reporter] BigQuery 최신 데이터 기준일: {latest_str}")
    return latest_str


def fetch_daily_cost_by_service(client: bigquery.Client, target_date: str) -> list[dict]:
    """
    서비스별 특정일 비용 조회.
    gross_usd: 크레딧 적용 전 금액 / net_usd: 크레딧 적용 후 실청구 금액
    """
    query = f"""
        SELECT
            service.description AS service,
            SUM(cost) AS gross_usd,
            SUM(cost) + SUM(
                (SELECT IFNULL(SUM(c.amount), 0) FROM UNNEST(credits) AS c)
            ) AS net_usd
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) = '{target_date}'
            AND cost > 0
        GROUP BY
            service
        ORDER BY
            gross_usd DESC
    """
    rows = [
        {
            "service":   r.service,
            "gross_usd": float(r.gross_usd),
            "net_usd":   float(r.net_usd),
        }
        for r in client.query(query).result()
    ]
    print(f"[cost-reporter] 서비스별 비용 조회 완료: {len(rows)}개")
    return rows


def fetch_monthly_total(client: bigquery.Client) -> dict:
    """
    이번 달 누적 총 비용 조회.
    반환: {"gross_usd": ..., "net_usd": ...}
    """
    query = f"""
        SELECT
            SUM(cost) AS gross_usd,
            SUM(cost) + SUM(
                (SELECT IFNULL(SUM(c.amount), 0) FROM UNNEST(credits) AS c)
            ) AS net_usd
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{MONTH_START}'
    """
    result = list(client.query(query).result())
    gross = float(result[0].gross_usd or 0.0)
    net   = float(result[0].net_usd   or 0.0)
    print(f"[cost-reporter] 이번 달 누적 비용 — gross: ${gross:.2f}, net: ${net:.2f}")
    return {"gross_usd": gross, "net_usd": net}


def build_slack_message(target_date: str, daily_rows: list[dict], monthly_total: dict) -> dict:
    """Slack Block Kit 형식의 메시지를 생성한다."""
    daily_gross = sum(r["gross_usd"] for r in daily_rows)
    daily_net   = sum(r["net_usd"]   for r in daily_rows)
    monthly_gross = monthly_total["gross_usd"]
    monthly_net   = monthly_total["net_usd"]

    # 예산 소진율은 gross 기준 (실제 사용량 파악용)
    budget_pct = monthly_gross / BUDGET_USD * 100
    if budget_pct >= 90:
        status_emoji = "🔴"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 즉시 비용 절감이 필요합니다."
    elif budget_pct >= 66:
        status_emoji = "🟡"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 비용 추이를 주의 깊게 모니터링하세요."
    else:
        status_emoji = "🟢"
        status_text  = f"예산의 {budget_pct:.1f}%를 소진했습니다. 정상 범위입니다."

    # 서비스별 내역 — gross / net 함께 표시
    service_lines = "\n".join(
        f"  • {r['service']:<28} ${r['gross_usd']:.2f}  (실청구 ${r['net_usd']:.2f})"
        for r in daily_rows
    )
    if not service_lines:
        service_lines = "  • 해당 날짜 비용 데이터 없음"

    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 GCP 비용 리포트 ({MONTH_START} ~ {target_date})"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*{target_date} 사용량*\n"
                            f"정가 ${daily_gross:.2f}  →  실청구 ${daily_net:.2f}"
                        )
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*이번 달 누적*\n"
                            f"정가 ${monthly_gross:.2f}  →  실청구 ${monthly_net:.2f}"
                        )
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*서비스별 내역 ({target_date})*\n```{service_lines}```"
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

    # BigQuery에 데이터가 있는 가장 최근 날짜 조회 (export 지연 대응)
    target_date   = fetch_latest_date(client)
    # 서비스별 비용 조회 (최신 데이터 기준일)
    daily_rows    = fetch_daily_cost_by_service(client, target_date)
    # 이번 달 누적 총 비용 조회
    monthly_total = fetch_monthly_total(client)

    # Slack 메시지 생성 및 전송
    message = build_slack_message(target_date, daily_rows, monthly_total)
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
