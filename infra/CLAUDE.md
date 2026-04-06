# CLAUDE.md - infra/

## 역할

ArgoCD가 감지하는 GitOps 디렉토리.
Helm values.yaml과 ArgoCD Application 정의를 관리한다.
Git push → ArgoCD 자동 감지 → GKE 클러스터 동기화.

## 구조

```
infra/
├── argocd/          # ArgoCD Application CRD 정의
└── helm/
    ├── kube-prometheus-stack/
    ├── loki/
    ├── tempo/
    ├── alloy/
    └── (필요 시 추가)
```

## 운영 원칙

- 클러스터 직접 수정(kubectl apply) 금지, 반드시 Git을 통해 반영
- 각 Helm chart는 values.yaml (기본값) + custom-values.yaml (환경별 override) 구조
- YAML 파일 들여쓰기는 2칸을 유지한다.
- `values.yaml` 수정 시 기존 주석을 삭제하지 않는다.

## 보안 주의사항

- K8s Secret manifest에 민감 값(base64 인코딩 포함)을 직접 작성하여 Git에 올리지 않는다.
- 시크릿이 필요한 경우 Sealed Secrets 또는 External Secrets Operator를 통해 관리한다.
- Helm values 파일에 패스워드, 토큰 등을 평문으로 작성하지 않는다.
