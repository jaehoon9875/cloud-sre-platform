# CLAUDE.md - custom-exporter/

## 역할

Go로 구현한 Prometheus Custom Exporter.
Prometheus가 기본으로 수집하지 않는 GCP 리소스 메트릭을 수집한다.

## 구현 시점

Stage 4 (마지막 단계). 전체 스택이 안정화된 후 진행.

## 기술

- Go
- `github.com/prometheus/client_golang`
- `/metrics` 엔드포인트 노출

## 수집 대상 메트릭 (예정)

- GKE node pool 현재 node 수
- GCP 서비스별 일별 비용 (billing-exporter.py와 비교 목적)
- 기타 필요 시 추가

## 상세 설계

Stage 4 진입 시 이 파일에 추가 작성
