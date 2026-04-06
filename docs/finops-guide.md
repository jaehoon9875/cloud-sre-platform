# FinOps Guide

## 비용 구조

| 항목 | 비용 | 비고 |
|------|------|------|
| GKE control plane | $0.10/hr (~$72/month) | 항상 발생 |
| spot node (e2-medium 기준) | ~$15~20/month/node | scale-down으로 절감 |
| Artifact Registry | 미미 | 소용량 |
| BigQuery | 무료 수준 | billing export 쿼리 |

## 비용 절감 전략

### 1. 야간/주말 node scale-down

```bash
# 수동 실행
make cluster-down   # node pool → 0
make cluster-up     # node pool → 복구

# 자동화
GitHub Actions scheduled workflow
- 평일 22:00 KST → scale-down
- 평일 08:00 KST → scale-up
```

### 2. GCP Budget Alert

- $250 도달 시 Slack 알림
- $300 도달 시 이메일 알림 (GCP 기본)

### 3. FinOps 모니터링

<!-- 파이프라인 구성 완료 후 상세 내용 추가 -->

## Grafana FinOps 대시보드

<!-- dashboards/finops-cost.json 구성 완료 후 스크린샷 및 설명 추가 -->
