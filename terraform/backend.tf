terraform {
  # bootstrap.sh에서 생성한 GCS 버킷에 state 저장
  # 버킷 이름 형식: {project_id}-tfstate
  backend "gcs" {
    bucket = "cloud-sre-platform-dev-tfstate"
    prefix = "terraform/state"
  }
}
