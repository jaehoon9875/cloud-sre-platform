# ── Stage 1: 빌드 ─────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS builder

WORKDIR /app

# 의존성 레이어 캐시 최적화 (소스 변경 시 재다운로드 방지)
COPY go.mod go.sum ./
RUN go mod download

# 소스 복사 및 정적 바이너리 빌드
COPY *.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -o gke-spot-exporter .

# ── Stage 2: 실행 이미지 ───────────────────────────────────────────────────────
# distroless: shell 없는 최소 이미지 (보안 + 크기 최적화)
FROM gcr.io/distroless/static:nonroot

WORKDIR /

COPY --from=builder /app/gke-spot-exporter .

# 9090 포트 노출 (Prometheus 기본 관례)
EXPOSE 9090

USER nonroot:nonroot

ENTRYPOINT ["/gke-spot-exporter"]
