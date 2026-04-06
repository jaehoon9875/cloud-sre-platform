# cloud-sre-platform

GCP 환경에서 Terraform으로 인프라를 프로비저닝하고, Kubernetes 기반 Observability 스택을 운영하며, Python으로 FinOps와 운영 자동화를 구현한 SRE 플랫폼 프로젝트입니다.

온프레미스 환경에서 운영하던 Observability 스택([observability-platform](https://github.com/jaehoon9875/observability-platform))을 GCP 클라우드로 전환하고, 실무 SRE 관점의 비용 최적화·자동화·장애 대응 프로세스를 추가했습니다.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                        GCP                          │
│                                                     │
│  Terraform ──▶ VPC ──▶ GKE Standard Cluster        │
│                         (spot node pool)            │
│                                                     │
│                Artifact Registry                    │
│                BigQuery (billing export)            │
└──────────────────────┬──────────────────────────────┘
                       │ GitOps (ArgoCD)
          ┌────────────▼────────────────────┐
          │      Kubernetes Cluster          │
          │                                 │
          │  sample-app (FastAPI)            │
          │       │                         │
          │  Observability Stack             │
          │  Prometheus ──▶ Grafana         │
          │  Alloy ──▶ Loki ──▶ Grafana     │
          │  OTel ──▶ Tempo ──▶ Grafana     │
          │                                 │
          │  FinOps Dashboard (Grafana)      │
          │  GCP Billing ──▶ BigQuery        │
          │  ──▶ Python ──▶ Pushgateway     │
          └─────────────────────────────────┘

Python Automation
  ├── billing-exporter.py    GCP 비용 메트릭 수집
  ├── cost-reporter.py       Slack 비용 리포트
  ├── scale-scheduler.py     야간 node scale-down
  └── incident-collector.py  장애 진단 자동 수집
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Cloud | GCP (GKE Standard, Artifact Registry, BigQuery, VPC) |
| IaC | Terraform |
| GitOps | ArgoCD |
| Observability | Prometheus, Grafana, Loki, Alloy, Tempo, OpenTelemetry |
| FinOps | GCP Billing API, BigQuery, Prometheus Pushgateway |
| Automation | Python |
| Load Testing | k6 |
| Custom Exporter | Go |
| CI/CD | GitHub Actions |

---

## 주요 구현 내용

- **Terraform 모듈화**: VPC / GKE / Registry를 모듈로 분리하여 환경별 재사용 가능한 구조 설계
- **GKE Standard + spot node pool**: 비용 최적화를 위한 node 구성 및 야간 자동 scale-down
- **FinOps 파이프라인**: GCP Billing → BigQuery → Prometheus → Grafana 비용 가시화
- **GitOps**: ArgoCD로 인프라 상태를 Git과 동기화
- **운영 자동화**: Python 기반 비용 리포트, 장애 진단 스크립트

---

## 문서

| 문서 | 설명 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 전체 아키텍처 및 GCP 인프라 구성 |
| [docs/finops-guide.md](docs/finops-guide.md) | FinOps 비용 구조 및 절감 전략 |
| [docs/PLAN.md](docs/PLAN.md) | Stage별 진행 계획 및 체크리스트 |
| [docs/ISSUES.md](docs/ISSUES.md) | 진행 중 이슈 및 미해결 항목 추적 |
| [docs/adr/001-gke-standard.md](docs/adr/001-gke-standard.md) | ADR: GKE Standard 선택 이유 |
| [docs/adr/002-spot-nodepool.md](docs/adr/002-spot-nodepool.md) | ADR: Spot Node Pool 사용 |
| [docs/runbook/high-cpu.md](docs/runbook/high-cpu.md) | Runbook: High CPU 대응 |

---

## 관련 프로젝트

- [observability-platform](https://github.com/jaehoon9875/observability-platform): 온프레미스 k8s 기반 Observability 스택 구축 (이 프로젝트의 출발점)
