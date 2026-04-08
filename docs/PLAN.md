# PLAN.md

## Stage 진행 현황

| Stage | 내용 | 상태 |
|-------|------|------|
| Stage 1 | GCP 인프라 프로비저닝 (Terraform) | ✅ 완료 |
| Stage 2 | Observability Stack 이전 (ArgoCD + Helm) | ✅ 완료 |
| Stage 3 | FinOps + Python 자동화 | ✅ 완료 |
| Stage 4 | Go Custom Exporter | ✅ 완료 |

---

## Stage 1 - GCP 인프라 프로비저닝 (Terraform)

**목표**: Terraform으로 GCP 인프라 전체를 코드로 관리

### 체크리스트

**✅ GCP 초기 설정**
- [x] GCP 프로젝트 생성
- [x] 필요한 API 활성화 (GKE, Artifact Registry, BigQuery, Billing)
- [x] Terraform 서비스 계정 생성 및 권한 설정
- [x] Terraform state 저장용 GCS bucket 생성

**✅ Terraform 구성**
- [x] `modules/vpc`: VPC, Subnet, Firewall 구성
- [x] `modules/gke`: GKE Standard Cluster + spot node pool
- [x] `modules/registry`: Artifact Registry 구성
- [x] `environments/dev`: dev 환경 tfvars 작성
- [x] Terraform plan / apply 검증

**FinOps 기반 설정**
- [x] GCP Budget Alert 설정 ($250 임계치)
- [x] BigQuery billing export 활성화 (GCP 콘솔에서 수동 설정 — [finops-guide.md](finops-guide.md) 참고)
- [x] `make cluster-down` / `make cluster-up` Makefile 작성
- [x] GitHub Actions: 야간 자동 scale-down workflow

---

## Stage 2 - Observability Stack 이전 (ArgoCD + Helm)

**목표**: 기존 observability-platform 스택을 GKE 위로 이전

### 체크리스트

**✅ GitOps 환경**
- [x] ArgoCD 설치 및 초기 설정
- [x] GitHub repo 연결 (infra/ 디렉토리 감지)

**✅ Observability 스택 배포**
- [x] kube-prometheus-stack (Prometheus + Grafana)
- [x] Loki + Alloy
- [x] Tempo
- [x] ArgoCD Application 정의 작성

**✅ Sample App**
- [x] FastAPI sample-app 개발 (Python)
  - [x] `/health`, `/orders` 엔드포인트
  - [x] Prometheus 메트릭 노출 (`/metrics`)
  - [x] OpenTelemetry 트레이싱 연동
  - [x] 의도적 에러/지연 엔드포인트 (장애 시뮬레이션)
- [x] Dockerfile 작성
- [x] GitHub Actions CI (build → Artifact Registry push)
- [x] ArgoCD로 GKE 배포 연동

**✅ 검증**
- [x] Grafana에서 메트릭 확인
- [x] 분산 트레이싱 (Trace → Log 연동) 확인
- [x] k6 부하 테스트 실행 확인

---

## Stage 3 - FinOps + Python 자동화

**목표**: 비용 가시화 + 운영 자동화 구현

### 체크리스트

**FinOps 파이프라인**
- [x] `billing-exporter.py`: BigQuery → Prometheus Pushgateway
- [x] Grafana FinOps 대시보드 (`dashboards/finops-cost.json`)
  - [x] 일별/주별 비용 추이
  - [x] 예산 소진율
  - [x] 서비스별 비용 분포
- [x] `cost-alerts.yaml`: 비용 임계치 Prometheus Alert

**비용 리포트 자동화**
- [x] `cost-reporter.py`: 일별 비용 Slack 리포트 (gross/net 분리 표시)
- [x] Slack Incoming Webhook 설정
- [x] GitHub Actions scheduled workflow (매일 KST 09:00)

**운영 자동화**
- [x] `scale-scheduler.py`: GitHub Actions workflow로 대체 (`cluster-scale-down.yml`) — scale-to-0 구조적 한계로 Python 스크립트 스킵 (docs/ISSUES.md #2 참고)
- [x] `incident-collector.py`: GKE 장애 진단 자동 수집 → Slack 전송 (GitHub Actions workflow_dispatch, 동작 확인 완료)

**문서**
- [x] `docs/finops-guide.md` 작성

---

## Stage 4 - Go Custom Exporter

**목표**: Go로 Prometheus Exporter 구현

### 체크리스트

- [x] exporter 설계 — GKE Spot 노드 현황 + 선점 이벤트 + 절감액 추정
- [x] Go 프로젝트 초기화 (`go mod init`)
- [x] `prometheus/client_golang` 연동 (Collector 인터페이스 구현)
- [x] `/metrics` 엔드포인트 구현 + 5분 캐시 (GCP API 비용 절감)
- [x] Dockerfile 작성 (multi-stage, distroless)
- [x] GKE 배포 및 Grafana 연동 (Workload Identity + ArgoCD + ServiceMonitor)
- [x] `custom-exporter/CLAUDE.md` 작성
- [x] CI에서 deployment.yaml 이미지 태그 자동 업데이트 → ArgoCD 자동 배포

---

## 마무리 작업

- [ ] `docs/architecture.md` 업데이트 — GKE Exporter 추가된 아키텍처 반영
- [ ] `README.md` 업데이트 — 전체 스택 완성 기준으로 정리 (구축 순서, 기술 스택 등)
- [ ] Grafana 대시보드 스크린샷 촬영 — 실제 메트릭이 찍힌 화면을 README에 첨부

---

## 이슈 및 메모

진행 중 발생한 이슈 및 미해결 항목은 **[ISSUES.md](ISSUES.md)** 에서 관리합니다.

| # | 단계 | 요약 | 상태 |
|---|------|------|------|
| [#1](ISSUES.md#1-상세) | Stage 1 | `gcloud billing budgets create` CLI INVALID_ARGUMENT 오류 | 🟢 우회 완료 |
| [#2](ISSUES.md#2-상세) | Stage 1 | GKE node scale-down이 0으로 되지 않음 | 🟡 검증 대기 중 |
