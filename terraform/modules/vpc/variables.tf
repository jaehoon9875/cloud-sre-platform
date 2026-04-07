variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "vpc_name" {
  description = "VPC 네트워크 이름"
  type        = string
}

variable "region" {
  description = "GCP 리전"
  type        = string
}

# 노드(서버)가 배치될 서브넷 CIDR
variable "subnet_cidr" {
  description = "서브넷 CIDR (GKE 노드용)"
  type        = string
  default     = "10.0.1.0/24"
}

# Pod: 컨테이너 하나당 IP를 부여하므로 넓은 대역 필요
variable "pods_cidr" {
  description = "GKE Pod 세컨더리 CIDR"
  type        = string
  default     = "10.1.0.0/16"
}

# Service: ClusterIP, LoadBalancer 등에 쓰이는 가상 IP 대역
variable "services_cidr" {
  description = "GKE Service 세컨더리 CIDR"
  type        = string
  default     = "10.2.0.0/20"
}
