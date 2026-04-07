output "vpc_name" {
  description = "생성된 VPC 이름"
  value       = module.vpc.vpc_name
}

# Docker push 시 사용: docker push {registry_url}/image:tag
output "registry_url" {
  description = "Artifact Registry URL"
  value       = module.registry.repository_url
}

output "cluster_name" {
  description = "GKE 클러스터 이름"
  value       = module.gke.cluster_name
}

# terraform output cluster_endpoint 으로 조회 가능
output "cluster_endpoint" {
  description = "GKE API 엔드포인트 (kubectl 연결용)"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}
