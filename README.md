# cloud-sre-platform

GCP 환경에서 Terraform으로 인프라를 프로비저닝하고, Kubernetes 기반 Observability 스택을 운영하며, Python으로 FinOps와 운영 자동화를 구현한 SRE 플랫폼 프로젝트입니다.

온프레미스 환경에서 운영하던 Observability 스택([observability-platform](https://github.com/jaehoon9875/observability-platform))을 GCP 클라우드로 전환하고, 실무 SRE 관점의 비용 최적화·자동화·장애 대응 프로세스를 추가했습니다.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                             GCP (asia-northeast3)                │
│                                                                  │
│  Terraform ──▶ VPC ──▶ GKE Standard Cluster (spot node pool)    │
│                         Artifact Registry                        │
│                         BigQuery (billing export)                │
└──────────────────────────────┬───────────────────────────────────┘
                               │ GitOps (ArgoCD)
               ┌───────────────▼──────────────────────────┐
               │           Kubernetes Cluster              │
               │                                          │
               │  sample-app (FastAPI)                    │
               │    ├── /metrics ──▶ Prometheus           │
               │    └── OTel SDK ──▶ Tempo                │
               │                                          │
               │  Prometheus ──▶ Grafana                  │
               │  Alloy ──▶ Loki ──▶ Grafana              │
               │  Tempo ──▶ Grafana (Trace↔Log 연동)      │
               │                                          │
               │  gke-spot-exporter (Go)                  │
               │    GCP Compute API ──▶ Prometheus        │
               │                                          │
               │  billing-exporter CronJob (Python)       │
               │    BigQuery ──▶ Pushgateway ──▶ Grafana  │
               └──────────────────────────────────────────┘

CI/CD: GitHub Actions ──▶ Artifact Registry ──▶ ArgoCD sync ──▶ GKE
Automation
  ├── cost-reporter.py       Slack 일별 비용 리포트 (KST 09:00)
  ├── incident-collector.py  GKE 장애 진단 자동 수집 → Slack
  └── cluster-scale-down.yml 야간 node scale-down (GitHub Actions)
```

ArgoCD Applications

---

## 기술 스택


| 영역              | 기술                                                     |
| --------------- | ------------------------------------------------------ |
| Cloud           | GCP (GKE Standard, Artifact Registry, BigQuery, VPC)   |
| IaC             | Terraform                                              |
| GitOps          | ArgoCD                                                 |
| Observability   | Prometheus, Grafana, Loki, Alloy, Tempo, OpenTelemetry |
| FinOps          | GCP Billing API, BigQuery, Prometheus Pushgateway      |
| Automation      | Python                                                 |
| Load Testing    | k6                                                     |
| Custom Exporter | Go                                                     |
| CI/CD           | GitHub Actions                                         |


---

## 주요 구현 내용

- **Terraform 모듈화**: VPC / GKE / Registry를 모듈로 분리하여 환경별 재사용 가능한 구조 설계
- **GKE Standard + spot node pool**: 비용 최적화를 위한 node 구성 및 야간 자동 scale-down (GitHub Actions)
- **Full-stack Observability**: Prometheus + Loki + Tempo + Grafana — Metrics / Logs / Traces 통합, Trace↔Log 상호 연동
- **FinOps 파이프라인**: GCP Billing → BigQuery → Pushgateway → Grafana 비용 가시화 + Slack 일별 리포트
- **GitOps**: ArgoCD로 모든 인프라 변경을 Git을 통해서만 반영
- **Go Custom Exporter**: GCP Compute API 기반 Spot 노드 현황·선점 이벤트 메트릭 수집 (Workload Identity, 5분 캐시)
- **운영 자동화**: Python 기반 비용 리포트, 장애 진단 자동 수집 → Slack 전송

Grafana GKE Spot Exporter Dashboard

Grafana FinOps Dashboard

Slack 비용 리포트

---

## 구축 순서

처음부터 환경을 구축하는 경우 아래 순서를 따른다.


| 단계  | 문서                                                                 | 내용                                                                                         |
| --- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| 1   | [docs/bootstrap.md](docs/bootstrap.md)                             | 로컬 도구 설치, GCP 프로젝트 초기화, Terraform SA 생성                                                    |
| 2   | [terraform/](terraform/)                                           | Terraform으로 VPC / GKE / Artifact Registry 프로비저닝                                            |
| 2-1 | [docs/github-actions-gcp-auth.md](docs/github-actions-gcp-auth.md) | GitHub Actions GCP 인증 설정 (Workload Identity Federation)                                    |
| 3   | [infra/](infra/)                                                   | ArgoCD 설치 → GitHub repo 연결 → Observability 스택 배포 (Prometheus, Grafana, Loki, Alloy, Tempo) |
| 4   | [docs/finops-guide.md](docs/finops-guide.md)                       | BigQuery billing export 활성화 → FinOps 파이프라인 배포 → Slack Webhook 설정                           |
| 5   | [custom-exporter/CLAUDE.md](custom-exporter/CLAUDE.md)             | Workload Identity 설정 → Go Exporter 빌드·배포 → Grafana 대시보드 import                             |


---

## 문서


| 문서                                                             | 설명                      |
| -------------------------------------------------------------- | ----------------------- |
| [docs/architecture.md](docs/architecture.md)                   | 전체 아키텍처 및 GCP 인프라 구성    |
| [docs/finops-guide.md](docs/finops-guide.md)                   | FinOps 비용 구조 및 절감 전략    |
| [docs/PLAN.md](docs/PLAN.md)                                   | Stage별 진행 계획 및 체크리스트    |
| [docs/ISSUES.md](docs/ISSUES.md)                               | 진행 중 이슈 및 미해결 항목 추적     |
| [docs/adr/001-gke-standard.md](docs/adr/001-gke-standard.md)   | ADR: GKE Standard 선택 이유 |
| [docs/adr/002-spot-nodepool.md](docs/adr/002-spot-nodepool.md) | ADR: Spot Node Pool 사용  |
| [docs/runbook/high-cpu.md](docs/runbook/high-cpu.md)           | Runbook: High CPU 대응    |


---

## 관련 프로젝트

- [observability-platform](https://github.com/jaehoon9875/observability-platform): 온프레미스 k8s 기반 Observability 스택 구축 (이 프로젝트의 출발점)
- [sre-sample-app](https://github.com/jaehoon9875/sre-sample-app): 이 인프라 위에서 운영될 MSA 기반 Sample App (진행 중)

> **전환 예정**: 현재 `sample-app/`의 단순 FastAPI 앱은 포트폴리오 시연 목적에 맞는 복잡한 아키텍처(Kafka + OpenSearch + Celery)를 갖춘 `sre-sample-app`으로 교체될 예정입니다.
> 전환 계획 상세 → [docs/sre-sample-app-migration.md](docs/sre-sample-app-migration.md)