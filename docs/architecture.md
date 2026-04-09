# Architecture

## 개요

cloud-sre-platform은 GCP 위에서 Terraform(IaC) → GKE(컨테이너 오케스트레이션) → ArgoCD(GitOps) 계층 구조로 운영됩니다.
Observability는 Prometheus / Loki / Tempo / Grafana 스택으로 구성하고, FinOps 파이프라인과 Go Custom Exporter를 통해 비용 가시화와 운영 자동화를 구현합니다.

```
┌──────────────────────────────────────────────────────────────────┐
│                             GCP                                  │
│                                                                  │
│  Terraform ──▶ VPC (asia-northeast3) ──▶ GKE Standard Cluster   │
│                  Artifact Registry                               │
│                  BigQuery (billing export)                       │
└──────────────────────────────┬───────────────────────────────────┘
                               │ GitOps (ArgoCD)
               ┌───────────────▼──────────────────────────┐
               │           Kubernetes Cluster              │
               │                                          │
               │  sample-app (FastAPI)                    │
               │    │ /metrics (Prometheus)               │
               │    │ OTel SDK (Tempo)                    │
               │                                          │
               │  ┌─ Observability Stack ──────────────┐  │
               │  │  Prometheus ──▶ Grafana            │  │
               │  │  Alloy ──▶ Loki ──▶ Grafana        │  │
               │  │  OTel Collector ──▶ Tempo ──▶ Grafana│ │
               │  └────────────────────────────────────┘  │
               │                                          │
               │  ┌─ FinOps Pipeline ──────────────────┐  │
               │  │  BigQuery → billing-exporter CronJob│  │
               │  │  → Pushgateway → Prometheus → Grafana│ │
               │  └────────────────────────────────────┘  │
               │                                          │
               │  ┌─ Custom Exporter ──────────────────┐  │
               │  │  gke-spot-exporter (Go)             │  │
               │  │  GCP Compute API → /metrics         │  │
               │  │  → Prometheus (ServiceMonitor)      │  │
               │  └────────────────────────────────────┘  │
               └──────────────────────────────────────────┘

CI/CD: GitHub Actions → Artifact Registry push → ArgoCD sync → GKE 배포
```

---

## GCP 인프라 구성

### 리전 / 영역

| 항목 | 값 |
|------|----|
| 리전 | asia-northeast3 (서울) |
| Terraform state | GCS bucket (remote backend) |

### VPC

커스텀 서브넷 모드로 생성하며, GKE VPC-native 클러스터를 위한 세컨더리 IP 대역을 미리 할당합니다.

| 항목 | CIDR |
|------|------|
| 노드 서브넷 | 10.0.1.0/24 |
| Pod 대역 | 10.1.0.0/16 |
| Service 대역 | 10.2.0.0/20 |

방화벽 규칙:
- `allow-internal`: 노드/Pod/Service 대역 간 tcp/udp/icmp 전면 허용
- `allow-ssh`: 태그 기반(ssh-allowed) SSH 허용

### GKE Standard Cluster

| 항목 | 값 |
|------|----|
| 종류 | GKE Standard (Autopilot 아님) |
| 네트워킹 | VPC-native |
| 인증 | Workload Identity (`{project}.svc.id.goog`) |
| 기본 노드 풀 | 즉시 삭제 후 spot 노드 풀로 교체 |

**Spot 노드 풀**

| 항목 | 값 |
|------|-----|
| 머신 타입 | e2-standard-2 (2vCPU / 8GB) |
| 디스크 | 50GB pd-standard |
| Spot 인스턴스 | 활성화 (일반 대비 60~80% 저렴) |
| 오토스케일링 | min=1, max=3 |
| 야간 scale-down | GitHub Actions workflow로 node 수 조정 |
| 비용 | control plane $0.10/hr + spot node 비용 |

### Artifact Registry

GKE 클러스터와 동일 리전(asia-northeast3)에 Docker 저장소를 운영합니다.
CI(GitHub Actions)에서 이미지를 빌드·푸시하고, GKE가 Workload Identity로 pull합니다.

### BigQuery

GCP 콘솔에서 billing export를 `billing_export` 데이터셋으로 활성화합니다.
FinOps 파이프라인의 데이터 소스로 사용되며, billing-exporter가 BigQuery Job User 권한으로 조회합니다.

---

## GKE 클러스터 구성

ArgoCD가 `infra/` 디렉토리를 감지하여 아래 컴포넌트를 자동 배포합니다.

| 네임스페이스 | 컴포넌트 | 배포 방식 |
|-------------|---------|---------|
| argocd | ArgoCD | Helm |
| monitoring | kube-prometheus-stack (Prometheus + Grafana) | Helm + ArgoCD |
| monitoring | Loki | Helm + ArgoCD |
| monitoring | Alloy | Helm + ArgoCD (DaemonSet) |
| monitoring | Tempo | Helm + ArgoCD |
| monitoring | Pushgateway | Helm + ArgoCD |
| monitoring | gke-spot-exporter | Manifest + ArgoCD |
| monitoring | billing-exporter | CronJob Manifest + ArgoCD |
| default | sample-app | Manifest + ArgoCD |

