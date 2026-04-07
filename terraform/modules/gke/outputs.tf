output "cluster_name" {
  description = "GKE 클러스터 이름"
  value       = google_container_cluster.cluster.name
}

# kubectl 연결 시 필요 — sensitive로 표시하여 terraform output 기본 출력에서 마스킹
output "cluster_endpoint" {
  description = "GKE API 서버 엔드포인트"
  value       = google_container_cluster.cluster.endpoint
  sensitive   = true
}

# kubeconfig 생성 시 필요
output "cluster_ca_certificate" {
  description = "클러스터 CA 인증서 (base64)"
  value       = google_container_cluster.cluster.master_auth[0].cluster_ca_certificate
  sensitive   = true
}
