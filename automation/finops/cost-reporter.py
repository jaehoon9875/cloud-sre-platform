"""
cost-reporter.py
전일 GCP 비용을 BigQuery에서 조회하여 Slack으로 전송하는 일별 비용 리포트.

실행 방식: GitHub Actions scheduled workflow (매일 KST 09:00)
필요 환경변수:
  - GCP_PROJECT_ID       : GCP 프로젝트 ID
  - BIGQUERY_DATASET     : billing export 데이터셋 이름 (기본: billing_export)
  - SLACK_WEBHOOK_URL    : Slack Incoming Webhook URL
  - GOOGLE_APPLICATION_CREDENTIALS : GCP SA 키 파일 경로 (로컬 실행 시)

통화 처리:
  BigQuery에서 조회한 현지 통화(KRW) 금액을 currency.py를 통해 USD로 변환 후 표시한다.
  currency_conversion_rate는 GCP가 매월 초에 고정하는 값으로, 월 내 환율 변동에 무관하다.
"""

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from google.cloud import bigquery

# 같은 디렉토리의 currency 유틸리티 로드
sys.path.insert(0, str(Path(__file__).parent))
from currency import fetch_conversion_rate, to_usd


# ── 환경변수 로드 ──────────────────────────────────────────────────────────────
GCP_PROJECT_ID  = os.environ["GCP_PROJECT_ID"]
BQ_DATASET      = os.environ.get("BIGQUERY_DATASET", "billing_export")
SLACK_WEBHOOK   = os.environ["SLACK_WEBHOOK_URL"]

# 무료 체험 크레딧 총액 (USD)
# GCP 무료 체험은 $300 USD 기준으로 제공된다.
# BigQuery 데이터는 KRW이지만 currency.py에서 USD로 변환하므로 여기서도 USD 기준으로 관리한다.
FREE_TRIAL_BUDGET_USD = 300.0

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
    반환값은 현지 통화(KRW) 기준이며, 이후 to_usd()로 변환된다.
    """
    query = f"""
        SELECT
            service.description AS service,
            SUM(cost) AS gross_local,
            ABS(SUM(
                (SELECT IFNULL(SUM(c.amount), 0)
                 FROM UNNEST(credits) AS c
                 WHERE c.type = 'FREE_TRIAL')
            )) AS free_trial_used_local
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) = '{target_date}'
            AND cost > 0
        GROUP BY
            service
        ORDER BY
            gross_local DESC
    """
    rows = [
        {
            "service":              r.service,
            "gross_local":          float(r.gross_local),
            "free_trial_used_local": float(r.free_trial_used_local),
        }
        for r in client.query(query).result()
    ]
    print(f"[cost-reporter] 서비스별 비용 조회 완료: {len(rows)}개")
    return rows


def fetch_monthly_gross(client: bigquery.Client) -> float:
    """
    이번 달 누적 실제 사용량(gross)을 조회한다.
    반환값은 현지 통화(KRW) 기준이며, 이후 to_usd()로 변환된다.
    """
    query = f"""
        SELECT SUM(cost) AS monthly_gross_local
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= '{MONTH_START}'
          AND cost > 0
    """
    result = list(client.query(query).result())
    return float(result[0].monthly_gross_local or 0.0)


def fetch_cumulative_free_trial_used(client: bigquery.Client) -> float:
    """
    전체 기간 누적 FREE_TRIAL 크레딧 소진량을 조회한다.
    BigQuery credits 배열의 type='FREE_TRIAL' 항목만 합산한다.
    반환값은 현지 통화(KRW) 기준이며, 이후 to_usd()로 변환된다.
    """
    query = f"""
        SELECT ABS(SUM(c.amount)) AS total_free_trial_used_local
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`,
             UNNEST(credits) AS c
        WHERE c.type = 'FREE_TRIAL'
    """
    result = list(client.query(query).result())
    return float(result[0].total_free_trial_used_local or 0.0)


def build_slack_message(
    target_date: str,
    daily_rows: list[dict],
    monthly_gross_usd: float,
    cumulative_used_usd: float,
) -> dict:
    """Slack Block Kit 형식의 메시지를 생성한다. 무료 크레딧 소진 현황을 중심으로 표시한다."""
    daily_gross_usd = sum(r["gross_usd"] for r in daily_rows)

    # 잔여 크레딧 및 소진율 계산 (USD 기준)
    credit_remaining_usd = FREE_TRIAL_BUDGET_USD - cumulative_used_usd
    credit_used_pct      = cumulative_used_usd / FREE_TRIAL_BUDGET_USD * 100

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

    # 서비스별 사용량 내역 (USD)
    service_lines = "\n".join(
        f"  • {r['service']:<28} ${r['gross_usd']:>8.2f}"
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
                "text": {"type": "mrkdwn", "text": "*🎁 무료 체험 크레딧 현황 ($300 기준)*"}
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*소진된 크레딧 (누적)*\n${cumulative_used_usd:.2f}  ({credit_used_pct:.1f}%)"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*잔여 크레딧*\n${credit_remaining_usd:.2f}"
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
                        "text": f"*{target_date} 사용량*\n${daily_gross_usd:.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*{MONTH_START[:7]} 이번 달 누적*\n${monthly_gross_usd:.2f}"
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
    if target_date is None:
        send_slack(build_no_data_message())
        return

    # 통화 및 환율 조회 (currency_conversion_rate — GCP 월초 고정값)
    currency, rate = fetch_conversion_rate(client, GCP_PROJECT_ID, BQ_DATASET)

    # 서비스별 비용 조회 후 USD 변환
    daily_rows = fetch_daily_cost_by_service(client, target_date)
    for row in daily_rows:
        row["gross_usd"]          = to_usd(row["gross_local"], currency, rate)
        row["free_trial_used_usd"] = to_usd(row["free_trial_used_local"], currency, rate)

    # 이번 달 누적 및 누적 크레딧 소진량 USD 변환
    monthly_gross_usd   = to_usd(fetch_monthly_gross(client), currency, rate)
    cumulative_used_usd = to_usd(fetch_cumulative_free_trial_used(client), currency, rate)
    print(f"[cost-reporter] 이번 달 누적 사용량: ${monthly_gross_usd:.2f}")
    print(f"[cost-reporter] 누적 크레딧 소진량: ${cumulative_used_usd:.2f}")

    # Slack 메시지 생성 및 전송
    message = build_slack_message(target_date, daily_rows, monthly_gross_usd, cumulative_used_usd)
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
