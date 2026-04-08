"""
billing-exporter.py
BigQuery GCP 결제 데이터를 Prometheus Pushgateway로 전송하는 FinOps 파이프라인.

실행 방식: GitHub Actions scheduled workflow (매일 KST 09:00)
필요 환경변수:
  - GCP_PROJECT_ID       : GCP 프로젝트 ID
  - BIGQUERY_DATASET     : billing export 데이터셋 이름 (기본: billing_export)
  - PUSHGATEWAY_URL      : Prometheus Pushgateway 주소 (예: http://pushgateway.monitoring:9091)
  - GOOGLE_APPLICATION_CREDENTIALS : GCP SA 키 파일 경로 (로컬 실행 시)
"""

import os
import sys
from datetime import date, timedelta

from google.cloud import bigquery
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway


# ── 환경변수 로드 ──────────────────────────────────────────────────────────────
GCP_PROJECT_ID   = os.environ["GCP_PROJECT_ID"]
BQ_DATASET       = os.environ.get("BIGQUERY_DATASET", "billing_export")
PUSHGATEWAY_URL  = os.environ["PUSHGATEWAY_URL"]
JOB_NAME         = "billing-exporter"

# 조회 기준일: 어제 (KST 기준 전일 비용)
TARGET_DATE = (date.today() - timedelta(days=1)).isoformat()


def fetch_daily_cost_by_service(client: bigquery.Client) -> list[dict]:
    """
    BigQuery billing export 테이블에서 서비스별 전일 비용을 조회한다.
    반환: [{"service": "Kubernetes Engine", "cost_usd": 2.45}, ...]
    """
    query = f"""
        SELECT
            service.description AS service,
            SUM(cost)           AS cost_usd
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) = '{TARGET_DATE}'
        GROUP BY
            service
        ORDER BY
            cost_usd DESC
    """
    print(f"[billing-exporter] BigQuery 조회 기준일: {TARGET_DATE}")
    results = client.query(query).result()
    rows = [{"service": row.service, "cost_usd": float(row.cost_usd)} for row in results]
    print(f"[billing-exporter] 조회된 서비스 수: {len(rows)}")
    return rows


def fetch_monthly_total(client: bigquery.Client) -> float:
    """
    BigQuery billing export 테이블에서 이번 달 누적 총 비용을 조회한다.
    예산 소진율 계산에 사용된다.
    """
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    query = f"""
        SELECT
            SUM(cost) AS total_cost_usd
        FROM
            `{GCP_PROJECT_ID}.{BQ_DATASET}.gcp_billing_export_v1_*`
        WHERE
            DATE(usage_start_time) >= '{month_start}'
    """
    result = list(client.query(query).result())
    total = float(result[0].total_cost_usd or 0.0)
    print(f"[billing-exporter] 이번 달 누적 비용: ${total:.4f}")
    return total


def push_metrics(daily_rows: list[dict], monthly_total: float) -> None:
    """
    수집된 비용 데이터를 Prometheus 메트릭으로 변환하여 Pushgateway에 전송한다.
    생성 메트릭:
      - gcp_cost_daily_usd{service, date}  : 서비스별 전일 비용 (USD)
      - gcp_cost_monthly_total_usd{date}   : 이번 달 누적 총 비용 (USD)
    """
    registry = CollectorRegistry()

    # 서비스별 전일 비용 게이지
    daily_gauge = Gauge(
        "gcp_cost_daily_usd",
        "GCP 서비스별 전일 비용 (USD)",
        labelnames=["service", "date"],
        registry=registry,
    )
    for row in daily_rows:
        daily_gauge.labels(service=row["service"], date=TARGET_DATE).set(row["cost_usd"])

    # 이번 달 누적 총 비용 게이지
    monthly_gauge = Gauge(
        "gcp_cost_monthly_total_usd",
        "GCP 이번 달 누적 총 비용 (USD)",
        labelnames=["date"],
        registry=registry,
    )
    monthly_gauge.labels(date=TARGET_DATE).set(monthly_total)

    # Pushgateway로 전송
    push_to_gateway(PUSHGATEWAY_URL, job=JOB_NAME, registry=registry)
    print(f"[billing-exporter] Pushgateway 전송 완료 → {PUSHGATEWAY_URL}")


def main() -> None:
    client = bigquery.Client(project=GCP_PROJECT_ID)

    # 서비스별 전일 비용 조회
    daily_rows = fetch_daily_cost_by_service(client)

    # 이번 달 누적 총 비용 조회
    monthly_total = fetch_monthly_total(client)

    # Pushgateway로 메트릭 전송
    push_metrics(daily_rows, monthly_total)


if __name__ == "__main__":
    try:
        main()
    except KeyError as e:
        print(f"[billing-exporter] 환경변수 누락: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[billing-exporter] 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
