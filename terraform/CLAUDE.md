# CLAUDE.md - terraform/

## 역할

GCP 인프라 전체를 Terraform으로 코드화하는 디렉토리.
모든 GCP 리소스는 이 디렉토리를 통해 생성/수정/삭제한다.

## 구조

```
terraform/
├── modules/
│   ├── vpc/         # VPC, Subnet, Firewall
│   ├── gke/         # GKE Standard Cluster + node pool
│   └── registry/    # Artifact Registry
├── environments/
│   └── dev/         # dev 환경 변수 (terraform.tfvars)
├── main.tf
├── variables.tf
└── outputs.tf
```

## 설계 원칙

- 모듈 단위로 분리하여 재사용 가능하게 구성
- Terraform state는 GCS backend에 저장
- 민감한 값(credentials 등)은 tfvars에만 존재하며 .gitignore 처리
- 리소스 변경 시 반드시 `terraform plan` 결과를 확인한 후 `apply`한다.

## GKE 구성 방향

- GKE Standard (Autopilot 아님)
- spot node pool: 비용 절감 목적
- node 수 조정으로 야간 비용 절감 (min=0 설정)
- region: asia-northeast3 (서울)

## 비용 관련

- control plane: $0.10/hr 고정
- spot node: 일반 대비 60~80% 저렴
- node pool min=0 설정으로 야간 scale-down 가능
