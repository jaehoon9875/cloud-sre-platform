# CLAUDE.md - custom-exporter/

## 역할

Go로 구현한 Prometheus Custom Exporter.
GKE Spot 노드 현황과 선점(preemption) 이벤트를 수집하여 FinOps 및 안정성 대시보드에 제공한다.

## 왜 이 Exporter가 필요한가

kube-prometheus-stack(kube-state-metrics + node_exporter)은 Kubernetes 레이어만 관측한다.
GCP 레이어 정보 — 노드가 spot인지, 선점이 발생했는지, zone 분포 — 는 Compute API를 직접 호출해야 알 수 있다.

## 기술

- Go 1.22
- `github.com/prometheus/client_golang` — Prometheus Collector 인터페이스 구현
- `google.golang.org/api/compute/v1` — GCP Compute API 클라이언트
- GKE Workload Identity — SA 키 없이 GCP 인증

## 수집 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `gke_node_count` | Gauge | zone/node_pool/spot 기준 노드 수 |
| `gke_node_preemption_total` | Gauge | 최근 24시간 zone별 선점 횟수 |
| `gke_exporter_scrape_duration_seconds` | Gauge | GCP API 수집 소요 시간 |
| `gke_exporter_scrape_error` | Gauge | 수집 오류 여부 (0=정상, 1=오류) |

## 캐시 설계

GCP Compute API는 무료지만 scrape 주기(5분)마다 호출을 최소화한다.
- `cacheTTL = 5m` — 캐시 유효 시간
- API 오류 시 이전 캐시 데이터로 폴백 (일시적 장애 대응)
- ServiceMonitor scrape interval도 5분으로 맞춤

## 파일 구조

```
custom-exporter/
├── main.go        # HTTP 서버, 메트릭 등록, 엔드포인트
├── collector.go   # GKECollector 구현 (Describe/Collect + GCP API)
├── go.mod
├── go.sum
└── Dockerfile     # multi-stage build (golang:1.22-alpine → distroless)
```

## 배포 구조

```
infra/manifests/gke-exporter/
├── serviceaccount.yaml   # Workload Identity 어노테이션 포함
├── deployment.yaml       # GCP_PROJECT_ID, GKE_CLUSTER_NAME 환경변수
├── service.yaml
└── servicemonitor.yaml   # Prometheus scrape 설정 (5m interval)

infra/argocd/monitoring/gke-exporter.yaml  # ArgoCD Application
dashboards/gke-spot-dashboard.json         # Grafana 대시보드
```

## Workload Identity 사전 설정 (1회)

```bash
# 1. GCP SA 생성
gcloud iam service-accounts create gke-spot-exporter \
  --project=cloud-sre-platform-dev

# 2. Compute Viewer 권한 부여
gcloud projects add-iam-policy-binding cloud-sre-platform-dev \
  --member="serviceAccount:gke-spot-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com" \
  --role="roles/compute.viewer"

# 3. Workload Identity 바인딩
gcloud iam service-accounts add-iam-policy-binding \
  gke-spot-exporter@cloud-sre-platform-dev.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:cloud-sre-platform-dev.svc.id.goog[monitoring/gke-spot-exporter]"
```

## 배포 순서

1. 위 Workload Identity 설정 완료
2. `go mod tidy` 실행 후 `go.sum` 커밋
3. Git push → GitHub Actions CI (빌드 + Artifact Registry push)
4. ArgoCD가 `infra/argocd/monitoring/gke-exporter.yaml` 감지 → 자동 배포
5. Grafana에서 `dashboards/gke-spot-dashboard.json` import

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `GCP_PROJECT_ID` | `cloud-sre-platform-dev` | GCP 프로젝트 ID |
| `GKE_CLUSTER_NAME` | `sre-platform-cluster` | GKE 클러스터 이름 |
| `PORT` | `9090` | HTTP 서버 포트 |
