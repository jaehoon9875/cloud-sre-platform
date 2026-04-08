package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"google.golang.org/api/compute/v1"
	"google.golang.org/api/option"
)

const (
	// GCP API 호출 비용 절감을 위한 캐시 유지 시간
	cacheTTL = 5 * time.Minute
	// preemption 이벤트 조회 기간 (최근 24시간)
	preemptionLookback = 24 * time.Hour
)

// GKECollector — GKE 클러스터의 Spot 노드 관련 메트릭 수집기
// prometheus.Collector 인터페이스를 구현한다
type GKECollector struct {
	projectID   string
	clusterName string
	computeSvc  *compute.Service

	// Prometheus 메트릭 디스크립터
	nodeCountDesc       *prometheus.Desc
	preemptionTotalDesc *prometheus.Desc
	scrapeDurationDesc  *prometheus.Desc
	scrapeErrorDesc     *prometheus.Desc

	// 동시성 안전 캐시
	mu          sync.Mutex
	cache       *collectorCache
	lastUpdated time.Time
}

// collectorCache — GCP API 응답 캐시 구조체
type collectorCache struct {
	nodeData       []nodeMetric
	preemptionData []preemptionMetric
}

// nodeMetric — zone/nodePool/spot 조합별 노드 수
type nodeMetric struct {
	zone     string
	nodePool string
	spot     string // "true" | "false"
	count    float64
}

// preemptionMetric — zone별 선점 발생 횟수
type preemptionMetric struct {
	zone  string
	count float64
}

// NewGKECollector — 수집기 생성 및 GCP Compute 클라이언트 초기화
// GKE Workload Identity 환경에서는 ADC(Application Default Credentials)가 자동으로 사용된다
func NewGKECollector(projectID, clusterName string) (*GKECollector, error) {
	ctx := context.Background()

	// Compute API 클라이언트 — WI 환경에서는 키 파일 없이 자동 인증
	svc, err := compute.NewService(ctx, option.WithScopes(compute.ComputeReadonlyScope))
	if err != nil {
		return nil, fmt.Errorf("Compute API 클라이언트 생성 실패: %w", err)
	}

	clusterLabel := prometheus.Labels{"cluster": clusterName}

	return &GKECollector{
		projectID:   projectID,
		clusterName: clusterName,
		computeSvc:  svc,

		// gke_node_count{cluster, zone, node_pool, spot}
		nodeCountDesc: prometheus.NewDesc(
			"gke_node_count",
			"GKE 클러스터의 RUNNING 상태 노드 수 (zone, node_pool, spot 기준 분류)",
			[]string{"zone", "node_pool", "spot"},
			clusterLabel,
		),
		// gke_node_preemption_total{cluster, zone}
		preemptionTotalDesc: prometheus.NewDesc(
			"gke_node_preemption_total",
			"최근 24시간 내 Spot 노드 선점(preemption) 발생 횟수",
			[]string{"zone"},
			clusterLabel,
		),
		// 수집기 자체 상태 메트릭
		scrapeDurationDesc: prometheus.NewDesc(
			"gke_exporter_scrape_duration_seconds",
			"GCP API 데이터 수집 소요 시간 (초)",
			nil, nil,
		),
		scrapeErrorDesc: prometheus.NewDesc(
			"gke_exporter_scrape_error",
			"GCP API 수집 오류 여부 (1=오류 발생, 0=정상)",
			nil, nil,
		),
	}, nil
}

// Describe — Prometheus가 메트릭 메타데이터를 조회할 때 호출 (등록 시 한 번)
func (c *GKECollector) Describe(ch chan<- *prometheus.Desc) {
	ch <- c.nodeCountDesc
	ch <- c.preemptionTotalDesc
	ch <- c.scrapeDurationDesc
	ch <- c.scrapeErrorDesc
}

// Collect — Prometheus가 /metrics scrape 시마다 호출
func (c *GKECollector) Collect(ch chan<- prometheus.Metric) {
	start := time.Now()
	scrapeError := 0.0

	data, err := c.getDataWithCache()
	if err != nil {
		log.Printf("[ERROR] 메트릭 수집 실패: %v", err)
		scrapeError = 1.0
	} else {
		// 노드 수 메트릭 전송
		for _, n := range data.nodeData {
			ch <- prometheus.MustNewConstMetric(
				c.nodeCountDesc,
				prometheus.GaugeValue,
				n.count,
				n.zone, n.nodePool, n.spot,
			)
		}
		// Preemption 횟수 메트릭 전송
		for _, p := range data.preemptionData {
			ch <- prometheus.MustNewConstMetric(
				c.preemptionTotalDesc,
				prometheus.GaugeValue,
				p.count,
				p.zone,
			)
		}
	}

	// 수집기 자체 상태 메트릭 항상 전송
	ch <- prometheus.MustNewConstMetric(c.scrapeDurationDesc, prometheus.GaugeValue, time.Since(start).Seconds())
	ch <- prometheus.MustNewConstMetric(c.scrapeErrorDesc, prometheus.GaugeValue, scrapeError)
}

