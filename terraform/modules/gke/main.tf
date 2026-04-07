# GKE Standard 클러스터 생성
resource "google_container_cluster" "cluster" {
  name     = var.cluster_name
  location = var.region
  project  = var.project_id

  # 기본 노드 풀 즉시 제거 — 아래에서 별도 spot 노드 풀로 교체
  remove_default_node_pool = true
  initial_node_count       = 1

  # VPC-native 모드: Pod/Service에 VPC IP를 직접 할당 (GKE 권장 방식)
  networking_mode = "VPC_NATIVE"
  network         = var.vpc_name
  subnetwork      = var.subnet_name

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  # Workload Identity: SA 키 JSON 없이 GCP API에 안전하게 접근
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # dev 환경에서는 삭제 방지 비활성화 (terraform destroy 가능하게)
  deletion_protection = false
}

# Spot 노드 풀 — 일반 VM 대비 60~80% 저렴, 선점 가능성 있음
resource "google_container_node_pool" "spot_nodes" {
  name     = "${var.cluster_name}-spot-pool"
  cluster  = google_container_cluster.cluster.name
  location = var.region
  project  = var.project_id

  # 오토스케일링: min=0 설정으로 야간/주말 scale-down 시 노드 비용 0원 가능
  autoscaling {
    min_node_count = var.min_node_count
    max_node_count = var.max_node_count
  }

  node_config {
    machine_type = var.machine_type
    disk_size_gb = 50
    disk_type    = "pd-standard"

    # Spot 인스턴스 활성화
    spot = true

    # 최소 권한 원칙: cloud-platform 범위로 제한
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    # Workload Identity 연동을 위한 노드 메타데이터 설정
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      env  = var.environment
      pool = "spot"
    }
  }
}
