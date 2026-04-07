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

### 3. BigQuery Billing Export 활성화

GCP 결제 데이터를 BigQuery로 내보내는 설정. **GCP 콘솔에서만 설정 가능** (Terraform 미지원).  
이 데이터를 기반으로 Stage 3에서 Python FinOps 파이프라인을 구성한다.

**설정 절차:**

1. GCP 콘솔 → 결제(Billing) → 결제 내보내기(Billing export)
2. **BigQuery 내보내기** 탭 선택
3. **수정** 클릭 후 아래 값 입력:
   - 프로젝트: `cloud-sre-platform-dev`
   - 데이터세트 이름: `billing_export` (없으면 새로 생성)
4. **저장** 클릭

> 데이터가 BigQuery에 쌓이기까지 최대 24시간 소요될 수 있다.  
> 내보낸 데이터는 BigQuery 콘솔에서 `billing_export.gcp_billing_export_v1_*` 테이블로 확인 가능.

### 4. FinOps 모니터링

<!-- 파이프라인 구성 완료 후 상세 내용 추가 -->

## Grafana FinOps 대시보드

<!-- dashboards/finops-cost.json 구성 완료 후 스크린샷 및 설명 추가 -->
