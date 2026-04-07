# VPC 네트워크 생성 (auto_create_subnetworks=false: 커스텀 서브넷 직접 관리)
resource "google_compute_network" "vpc" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
  project                 = var.project_id
}

# 서브넷 생성 — GKE 노드가 올라갈 네트워크 구역
# secondary_ip_range: GKE Pod/Service 주소를 위한 추가 IP 대역 (VPC-native 클러스터 필수)
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.vpc_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id

  # Pod IP 대역 (컨테이너 하나당 IP 할당)
  secondary_ip_range {
    range_name    = "${var.vpc_name}-pods"
    ip_cidr_range = var.pods_cidr
  }

  # Service IP 대역 (ClusterIP, LoadBalancer 등)
  secondary_ip_range {
    range_name    = "${var.vpc_name}-services"
    ip_cidr_range = var.services_cidr
  }
}

# 내부 트래픽 허용 방화벽 규칙 (노드 ↔ 노드, Pod ↔ Pod 통신)
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.vpc_name}-allow-internal"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow { protocol = "tcp" }
  allow { protocol = "udp" }
  allow { protocol = "icmp" }

  source_ranges = [var.subnet_cidr, var.pods_cidr, var.services_cidr]
}

# SSH 접근 허용 방화벽 규칙 (태그 기반 — 필요한 노드에만 적용)
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.vpc_name}-allow-ssh"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-allowed"]
}
