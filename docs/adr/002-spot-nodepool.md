# ADR 002 - Spot Node Pool 사용

## 상태

채택

## 결정

GKE node pool을 spot(preemptible) instance로 구성한다.

## 이유

- 일반 node 대비 60~80% 비용 절감
- dev/학습 환경에서 spot으로 인한 node 중단은 허용 가능
- spot 환경에서 workload 안정성을 확보하는 방법(PodDisruptionBudget 등)을 직접 경험할 수 있다

## 트레이드오프

- GCP가 리소스 부족 시 node를 회수할 수 있음 (최대 24시간)
- 중요 워크로드에는 적합하지 않음 → 학습/dev 환경에서 적절한 선택

## 대응 방안

- Kubernetes가 node 중단 시 자동으로 다른 node에 pod를 재스케줄링
- 상태가 없는(stateless) 워크로드 위주로 구성
