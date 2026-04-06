# ADR 001 - GKE Standard 선택

## 상태

채택

## 결정

GKE Autopilot 대신 GKE Standard를 사용한다.

## 이유

- node pool, spot instance, auto-scaler를 직접 제어할 수 있어 비용 최적화 여지가 크다
- AWS EKS, AKS에도 동일하게 적용되는 범용 지식 (Autopilot은 GCP 전용 편의 기능)
- node pool scale-down 자동화, spot instance 활용 등 실무 경험을 직접 쌓을 수 있다
- 면접에서 설명할 수 있는 의사결정 포인트가 많다

## 트레이드오프

- control plane 비용 $0.10/hr 고정 발생 (Autopilot도 동일)
- node 관리를 직접 해야 함 → 이 자체가 학습 목표
