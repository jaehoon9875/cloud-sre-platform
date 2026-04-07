variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "region" {
  description = "GCP 리전"
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry 저장소 ID (URL의 일부가 됨)"
  type        = string
}
