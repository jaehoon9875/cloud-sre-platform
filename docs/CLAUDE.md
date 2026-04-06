# docs/CLAUDE.md

이 디렉토리는 프로젝트의 설계 문서, 의사결정 기록, 운영 가이드, 진행 계획을 관리합니다.

---

## 문서 구조

| 파일/디렉토리 | 용도 |
|---------------|------|
| [PLAN.md](PLAN.md) | Stage별 진행 계획 및 체크리스트. 현재 진행 단계 파악 시 참조 |
| [ISSUES.md](ISSUES.md) | 진행 중 이슈, 미해결 항목, 보류 결정 사항 추적 |
| [bootstrap.md](bootstrap.md) | GCP 초기 환경 설정 절차. `scripts/bootstrap.sh` 실행 전 반드시 확인 |
| [architecture.md](architecture.md) | 전체 아키텍처 설명, GCP 인프라 구성, Observability 파이프라인 흐름 |
| [finops-guide.md](finops-guide.md) | 비용 구조, 절감 전략, Grafana FinOps 대시보드 설명 |
| [adr/](adr/) | Architecture Decision Records — 주요 기술 선택의 배경과 트레이드오프 |
| [runbook/](runbook/) | 장애 유형별 대응 절차 |

---

## ADR 목록

| 파일 | 결정 내용 |
|------|-----------|
| [adr/001-gke-standard.md](adr/001-gke-standard.md) | GKE Autopilot 대신 GKE Standard 선택 |
| [adr/002-spot-nodepool.md](adr/002-spot-nodepool.md) | node pool을 spot(preemptible) instance로 구성 |

---

## Runbook 목록

| 파일 | 대응 시나리오 |
|------|---------------|
| [runbook/high-cpu.md](runbook/high-cpu.md) | Pod CPU throttling 및 응답 지연 대응 |

---

## 문서 작성 규칙

- 진행하면서 채워야 할 항목은 `<!-- TODO: ... -->` 주석으로 표시한다.
- ADR은 결정이 내려진 시점에 작성하며, 번호를 순차적으로 부여한다 (`003-...`).
- Runbook은 실제 장애를 경험한 후 추가하거나 보완한다.
- ISSUES.md의 이슈가 해결되면 해당 항목에 해결 날짜와 방법을 기록한 뒤 닫힌 이슈 섹션으로 이동한다.
