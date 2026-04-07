# Artifact Registry 저장소 생성 — GitHub Actions에서 빌드한 Docker 이미지를 여기에 push
# GKE는 이 저장소에서 이미지를 pull하여 컨테이너를 실행
resource "google_artifact_registry_repository" "registry" {
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker 이미지 저장소 (SRE 플랫폼)"
  format        = "DOCKER"
  project       = var.project_id
}
