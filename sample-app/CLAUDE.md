# CLAUDE.md - sample-app/

## 역할

Observability 스택의 관측 대상이 되는 경량 FastAPI 애플리케이션.
메트릭/로그/트레이싱을 모두 노출하여 전체 Observability 파이프라인을 검증한다.

## 설계 방향

- 단일 서비스 (MSA 구성 없음, 비용 최소화)
- Python FastAPI
- 메모리 100MB 이하 목표

## 엔드포인트

| 경로 | 설명 |
|------|------|
| `GET /health` | 헬스체크 |
| `GET /orders` | 주문 목록 (정상 응답) |
| `POST /orders` | 주문 생성 |
| `GET /slow` | 의도적 지연 (지연 시뮬레이션) |
| `GET /error` | 의도적 500 에러 (장애 시뮬레이션) |
| `GET /metrics` | Prometheus 메트릭 노출 |

## Observability 연동

- **Metrics**: `prometheus-fastapi-instrumentator` 라이브러리로 자동 수집
- **Traces**: OpenTelemetry SDK → Tempo
- **Logs**: structlog (JSON 형식) → Alloy → Loki
