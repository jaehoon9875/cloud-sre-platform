# GKE 모듈에서 network 파라미터로 사용
output "vpc_name" {
  description = "VPC 네트워크 이름"
  value       = google_compute_network.vpc.name
}

# GKE 모듈에서 subnetwork 파라미터로 사용
output "subnet_name" {
  description = "서브넷 이름"
  value       = google_compute_subnetwork.subnet.name
}

# GKE ip_allocation_policy 설정에 사용
output "pods_range_name" {
  description = "Pod IP 세컨더리 범위 이름"
  value       = "${var.vpc_name}-pods"
}

output "services_range_name" {
  description = "Service IP 세컨더리 범위 이름"
  value       = "${var.vpc_name}-services"
}
