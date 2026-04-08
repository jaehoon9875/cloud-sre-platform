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

파이프라인 흐름:

```
BigQuery (gcp_billing_export_v1_*)
    │  billing-exporter CronJob (매일 KST 09:00)
    ▼
Prometheus Pushgateway (monitoring 네임스페이스)
    │  Prometheus scrape
    ▼
Grafana FinOps 대시보드 (dashboards/finops-cost.json)
```

---

## FinOps 파이프라인 초기 설정

billing-exporter CronJob이 BigQuery에 접근하려면 GCP SA와 GKE Workload Identity 연결이 필요하다.  
**최초 1회만 실행**하면 된다.

### Step 1. GCP 서비스 계정 생성

```bash
gcloud iam service-accounts create billing-exporter \
  --project=cloud-sre-platform-dev \
  --display-name="billing-exporter (FinOps CronJob)"
```

> "already exists" 오류가 뜨면 이미 생성된 것이므로 Step 2로 넘어간다.
> 기존 SA 확인: `gcloud iam service-accounts describe billing-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com`

### Step 2. BigQuery 권한 부여

```bash
# 결제 데이터 테이블 읽기 권한
gcloud projects add-iam-policy-binding cloud-sre-platform-dev \
  --member="serviceAccount:billing-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

# BigQuery 쿼리 실행 권한
gcloud projects add-iam-policy-binding cloud-sre-platform-dev \
  --member="serviceAccount:billing-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

### Step 3. GKE Workload Identity 연결

K8s ServiceAccount(`monitoring/billing-exporter`)가 GCP SA를 가장(impersonate)할 수 있도록 바인딩.  
SA 키 파일 없이 클러스터 내부에서 자동으로 GCP 인증이 처리된다.

```bash
gcloud iam service-accounts add-iam-policy-binding \
  billing-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:cloud-sre-platform-dev.svc.id.goog[monitoring/billing-exporter]"
```

> `cloud-sre-platform-dev.svc.id.goog` 형식: `{GCP_PROJECT_ID}.svc.id.goog[{K8s_NAMESPACE}/{K8s_SA_NAME}]`

### Step 4. 검증

ArgoCD로 billing-exporter CronJob이 배포된 후 수동으로 Job을 실행해 확인한다.

```bash
# CronJob에서 Job 수동 생성
kubectl create job billing-exporter-test \
  --from=cronjob/billing-exporter \
  -n monitoring

# 로그 확인
kubectl logs -l job-name=billing-exporter-test -n monitoring --follow

# 성공 로그 예시
# [billing-exporter] BigQuery 조회 기준일: 2026-04-07
# [billing-exporter] 조회된 서비스 수: 5
# [billing-exporter] 이번 달 누적 비용: $12.3400
# [billing-exporter] Pushgateway 전송 완료 → http://pushgateway.monitoring:9091

# Pushgateway에서 메트릭 확인
kubectl port-forward svc/pushgateway 9091:9091 -n monitoring
# 브라우저에서 http://localhost:9091 접속 후 gcp_cost_daily_usd 확인
```

---

## Grafana FinOps 대시보드

대시보드 JSON: `dashboards/finops-cost.json`

**패널 구성:**

| 패널 | 타입 | 설명 |
|------|------|------|
| 이번 달 누적 비용 | Gauge | 월간 총 비용 / $300 예산 기준 |
| 예산 소진율 | Gauge | % 표시, 66% 황색 / 90% 적색 경보 |
| 어제 총 비용 | Stat | 전일 서비스 합계 |
| 서비스별 전일 비용 | Pie chart | GKE, BigQuery 등 서비스별 분포 |
| 서비스별 비용 상세 | Table | 금액 내림차순 정렬 |
| 서비스별 일별 추이 | Time series | 누적 막대 차트, 최근 7일 기본 조회 |
