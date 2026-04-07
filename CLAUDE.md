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
├── terraform/         # GCP 인프라 IaC (Terraform 모듈/환경)
├── infra/             # Helm values + ArgoCD 정의 (GitOps)
├── sample-app/        # 관측 대상 FastAPI 앱
├── automation/        # Python 운영 자동화 (FinOps, 스케줄러, 인시던트)
├── custom-exporter/   # Go 기반 Prometheus Exporter
├── dashboards/        # Grafana 대시보드 JSON
├── alerts/            # Prometheus Alert Rule YAML
└── docs/              # 설계 문서, ADR, Runbook, 진행 계획
```

각 디렉토리의 상세 구조는 해당 디렉토리의 CLAUDE.md 참고.

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

## 참고 문서

문서 목록 및 각 파일의 용도 → [docs/CLAUDE.md](docs/CLAUDE.md)

---

## 현재 진행 상태

현재 **Stage 2 진행 예정** (전체 4단계 중) — Stage 1 완료, Observability Stack 이전 단계

단계별 체크리스트 → [docs/PLAN.md](docs/PLAN.md)
진행 중 이슈 → [docs/ISSUES.md](docs/ISSUES.md)

---

## Git Conventions

- 커밋 메시지: `type: 설명` (예: `feat: GKE 모듈 구현`, `fix: terraform plan 오류 수정`)
- type 목록: `feat`, `fix`, `refactor`, `docs`, `infra`, `test`, `chore`
- 브랜치: `feature/{기능명}`, `fix/{버그명}`

---

## Important Rules

- ArgoCD로 관리되는 리소스는 `kubectl apply`나 `helm upgrade` CLI로 직접 수정하지 않는다.
  변경은 반드시 `infra/` 파일 수정 → Git push → ArgoCD sync 경로로만 반영한다.
- GCP 크레딧($300 free trial)을 고려하여 리소스 생성·변경 시 비용 영향을 먼저 검토한다.
- 환경변수는 하드코딩하지 않고 K8s ConfigMap/Secret 또는 Terraform variables로 관리한다.
- 주요 개발 내용 중 문서화가 필요한 부분은 [docs/CLAUDE.md](docs/CLAUDE.md)를 확인하고 docs/ 하위에 문서를 추가한다.
- 스크립트·코드 작성 시 기능 단위마다 한글 주석을 작성한다.
- GCP SA 키, API 키, 토큰 등 민감 정보는 코드나 설정 파일에 하드코딩하지 않는다. `.env`, `*.json` 키 파일, `terraform.tfvars` 등 시크릿을 담는 파일은 반드시 `.gitignore`에 포함되어 있는지 확인한다.
- GitHub에 push 전, 민감 정보가 포함된 파일이 스테이징되어 있지 않은지 반드시 확인한다.
