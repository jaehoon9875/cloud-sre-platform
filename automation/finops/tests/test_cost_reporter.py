"""
test_cost_reporter.py
cost-reporter.py 단위 테스트

주의: cost-reporter.py는 파일명에 하이픈이 있어 일반 import가 불가능.
     importlib으로 로드한다 (Java의 Class.forName()과 유사).
     또한 모듈 상단에서 os.environ을 읽으므로, 로드 전에 환경변수를 주입해야 한다.
"""
import os
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_cost_reporter():
    """
    cost-reporter.py를 테스트용 환경변수와 함께 로드한다.
    모듈 최상단에서 os.environ["GCP_PROJECT_ID"] 등을 읽기 때문에
    patch.dict로 먼저 환경변수를 주입한 뒤 exec_module을 호출한다.
    """
    env = {
        "GCP_PROJECT_ID": "test-project",
        "BIGQUERY_DATASET": "test_dataset",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
    }
    with patch.dict(os.environ, env):
        spec = importlib.util.spec_from_file_location(
            "cost_reporter",
            Path(__file__).parent.parent / "cost-reporter.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


# 모듈을 한 번만 로드 (세션 전체에서 재사용)
_mod = _load_cost_reporter()


# ── build_slack_message() 테스트 ─────────────────────────────────────────────
# 순수 함수 — Mock 불필요

class TestBuildSlackMessage:
    """build_slack_message() — Slack Block Kit 메시지 생성 함수 테스트"""

    # 테스트용 공통 샘플 데이터 (Java의 @BeforeEach 필드 초기화와 동일)
    SAMPLE_ROWS = [
        {"service": "Kubernetes Engine", "gross_usd": 3.50, "free_trial_used_usd": 3.50},
        {"service": "Compute Engine",    "gross_usd": 1.20, "free_trial_used_usd": 1.20},
    ]

    def test_blocks_키가_존재함(self):
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 30.0)
        assert "blocks" in msg
        assert len(msg["blocks"]) > 0

    def test_헤더에_날짜가_포함됨(self):
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 30.0)
        header_text = msg["blocks"][0]["text"]["text"]
        assert "2026-04-08" in header_text

    def test_서비스명이_메시지에_포함됨(self):
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 30.0)
        msg_str = str(msg)
        assert "Kubernetes Engine" in msg_str
        assert "Compute Engine" in msg_str

    def test_크레딧_소진율_90_이상이면_빨간_이모지(self):
        # $300 중 $270 소진 → 90.0%
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 270.0)
        assert "🔴" in str(msg)

    def test_크레딧_소진율_66_이상이면_노란_이모지(self):
        # $300 중 $200 소진 → 66.6%
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 200.0)
        assert "🟡" in str(msg)

    def test_크레딧_소진율_낮으면_초록_이모지(self):
        # $300 중 $30 소진 → 10%
        msg = _mod.build_slack_message("2026-04-08", self.SAMPLE_ROWS, 50.0, 30.0)
        assert "🟢" in str(msg)

    def test_서비스_데이터_없으면_안내_문구_표시(self):
        msg = _mod.build_slack_message("2026-04-08", [], 0.0, 0.0)
        assert "해당 날짜 사용량 데이터 없음" in str(msg)


# ── build_no_data_message() 테스트 ──────────────────────────────────────────

class TestBuildNoDataMessage:
    """build_no_data_message() — BigQuery 데이터 없음 안내 메시지 테스트"""

    def test_blocks_키가_존재함(self):
        msg = _mod.build_no_data_message()
        assert "blocks" in msg

    def test_bigquery_export_안내_문구_포함(self):
        msg = _mod.build_no_data_message()
        assert "BigQuery export" in str(msg)


# ── fetch_daily_cost_by_service() 테스트 ─────────────────────────────────────
# BigQuery 클라이언트를 Mock으로 대체

