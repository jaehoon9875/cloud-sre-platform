# Docker push/pull 시 사용하는 전체 URL
# 예: asia-northeast3-docker.pkg.dev/my-project/sre-platform
output "repository_url" {
  description = "Artifact Registry 저장소 URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_id}"
}

output "repository_id" {
  description = "저장소 ID"
  value       = google_artifact_registry_repository.registry.repository_id
}
