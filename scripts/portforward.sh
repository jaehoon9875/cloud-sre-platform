#!/usr/bin/env bash
# scripts/portforward.sh
# GKE 클러스터 내부 운영 도구 UI를 로컬에서 접근하기 위한 port-forward 스크립트
# 사용법: ./scripts/portforward.sh [grafana|prometheus|alertmanager|argocd|all|stop]
#
#   grafana      → http://localhost:3000
#   prometheus   → http://localhost:9090
#   alertmanager → http://localhost:9093
#   argocd       → http://localhost:8080

set -euo pipefail

PID_FILE="/tmp/portforward_pids.txt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${RESET} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }

# ────────────────────────────────────────────
# 서비스 속성 반환 헬퍼 (연관 배열 대신 case 사용)
# ────────────────────────────────────────────
get_ns() {
  case "$1" in
    grafana)      echo "monitoring" ;;
    prometheus)   echo "monitoring" ;;
    alertmanager) echo "monitoring" ;;
    argocd)       echo "argocd" ;;
  esac
}

get_svc() {
  case "$1" in
    grafana)      echo "svc/my-kube-prometheus-stack-grafana" ;;
    prometheus)   echo "svc/my-kube-prometheus-stack-prometheus" ;;
    alertmanager) echo "svc/my-kube-prometheus-stack-alertmanager" ;;
    argocd)       echo "svc/argocd-server" ;;
  esac
}

get_port() {
  case "$1" in
    grafana)      echo "3000:80" ;;
    prometheus)   echo "9090:9090" ;;
    alertmanager) echo "9093:9093" ;;
    argocd)       echo "8080:80" ;;
  esac
}

get_url() {
  case "$1" in
    grafana)      echo "http://localhost:3000" ;;
    prometheus)   echo "http://localhost:9090" ;;
    alertmanager) echo "http://localhost:9093" ;;
    argocd)       echo "http://localhost:8080" ;;
  esac
}

# ────────────────────────────────────────────
# 단일 서비스 port-forward (백그라운드 실행)
# ────────────────────────────────────────────
start_portforward() {
  local key="$1"
  local ns; ns=$(get_ns "$key")
  local svc; svc=$(get_svc "$key")
  local port; port=$(get_port "$key")
  local url; url=$(get_url "$key")
  local local_port="${port%%:*}"

  # 이미 해당 로컬 포트를 사용 중인지 확인
  if lsof -ti :"$local_port" &>/dev/null; then
    log_warn "$key: 포트 $local_port 이미 사용 중 — 건너뜁니다"
    return
  fi

  log_info "$key 포트포워드 시작 ($url)"
  kubectl port-forward "$svc" -n "$ns" "$port" &>/dev/null &
  echo $! >> "$PID_FILE"
}

# ────────────────────────────────────────────
# 실행 중인 port-forward 전체 종료
# ────────────────────────────────────────────
stop_all() {
  if [[ -f "$PID_FILE" ]]; then
    log_info "포트포워드 프로세스 종료 중..."
    while read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  # PID 파일에 없는 잔여 프로세스도 정리
  pkill -f "kubectl port-forward" 2>/dev/null || true
  log_info "포트포워드 종료 완료"
}

# ────────────────────────────────────────────
# 접속 URL 출력
# ────────────────────────────────────────────
print_urls() {
  echo ""
  echo "────────────────────────────────────"
  echo " 접속 가능한 서비스 URL"
  echo "────────────────────────────────────"
  for key in "$@"; do
    printf " %-15s ${CYAN}%s${RESET}\n" "$key" "$(get_url "$key")"
  done
  echo "────────────────────────────────────"
  echo " 종료: Ctrl+C  |  다른 터미널: make pf-stop"
  echo ""
}

# ────────────────────────────────────────────
# Ctrl+C 트랩 — 종료 시 백그라운드 프로세스 정리
# ────────────────────────────────────────────
cleanup() {
  echo ""
  stop_all
  exit 0
}
trap cleanup INT TERM

# ────────────────────────────────────────────
# 메인 로직
# ────────────────────────────────────────────
TARGET="${1:-all}"

if [[ "$TARGET" == "stop" ]]; then
  stop_all
  exit 0
fi

rm -f "$PID_FILE"

case "$TARGET" in
  all)          SERVICES="grafana prometheus alertmanager argocd" ;;
  grafana)      SERVICES="grafana" ;;
  prometheus)   SERVICES="prometheus" ;;
  alertmanager) SERVICES="alertmanager" ;;
  argocd)       SERVICES="argocd" ;;
  *)
    echo "사용법: $0 [grafana|prometheus|alertmanager|argocd|all|stop]"
    exit 1
    ;;
esac

# kubectl 컨텍스트 확인
CURRENT_CTX=$(kubectl config current-context 2>/dev/null || echo "없음")
log_info "현재 kubectl 컨텍스트: $CURRENT_CTX"
echo ""

# 서비스별 포트포워드 시작
for svc in $SERVICES; do
  start_portforward "$svc"
done

sleep 1

# shellcheck disable=SC2086
print_urls $SERVICES

wait