class TestFetchDailyCostByService:
    """fetch_daily_cost_by_service() — 서비스별 당일 비용 조회 테스트"""

    def _make_row(self, service: str, gross_local: float, free_trial_used_local: float) -> MagicMock:
        """BigQuery 결과 행(Row) Mock 생성 헬퍼"""
        row = MagicMock()
        row.service = service
        row.gross_local = gross_local
        row.free_trial_used_local = free_trial_used_local
        return row

    def test_서비스별_비용_정상_조회(self):
        rows = [
            self._make_row("Kubernetes Engine", 4900.0, 4900.0),
            self._make_row("Compute Engine",    1680.0, 1680.0),
        ]
        client = MagicMock()
        client.query.return_value.result.return_value = rows

        result = _mod.fetch_daily_cost_by_service(client, "2026-04-08")

        assert len(result) == 2
        assert result[0]["service"] == "Kubernetes Engine"
        assert result[0]["gross_local"] == pytest.approx(4900.0)
        assert result[1]["service"] == "Compute Engine"

    def test_데이터_없으면_빈_리스트_반환(self):
        client = MagicMock()
        client.query.return_value.result.return_value = []

        result = _mod.fetch_daily_cost_by_service(client, "2026-04-08")

        assert result == []

    def test_반환_딕셔너리에_필요한_키가_모두_존재함(self):
        rows = [self._make_row("Kubernetes Engine", 4900.0, 4900.0)]
        client = MagicMock()
        client.query.return_value.result.return_value = rows

        result = _mod.fetch_daily_cost_by_service(client, "2026-04-08")

        assert "service" in result[0]
        assert "gross_local" in result[0]
        assert "free_trial_used_local" in result[0]

    def test_생성된_쿼리에_target_date가_포함됨(self):
        client = MagicMock()
        client.query.return_value.result.return_value = []

        _mod.fetch_daily_cost_by_service(client, "2026-04-08")

        called_query: str = client.query.call_args[0][0]
        assert "2026-04-08" in called_query


# ── fetch_monthly_gross() 테스트 ─────────────────────────────────────────────

class TestFetchMonthlyGross:
    """fetch_monthly_gross() — 월 누적 비용 조회 테스트"""

    def test_정상_금액_반환(self):
        row = MagicMock()
        row.monthly_gross_local = 50000.0
        client = MagicMock()
        client.query.return_value.result.return_value = [row]

        result = _mod.fetch_monthly_gross(client)

        assert result == pytest.approx(50000.0)

    def test_null이면_0_반환(self):
        # BigQuery SUM이 NULL을 반환할 때 (데이터 없음)
        row = MagicMock()
        row.monthly_gross_local = None
        client = MagicMock()
        client.query.return_value.result.return_value = [row]

        result = _mod.fetch_monthly_gross(client)

        assert result == 0.0


# ── fetch_cumulative_free_trial_used() 테스트 ────────────────────────────────

class TestFetchCumulativeFreeTrialUsed:
    """fetch_cumulative_free_trial_used() — 누적 크레딧 소진량 조회 테스트"""

    def test_정상_누적량_반환(self):
        row = MagicMock()
        row.total_free_trial_used_local = 150000.0
        client = MagicMock()
        client.query.return_value.result.return_value = [row]

        result = _mod.fetch_cumulative_free_trial_used(client)

        assert result == pytest.approx(150000.0)

    def test_null이면_0_반환(self):
        row = MagicMock()
        row.total_free_trial_used_local = None
        client = MagicMock()
        client.query.return_value.result.return_value = [row]

        result = _mod.fetch_cumulative_free_trial_used(client)

        assert result == 0.0

    def test_생성된_쿼리에_FREE_TRIAL_필터가_포함됨(self):
        # FREE_TRIAL 타입만 필터링하는지 검증 (회귀 방지)
        client = MagicMock()
        client.query.return_value.result.return_value = [MagicMock(total_free_trial_used_local=0)]

        _mod.fetch_cumulative_free_trial_used(client)

        called_query: str = client.query.call_args[0][0]
        assert "FREE_TRIAL" in called_query
