terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── VPC 모듈 ──────────────────────────────────────────────────────────────────
# 네트워크 인프라를 먼저 구성 (GKE가 이 위에 올라가야 하므로)
module "vpc" {
  source = "./modules/vpc"

  project_id    = var.project_id
  vpc_name      = var.vpc_name
  region        = var.region
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
}

# ── Artifact Registry 모듈 ────────────────────────────────────────────────────
# Docker 이미지 저장소 (VPC와 독립적으로 생성 가능)
module "registry" {
  source = "./modules/registry"

  project_id    = var.project_id
  region        = var.region
  repository_id = var.repository_id
}

# ── GKE 모듈 ─────────────────────────────────────────────────────────────────
# VPC 모듈 완료 후 생성 (네트워크 정보를 받아서 사용)
module "gke" {
  source = "./modules/gke"

  project_id          = var.project_id
  region              = var.region
  cluster_name        = var.cluster_name
  environment         = var.environment
  vpc_name            = module.vpc.vpc_name
  subnet_name         = module.vpc.subnet_name
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name
  machine_type        = var.machine_type
  min_node_count      = var.min_node_count
  max_node_count      = var.max_node_count

  depends_on = [module.vpc]
}
