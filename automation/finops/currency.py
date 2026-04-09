"""
currency.py
GCP billing export 데이터의 통화 변환 공통 유틸리티.

배경:
  GCP 결제 계정의 통화는 계정 생성 국가를 따르며 이후 변경 불가하다.
  한국 계정은 KRW로 운영되고, BigQuery billing export 데이터도 KRW로 저장된다.
  billing-exporter, cost-reporter 두 스크립트에서 공통으로 사용한다.

변환 방식:
  BigQuery billing export의 currency_conversion_rate 필드를 활용한다.
  이 값은 GCP가 매월 초에 고정하는 환율로, 1 USD = N 현지통화를 의미한다.
  cost_usd = cost_local / currency_conversion_rate

현재 지원 통화:
  - KRW → USD 변환 지원
  - USD 계정은 변환 없이 그대로 반환
"""

from google.cloud import bigquery


# 현재 지원하는 변환 대상 통화 목록
SUPPORTED_CURRENCIES = {"USD", "KRW"}


def fetch_conversion_rate(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
) -> tuple[str, float]:
    """
    BigQuery billing export에서 이번 달 통화 단위와 환율을 조회한다.

    currency_conversion_rate: GCP가 매월 초에 고정하는 값 (1 USD = N 현지통화)
    월 중간에 환율이 변동되어도 이 값은 해당 월 내에 변하지 않는다.

    반환:
      (currency, rate)
      - currency: "KRW", "USD" 등 ISO 4217 통화 코드
      - rate: 1 USD = rate 현지통화 (USD 계정이면 1.0)
    """
    query = f"""
        SELECT
            currency,
            MAX(currency_conversion_rate) AS rate
        FROM `{project_id}.{dataset}.gcp_billing_export_v1_*`
        WHERE DATE(usage_start_time) >= DATE_TRUNC(CURRENT_DATE(), MONTH)
          AND currency_conversion_rate IS NOT NULL
          AND currency_conversion_rate > 0
        GROUP BY currency
        LIMIT 1
    """
    result = list(client.query(query).result())

    # 데이터가 없거나 USD 계정이면 변환 불필요
    if not result or result[0].currency is None:
        print("[currency] 환율 데이터 없음 — USD 계정으로 간주하여 rate=1.0 사용")
        return "USD", 1.0

    currency = result[0].currency
    rate = float(result[0].rate)

    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(
            f"[currency] 지원하지 않는 통화: {currency} (현재 지원: {SUPPORTED_CURRENCIES})"
        )

    print(f"[currency] 통화: {currency}, 이번 달 환율: 1 USD = {rate:,.2f} {currency}")
    return currency, rate


def to_usd(amount: float, currency: str, rate: float) -> float:
    """
    현지 통화 금액을 USD로 변환한다.

    args:
      amount  : 현지 통화 금액 (예: 6500.0 KRW)
      currency: ISO 4217 통화 코드 (예: "KRW")
      rate    : 1 USD = rate 현지통화 (fetch_conversion_rate 반환값)

    반환: USD 금액 (float)
    """
    if currency == "USD":
        return amount
    if currency == "KRW":
        return amount / rate
    raise ValueError(
        f"[currency] 지원하지 않는 통화: {currency} (현재 지원: {SUPPORTED_CURRENCIES})"
    )