// getDataWithCache — 캐시가 유효하면 캐시 반환, 만료 시 GCP API 재호출
func (c *GKECollector) getDataWithCache() (*collectorCache, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.cache != nil && time.Since(c.lastUpdated) < cacheTTL {
		return c.cache, nil
	}

	log.Printf("[INFO] 캐시 만료 — GCP API 재수집 시작 (project=%s, cluster=%s)", c.projectID, c.clusterName)
	cache, err := c.fetchFromGCP()
	if err != nil {
		// 이전 캐시가 있으면 오류 대신 구 데이터 반환 (일시적 API 장애 대응)
		if c.cache != nil {
			log.Printf("[WARN] API 오류, 이전 캐시 데이터 사용: %v", err)
			return c.cache, nil
		}
		return nil, err
	}

	c.cache = cache
	c.lastUpdated = time.Now()
	return c.cache, nil
}

// fetchFromGCP — GCP Compute API를 호출하여 노드 및 preemption 데이터 수집
func (c *GKECollector) fetchFromGCP() (*collectorCache, error) {
	ctx := context.Background()

	nodes, err := c.fetchNodeData(ctx)
	if err != nil {
		return nil, fmt.Errorf("노드 데이터 수집 실패: %w", err)
	}

	preemptions, err := c.fetchPreemptionData(ctx)
	if err != nil {
		// preemption 조회 실패는 치명적이지 않으므로 경고 후 빈 슬라이스 반환
		log.Printf("[WARN] preemption 데이터 수집 실패 (노드 메트릭은 정상): %v", err)
		preemptions = []preemptionMetric{}
	}

	return &collectorCache{
		nodeData:       nodes,
		preemptionData: preemptions,
	}, nil
}

// fetchNodeData — Compute API Aggregated Instances List로 GKE 노드 목록 조회
// GKE 노드는 'goog-k8s-cluster-name' 라벨로 식별한다
func (c *GKECollector) fetchNodeData(ctx context.Context) ([]nodeMetric, error) {
	filter := fmt.Sprintf(`labels.goog-k8s-cluster-name="%s" AND status="RUNNING"`, c.clusterName)

	// zone + nodePool + spot 조합별 집계
	type key struct{ zone, nodePool, spot string }
	counts := make(map[key]float64)

	err := c.computeSvc.Instances.AggregatedList(c.projectID).
		Filter(filter).
		Fields("items/*/instances(zone,labels,scheduling)").
		Pages(ctx, func(page *compute.InstanceAggregatedList) error {
			for _, scopedList := range page.Items {
				for _, inst := range scopedList.Instances {
					zone := lastSegment(inst.Zone)

					// GKE가 자동으로 붙이는 노드 풀 라벨
					nodePool := inst.Labels["cloud.google.com/gke-nodepool"]
					if nodePool == "" {
						nodePool = "unknown"
					}

					spot := "false"
					if inst.Scheduling != nil && inst.Scheduling.Preemptible {
						spot = "true"
					}

					counts[key{zone, nodePool, spot}]++
				}
			}
			return nil
		})
	if err != nil {
		return nil, err
	}

	result := make([]nodeMetric, 0, len(counts))
	for k, v := range counts {
		result = append(result, nodeMetric{
			zone: k.zone, nodePool: k.nodePool, spot: k.spot, count: v,
		})
	}
	return result, nil
}

// fetchPreemptionData — 최근 24시간 내 Spot 선점(preemption) 이벤트 수 조회
// GCP Operations API의 operationType="compute.instances.preempted" 이벤트를 집계한다
func (c *GKECollector) fetchPreemptionData(ctx context.Context) ([]preemptionMetric, error) {
	since := time.Now().Add(-preemptionLookback).UTC().Format(time.RFC3339)
	filter := fmt.Sprintf(
		`operationType="compute.instances.preempted" AND insertTime>="%s"`, since,
	)

	zoneCounts := make(map[string]float64)

	err := c.computeSvc.GlobalOperations.AggregatedList(c.projectID).
		Filter(filter).
		Fields("items/*/operations(zone,operationType)").
		Pages(ctx, func(page *compute.OperationAggregatedList) error {
			for _, scopedList := range page.Items {
				for _, op := range scopedList.Operations {
					zone := lastSegment(op.Zone)
					if zone != "" {
						zoneCounts[zone]++
					}
				}
			}
			return nil
		})
	if err != nil {
		return nil, err
	}

	result := make([]preemptionMetric, 0, len(zoneCounts))
	for zone, count := range zoneCounts {
		result = append(result, preemptionMetric{zone: zone, count: count})
	}
	return result, nil
}

// lastSegment — GCP 리소스 URL에서 마지막 세그먼트 추출
// 예: "https://.../zones/asia-northeast3-a" → "asia-northeast3-a"
func lastSegment(url string) string {
	parts := strings.Split(url, "/")
	if len(parts) == 0 {
		return ""
	}
	return parts[len(parts)-1]
}