---

## Observability 파이프라인

### Metrics (Prometheus)

```
sample-app /metrics
gke-spot-exporter /metrics    ──▶ Prometheus (scrape) ──▶ Grafana
kube-state-metrics
node-exporter
Pushgateway (FinOps 메트릭)
```

- ServiceMonitor 리소스로 scrape 대상 정의 (kube-prometheus-stack 연동)
- gke-spot-exporter: scrape interval 5분 (GCP API 호출 최소화)

### Logs (Loki + Alloy)

```
Pod 로그 (/var/log/pods)
K8s 이벤트                  ──▶ Alloy (DaemonSet) ──▶ Loki ──▶ Grafana
```

- Alloy: 각 노드에 DaemonSet으로 배포, `/var/log/pods` 마운트
- 수집 라벨: namespace, app, container (낮은 카디널리티 유지)
- pod명은 structured_metadata로 이동 (고카디널리티 라벨 제외)
- JSON 로그에서 trace_id/span_id 추출 → Traces 연동

### Traces (Tempo + OpenTelemetry)

```
sample-app (OTel SDK)  ──▶ Tempo ──▶ Grafana
```

- sample-app에 OpenTelemetry Python SDK 삽입
- Grafana에서 Trace → Log 연동: trace_id로 Loki 로그 조회 가능

---

## FinOps 파이프라인

```
GCP Billing
    │
    ▼ (GCP 콘솔 - 수동 1회 설정)
BigQuery (billing_export 데이터셋)
    │
    ▼ (CronJob - 매일 KST 09:00)
billing-exporter.py
  - BigQuery 조회 (Workload Identity 인증)
  - 일별/서비스별 비용 집계
    │
    ├──▶ Pushgateway ──▶ Prometheus ──▶ Grafana (FinOps 대시보드)
    │
    └──▶ cost-reporter.py ──▶ Slack (일별 비용 리포트)
                               (GitHub Actions - 매일 KST 09:00)
```

- billing-exporter: GKE CronJob, Workload Identity로 SA 키 불필요
- Grafana 대시보드: 일별/주별 비용 추이, 예산 소진율, 서비스별 분포
- cost-alerts.yaml: Prometheus Alert로 비용 임계치 초과 시 알림

---

## Go Custom Exporter (gke-spot-exporter)

kube-prometheus-stack은 Kubernetes 레이어만 관측하므로, GCP Compute API를 직접 호출하는 별도 exporter를 구현합니다.

### 수집 메트릭

| 메트릭 | 타입 | 설명 |
|--------|------|------|
| `gke_node_count` | Gauge | zone/node_pool/spot 기준 노드 수 |
| `gke_node_preemption_total` | Gauge | 최근 24시간 zone별 선점 횟수 |
| `gke_exporter_scrape_duration_seconds` | Gauge | GCP API 수집 소요 시간 |
| `gke_exporter_scrape_error` | Gauge | 수집 오류 여부 (0=정상, 1=오류) |

### 아키텍처

```
gke-spot-exporter Pod
  │ (Workload Identity - SA 키 없음)
  ▼
GCP Compute API
  - instances.list (노드 현황)
  - operations.list (선점 이벤트)
  │
  ▼ (5분 캐시 - cacheTTL)
/metrics 엔드포인트 (port 9090)
  │
  ▼ (ServiceMonitor - 5분 interval)
Prometheus ──▶ Grafana (gke-spot-dashboard)
```

- **Workload Identity**: `monitoring/gke-spot-exporter` K8s SA → `gke-spot-exporter` GCP SA 연결
- **캐시**: 5분 TTL, API 오류 시 이전 캐시로 폴백
- **배포**: ArgoCD가 `infra/argocd/monitoring/gke-exporter.yaml` 감지 → 자동 배포

---

## CI/CD 흐름

```
Git push (main branch)
    │
    ▼
GitHub Actions
  ├── sample-app CI
  │     build → Artifact Registry push
  │     → infra/manifests/sample-app/deployment.yaml 이미지 태그 업데이트
  │     → Git commit/push → ArgoCD 감지 → GKE 배포
  │
  ├── gke-spot-exporter CI
  │     build → Artifact Registry push
  │     → infra/manifests/gke-exporter/deployment.yaml 이미지 태그 업데이트
  │     → Git commit/push → ArgoCD 감지 → GKE 배포
  │
  ├── billing-exporter CI
  │     build → Artifact Registry push
  │
  └── 야간 scale-down workflow (매일 KST 23:00)
        GKE node pool max=0 설정 → 노드 비용 절감
```

모든 ArgoCD Application은 `infra/argocd/` 하위 YAML로 정의되며, Git push 즉시 ArgoCD가 감지하여 클러스터에 동기화합니다.
