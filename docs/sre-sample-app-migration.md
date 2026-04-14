# sre-sample-app 전환 계획

현재 `sample-app/`의 단순 FastAPI 앱을 MSA 기반의 복잡한 아키텍처 앱([sre-sample-app](https://github.com/jaehoon9875/sre-sample-app))으로 교체하기 위한 계획 문서.

> **상태**: sre-sample-app 개발 진행 중 — 앱 완성 후 이 인프라(cloud-sre-platform)를 함께 수정할 예정

---

## 배경

`cloud-sre-platform`은 GKE 기반 인프라 + Observability + FinOps 역량을 보여주기 위한 포트폴리오 프로젝트다.
그러나 현재 올라가 있는 `sample-app`은 단일 FastAPI 서비스로, 구조가 단순하여 실질적인 SRE 시나리오(Kafka consumer lag, OOM, circuit breaker 등)를 시연하기에 부족하다.

이를 해결하기 위해 별도 repo(`sre-sample-app`)에 복잡한 MSA 앱을 구현하고, 완성 후 이 인프라로 통합한다.

---

## repo 구조 방침

3개 repo 분리 구조를 그대로 유지한다. App repo / Infra repo 분리는 GitOps 표준 패턴이며, 현재 구조를 변경하지 않는다.

| repo | 역할 |
|------|------|
| `sre-sample-app` | MSA 앱 소스 코드 |
| `cloud-sre-platform` | GCP 인프라(Terraform) + Observability + GitOps |
| `observability-platform` | 온프레미스 출발점 (아카이브) |

---

## sre-sample-app 아키텍처

### 서비스 구성

기존 3개 서비스(order / inventory / notification)를 유지하고, 아래 컴포넌트를 추가/변경한다.

- **Kafka 브로커 3개**로 명시 (기존 미정)
- **OpenSearch 3노드 클러스터** 추가 (inventory-service가 이벤트 인덱싱)
- **Celery worker**를 별도 batch-pool 대상으로 명시

### 서비스 흐름

```
order-service → Kafka 발행 → PostgreSQL 저장
                    ↓
         inventory-service → 재고 차감 → OpenSearch 인덱싱
                    ↓
         notification-service → Celery 큐 → Celery worker → 알림 발송
```

### SRE 시나리오 (서비스별)

| 서비스 | 시나리오 |
|--------|----------|
| order-service | DB connection pool 고갈 |
| inventory-service | Kafka consumer lag 누적 |
| notification-service | Celery worker OOM |
| 전체 | Circuit breaker (inventory-service 다운 시 order-service 동작) |

---

## cloud-sre-platform node pool 재구성 계획

Terraform에 아래 4개 node pool을 추가/변경한다. (현재는 단일 spot-pool)

| pool | 머신 타입 | spot 여부 | 목적 |
|------|----------|-----------|------|
| system-pool | e2-small × 1 | 고정 | 시스템 pod 전용 |
| app-pool | e2-standard-2 × 0~3 | spot | FastAPI 3개, Redis, Nginx |
| data-pool | e2-standard-4 × 3 | **고정** | Kafka 3브로커, OpenSearch 3노드, PostgreSQL |
| batch-pool | e2-standard-2 × 0~N | spot | Celery worker |

**data-pool을 spot으로 하지 않는 이유**: Kafka replication, OpenSearch shard 복구 중 노드가 선점되면 데이터 유실 가능성이 있다. 이 판단은 Terraform 주석 및 ADR 문서에 명시한다.

**batch-pool을 app-pool과 분리하는 이유**: Celery worker는 CPU/메모리를 단기간 집중 사용하는 패턴으로, app-pool과 같이 두면 FastAPI 응답시간에 영향을 준다.

---

## 작업 예정 목록

### cloud-sre-platform

- [ ] `terraform/modules/gke/main.tf` — node pool 4개로 재구성
- [ ] `terraform/modules/gke/variables.tf` — pool별 변수 추가
- [ ] `terraform/environments/dev/terraform.tfvars.example` — 신규 변수 반영
- [ ] `docs/adr/` — data-pool, batch-pool 분리 결정 근거 ADR 문서 추가
- [ ] `README.md` — 아키텍처 다이어그램 및 node pool 구성 설명 업데이트

### sre-sample-app

- [ ] `README.md` — 서비스 흐름도, 기술 스택(OpenSearch 추가), node pool 배치 명시
- [ ] `docs/architecture.md` — OpenSearch 추가, Celery worker 분리 근거 기술
- [ ] `docs/PLAN.md` — Kafka 브로커 3개, OpenSearch, batch-pool 관련 태스크 추가

---

## 주의사항

- 실제 코드 구현은 아직 하지 않는다. 문서와 Terraform 구조 설계를 먼저 반영한다.
- OpenSearch는 이전 온프레미스 경험(Flink → OpenSearch 파이프라인)을 클라우드로 이전하는 맥락과 연결되므로, `architecture.md`에 그 배경을 명시한다.
- 기존 단일 spot-pool Terraform 코드는 삭제하지 않고 주석 처리 또는 별도 보존한다.
