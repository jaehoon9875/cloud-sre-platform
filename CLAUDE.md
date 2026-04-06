# CLAUDE.md

이 파일은 AI 어시스턴트가 프로젝트 전체 문맥을 파악하기 위한 파일입니다.

---

## 프로젝트 개요

**cloud-sre-platform**
GCP 환경에서 Terraform으로 인프라를 구성하고, GKE 위에 Observability 스택을 운영하며, Python으로 FinOps와 운영 자동화를 구현하는 SRE 플랫폼 프로젝트.

**배경**
- 기존 프로젝트(observability-platform)는 홈서버 기반 온프레미스 k8s 환경
- 이 프로젝트는 동일한 스택을 GCP로 전환하고, FinOps/자동화를 추가

---

## 디렉토리 구조

```
cloud-sre-platform/
├── README.md                  # 외부 공개용 소개
├── CLAUDE.md                  # 이 파일 (root AI 문맥)
├── PLAN.md                    # Stage별 진행 계획
│
├── terraform/                 # GCP 인프라 IaC
│   ├── CLAUDE.md
│   └── modules/ environments/
│
├── infra/                     # Helm values + ArgoCD 정의 (GitOps)
│   ├── CLAUDE.md
│   ├── argocd/
│   └── helm/
│
├── sample-app/                # 관측 대상 FastAPI 앱 (단일 서비스)
│   └── CLAUDE.md
│
├── automation/                # Python 운영 자동화
│   ├── CLAUDE.md
│   ├── finops/
│   ├── scheduler/
│   └── incident/
│
├── custom-exporter/           # Go 기반 Prometheus Exporter
│   └── CLAUDE.md
│
├── dashboards/                # Grafana 대시보드 JSON
├── alerts/                    # Prometheus Alert Rule YAML
│
└── docs/                      # 설계 문서 (사람/AI 모두 참고)
    ├── architecture.md
    ├── finops-guide.md
    ├── adr/
    └── runbook/
```

---

## 핵심 설계 원칙

1. **FinOps 우선**: 모든 리소스 설계 시 비용 영향을 고려한다
2. **GitOps**: 인프라 변경은 Git을 통해서만 반영한다 (ArgoCD)
3. **자동화**: 반복 운영 작업은 Python 스크립트로 자동화한다
4. **모듈화**: Terraform은 모듈 단위로 분리하여 재사용 가능하게 한다

---

## 기술 스택 요약

| 영역 | 기술 | 비고 |
|------|------|------|
| Cloud | GCP | free trial ($300) |
| IaC | Terraform | GCP provider |
| Container | GKE Standard | spot node pool |
| GitOps | ArgoCD | infra/ 디렉토리 감지 |
| Observability | Prometheus, Grafana, Loki, Tempo, Alloy | Helm 배포 |
| FinOps | BigQuery + Python + Pushgateway | billing export 활용 |
| Automation | Python 3.11+ | |
| Sample App | FastAPI (Python) | 단일 경량 서비스 |
| Custom Exporter | Go | Stage 4 (마지막) |
| CI/CD | GitHub Actions | |
| Load Test | k6 | |

---

## 환경 정보

- **Cloud**: GCP (free trial, $300 크레딧, 유효기간 확인 필요)
- **Cluster**: GKE Standard, 싱글 클러스터, dev 환경
- **Node**: spot node pool (비용 절감), 야간 scale-down 자동화
- **Region**: asia-northeast3 (서울)

---

## 비용 관리 전략

- GCP Budget Alert: $250 도달 시 Slack 알림
- 야간/주말: node pool을 0으로 scale-down (scale-scheduler.py)
- 수동: `make cluster-down` / `make cluster-up`
- control plane 비용: $0.10/hr (월 약 $72) → 항상 발생
- spot node 1~2개: 월 약 $20~30 → scale-down으로 절감

---

## 진행 상태

PLAN.md 참고
