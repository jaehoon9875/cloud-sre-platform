# PLAN.md

## Stage 진행 현황

| Stage | 내용 | 상태 |
|-------|------|------|
| Stage 1 | GCP 인프라 프로비저닝 (Terraform) | 🔲 진행 전 |
| Stage 2 | Observability Stack 이전 (ArgoCD + Helm) | 🔲 진행 전 |
| Stage 3 | FinOps + Python 자동화 | 🔲 진행 전 |
| Stage 4 | Go Custom Exporter | 🔲 진행 전 |

---

## Stage 1 - GCP 인프라 프로비저닝 (Terraform)

**목표**: Terraform으로 GCP 인프라 전체를 코드로 관리

### 체크리스트

**GCP 초기 설정**
- [ ] GCP 프로젝트 생성
- [ ] 필요한 API 활성화 (GKE, Artifact Registry, BigQuery, Billing)
- [ ] Terraform 서비스 계정 생성 및 권한 설정
- [ ] Terraform state 저장용 GCS bucket 생성

**Terraform 구성**
- [ ] `modules/vpc`: VPC, Subnet, Firewall 구성
- [ ] `modules/gke`: GKE Standard Cluster + spot node pool
- [ ] `modules/registry`: Artifact Registry 구성
- [ ] `environments/dev`: dev 환경 tfvars 작성
- [ ] Terraform plan / apply 검증

**FinOps 기반 설정**
- [ ] GCP Budget Alert 설정 ($250 임계치)
- [ ] BigQuery billing export 활성화
- [ ] `make cluster-down` / `make cluster-up` Makefile 작성
- [ ] GitHub Actions: 야간 자동 scale-down workflow

---

## Stage 2 - Observability Stack 이전 (ArgoCD + Helm)

**목표**: 기존 observability-platform 스택을 GKE 위로 이전

### 체크리스트

**GitOps 환경**
- [ ] ArgoCD 설치 및 초기 설정
- [ ] GitHub repo 연결 (infra/ 디렉토리 감지)

**Observability 스택 배포**
- [ ] kube-prometheus-stack (Prometheus + Grafana)
- [ ] Loki + Alloy
- [ ] Tempo
- [ ] ArgoCD Application 정의 작성

**Sample App**
- [ ] FastAPI sample-app 개발 (Python)
  - [ ] `/health`, `/orders` 엔드포인트
  - [ ] Prometheus 메트릭 노출 (`/metrics`)
  - [ ] OpenTelemetry 트레이싱 연동
  - [ ] 의도적 에러/지연 엔드포인트 (장애 시뮬레이션)
- [ ] Dockerfile 작성
- [ ] GitHub Actions CI (build → Artifact Registry push)
- [ ] ArgoCD로 GKE 배포 연동

**검증**
- [ ] Grafana에서 메트릭 확인
- [ ] 분산 트레이싱 (Trace → Log 연동) 확인
- [ ] k6 부하 테스트 실행 확인

---

## Stage 3 - FinOps + Python 자동화

**목표**: 비용 가시화 + 운영 자동화 구현

### 체크리스트

**FinOps 파이프라인**
- [ ] `billing-exporter.py`: BigQuery → Prometheus Pushgateway
- [ ] Grafana FinOps 대시보드 (`dashboards/finops-cost.json`)
  - [ ] 일별/주별 비용 추이
  - [ ] 네임스페이스별 비용 분포
  - [ ] 예산 소진율
- [ ] `cost-alerts.yaml`: 비용 임계치 Prometheus Alert

**비용 리포트 자동화**
- [ ] `cost-reporter.py`: 일별 비용 Slack 리포트
- [ ] Slack Incoming Webhook 설정
- [ ] GitHub Actions scheduled workflow (매일 오전 9시)

**운영 자동화**
- [ ] `scale-scheduler.py`: 야간/주말 node scale-down
- [ ] `incident-collector.py`: GKE 장애 진단 자동 수집

**문서**
- [ ] `docs/finops-guide.md` 작성

---

## Stage 4 - Go Custom Exporter

**목표**: Go로 Prometheus Exporter 구현

### 체크리스트

- [ ] exporter 설계 (수집 메트릭 정의)
- [ ] Go 프로젝트 초기화 (`go mod init`)
- [ ] `prometheus/client_golang` 연동
- [ ] `/metrics` 엔드포인트 구현
- [ ] Dockerfile 작성
- [ ] GKE 배포 및 Grafana 연동
- [ ] `custom-exporter/CLAUDE.md` 작성

---

## 이슈 및 메모

> 진행하면서 발생한 이슈, 결정 사항, 참고할 내용을 여기에 기록
