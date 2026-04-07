# ── GCP 기본 설정 ─────────────────────────────────────────────────────────────
variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "region" {
  description = "GCP 리전"
  type        = string
  default     = "asia-northeast3" # 서울
}

variable "environment" {
  description = "환경 이름 (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# ── VPC 설정 ──────────────────────────────────────────────────────────────────
variable "vpc_name" {
  description = "VPC 네트워크 이름"
  type        = string
  default     = "sre-platform-vpc"
}

variable "subnet_cidr" {
  description = "노드 서브넷 CIDR"
  type        = string
  default     = "10.0.1.0/24"
}

variable "pods_cidr" {
  description = "Pod 세컨더리 CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

variable "services_cidr" {
  description = "Service 세컨더리 CIDR"
  type        = string
  default     = "10.2.0.0/20"
}

# ── Artifact Registry 설정 ────────────────────────────────────────────────────
variable "repository_id" {
  description = "Artifact Registry 저장소 ID"
  type        = string
  default     = "sre-platform"
}

# ── GKE 설정 ─────────────────────────────────────────────────────────────────
variable "cluster_name" {
  description = "GKE 클러스터 이름"
  type        = string
  default     = "sre-platform-cluster"
}

variable "machine_type" {
  description = "노드 머신 타입"
  type        = string
  default     = "e2-standard-2" # 2vCPU / 8GB
}

variable "min_node_count" {
  description = "최소 노드 수 (0으로 설정하면 야간 scale-down 시 비용 0)"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "최대 노드 수"
  type        = number
  default     = 3
}
