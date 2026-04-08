package main

import (
	"log"
	"net/http"
	"os"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// 환경변수 읽기 — 값이 없으면 기본값 반환
func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func main() {
	projectID := getEnv("GCP_PROJECT_ID", "cloud-sre-platform-dev")
	clusterName := getEnv("GKE_CLUSTER_NAME", "sre-platform-cluster")
	port := getEnv("PORT", "9090")

	// GKE Spot 수집기 생성 및 Prometheus 기본 레지스트리에 등록
	collector, err := NewGKECollector(projectID, clusterName)
	if err != nil {
		log.Fatalf("수집기 초기화 실패: %v", err)
	}
	prometheus.MustRegister(collector)

	// /metrics — Prometheus scrape 엔드포인트
	// /health  — liveness probe 엔드포인트
	http.Handle("/metrics", promhttp.Handler())
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	log.Printf("GKE Spot Exporter 시작 — :%s/metrics", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
