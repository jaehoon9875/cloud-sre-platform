variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "region" {
  description = "GCP 리전"
  type        = string
}

variable "cluster_name" {
  description = "GKE 클러스터 이름"
  type        = string
}

variable "environment" {
  description = "환경 이름 (dev, staging, prod)"
  type        = string
}

# VPC 모듈의 출력값을 받아 클러스터를 해당 네트워크 위에 배치
variable "vpc_name" {
  description = "VPC 네트워크 이름"
  type        = string
}

variable "subnet_name" {
  description = "서브넷 이름"
  type        = string
}

variable "pods_range_name" {
  description = "Pod IP 세컨더리 범위 이름 (VPC 모듈 output)"
  type        = string
}

variable "services_range_name" {
  description = "Service IP 세컨더리 범위 이름 (VPC 모듈 output)"
  type        = string
}

variable "machine_type" {
  description = "노드 머신 타입"
  type        = string
  default     = "e2-standard-2" # 2vCPU / 8GB — 비용 대비 성능 균형
}

# 0으로 설정하면 야간 scale-down 시 노드 비용 완전 절감
variable "min_node_count" {
  description = "최소 노드 수 (0: 야간 scale-down 가능)"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "최대 노드 수"
  type        = number
  default     = 3
}
