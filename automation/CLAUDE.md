# CLAUDE.md - automation/

## 역할

Python 기반 운영 자동화 스크립트 모음.
FinOps, 비용 리포트, 야간 스케줄링, 장애 대응을 자동화한다.

## 구조

```
automation/
├── finops/
│   ├── billing-exporter.py       # BigQuery → Prometheus Pushgateway
│   ├── cost-reporter.py          # 일별 비용 Slack 리포트
│   └── budget-alert-handler.py   # GCP Budget Alert webhook 처리
├── scheduler/
│   └── scale-scheduler.py        # 야간/주말 GKE node scale-down
└── incident/
    └── incident-collector.py     # 장애 시 GKE 진단 정보 수집
```

## 공통 사항

- Python 3.11+
- 환경변수로 설정값 주입 (GCP credentials, Slack webhook URL 등)
- 민감한 값은 .env 파일 또는 GCP Secret Manager 사용 (.gitignore 처리)

## 주요 스크립트 설명

### billing-exporter.py
- GCP BigQuery의 billing export 테이블을 조회
- 네임스페이스별, 서비스별 비용을 Prometheus 메트릭으로 변환
- Prometheus Pushgateway로 push
- GitHub Actions scheduled workflow로 주기적 실행

### cost-reporter.py
- 전일 GCP 비용 요약을 Slack으로 전송
- 예산 소진율 포함

### scale-scheduler.py
- GKE node pool 크기를 조정 (min/max node 수 변경)
- 야간(22:00) → node 0, 주간(08:00) → node 복구
- GitHub Actions scheduled workflow로 실행
