"""
test_currency.py
currency.py 단위 테스트

JUnit 대응표:
  pytest 함수           → @Test 메서드
  assert                → assertEquals / assertTrue
  pytest.raises()       → assertThrows()
  MagicMock()           → @Mock / Mockito.mock()
  client.query.return_value.result.return_value = rows
                        → when(client.query(...)).thenReturn(rows)
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 상위 디렉토리(finops/)를 sys.path에 추가 — Java의 classpath 설정과 동일한 역할
sys.path.insert(0, str(Path(__file__).parent.parent))

from currency import fetch_conversion_rate, to_usd


# ── to_usd() 테스트 ──────────────────────────────────────────────────────────
# 외부 의존성이 없는 순수 함수 → Mock 불필요 (JUnit의 단순 @Test와 동일)

class TestToUsd:
    """to_usd() — 현지 통화를 USD로 변환하는 순수 함수 테스트"""

    def test_krw를_usd로_변환(self):
        # 1 USD = 1400 KRW 기준, 7000 KRW → 5.0 USD
        result = to_usd(7000.0, "KRW", 1400.0)
        assert result == pytest.approx(5.0)  # 부동소수점 비교는 approx 사용

    def test_usd는_변환_없이_그대로_반환(self):
        result = to_usd(10.0, "USD", 1.0)
        assert result == 10.0

    def test_0원은_0달러(self):
        assert to_usd(0.0, "KRW", 1400.0) == 0.0

    def test_지원하지_않는_통화는_ValueError(self):
        # JUnit: assertThrows(ValueError.class, () -> to_usd(...))
        with pytest.raises(ValueError, match="지원하지 않는 통화"):
            to_usd(100.0, "EUR", 1.1)


# ── fetch_conversion_rate() 테스트 ───────────────────────────────────────────
# BigQuery 클라이언트를 Mock으로 대체 — Mockito와 동일한 역할

class TestFetchConversionRate:
    """fetch_conversion_rate() — BigQuery에서 환율을 조회하는 함수 테스트"""

    def _make_bq_client(self, rows: list) -> MagicMock:
        """
        BigQuery 클라이언트 Mock 생성 헬퍼.
        Java: Mockito.when(client.query(any())).thenReturn(mockResult)
        """
        client = MagicMock()
        client.query.return_value.result.return_value = rows
        return client

    def test_krw_환율_정상_조회(self):
        row = MagicMock()
        row.currency = "KRW"
        row.rate = 1400.0
        client = self._make_bq_client([row])

        currency, rate = fetch_conversion_rate(client, "test-project", "test_dataset")

        assert currency == "KRW"
        assert rate == pytest.approx(1400.0)

    def test_데이터_없으면_usd_기본값_반환(self):
        # 이번 달 BigQuery 데이터가 없는 경우 → USD, rate=1.0 반환
        client = self._make_bq_client([])

        currency, rate = fetch_conversion_rate(client, "test-project", "test_dataset")

        assert currency == "USD"
        assert rate == 1.0

    def test_currency_필드가_None이면_usd_기본값_반환(self):
        row = MagicMock()
        row.currency = None
        client = self._make_bq_client([row])

        currency, rate = fetch_conversion_rate(client, "test-project", "test_dataset")

        assert currency == "USD"
        assert rate == 1.0

    def test_지원하지_않는_통화는_ValueError(self):
        row = MagicMock()
        row.currency = "EUR"
        row.rate = 1.1
        client = self._make_bq_client([row])

        with pytest.raises(ValueError, match="지원하지 않는 통화"):
            fetch_conversion_rate(client, "test-project", "test_dataset")

    def test_생성된_쿼리에_project_id와_dataset이_포함됨(self):
        # SQL 쿼리 문자열에 올바른 테이블 경로가 들어가는지 검증
        # Java: verify(client).query(argThat(q -> q.contains("my-project")))
        client = self._make_bq_client([])

        fetch_conversion_rate(client, "my-project", "my_dataset")

        called_query: str = client.query.call_args[0][0]
        assert "my-project" in called_query
        assert "my_dataset" in called_query

    def test_query에_group_by_currency_포함됨(self):
        # 이전에 GROUP BY 누락으로 BigQuery 400 에러가 발생했던 회귀 방지 테스트
        client = self._make_bq_client([])

        fetch_conversion_rate(client, "test-project", "test_dataset")

        called_query: str = client.query.call_args[0][0].upper()
        assert "GROUP BY" in called_query
        assert "CURRENCY" in called_query
