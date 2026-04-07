import asyncio
import random
import time

import structlog
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator

# ──────────────────────────────────────────────
# 구조화 로깅 설정 (JSON 형식 → Alloy → Loki)
# ──────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# ──────────────────────────────────────────────
# OpenTelemetry 트레이싱 설정 → Tempo
# ──────────────────────────────────────────────
resource = Resource.create({"service.name": "sample-app"})
provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(
    endpoint="http://tempo.monitoring:4317",
    insecure=True,
)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# ──────────────────────────────────────────────
# FastAPI 앱 초기화
# ──────────────────────────────────────────────
app = FastAPI(title="sample-app", version="1.0.0")

# Prometheus 메트릭 자동 수집 (/metrics 엔드포인트)
Instrumentator().instrument(app).expose(app)

# FastAPI 자동 트레이싱 계측
FastAPIInstrumentor.instrument_app(app)

# 더미 주문 데이터
ORDERS = [
    {"id": 1, "item": "keyboard", "price": 120000, "status": "delivered"},
    {"id": 2, "item": "mouse", "price": 45000, "status": "processing"},
    {"id": 3, "item": "monitor", "price": 350000, "status": "shipped"},
]


# ──────────────────────────────────────────────
# 엔드포인트 정의
# ──────────────────────────────────────────────

@app.get("/health")
def health():
    """헬스체크 — Kubernetes liveness/readiness probe 용"""
    return {"status": "ok"}


@app.get("/orders")
def get_orders():
    """주문 목록 반환 (정상 응답)"""
    with tracer.start_as_current_span("get-orders"):
        logger.info("orders.list", count=len(ORDERS))
        return {"orders": ORDERS}


@app.post("/orders")
def create_order(item: str, price: int):
    """주문 생성 (더미 — 실제 저장 없음)"""
    with tracer.start_as_current_span("create-order") as span:
        new_order = {
            "id": len(ORDERS) + 1,
            "item": item,
            "price": price,
            "status": "processing",
        }
        ORDERS.append(new_order)
        span.set_attribute("order.item", item)
        span.set_attribute("order.price", price)
        logger.info("orders.created", item=item, price=price)
        return new_order


@app.get("/slow")
async def slow():
    """의도적 지연 — 트레이싱/레이턴시 알럿 테스트용"""
    delay = random.uniform(1.0, 3.0)
    with tracer.start_as_current_span("slow-operation") as span:
        span.set_attribute("delay_seconds", delay)
        logger.info("slow.start", delay=round(delay, 2))
        await asyncio.sleep(delay)
        logger.info("slow.done", delay=round(delay, 2))
    return {"delayed_seconds": round(delay, 2)}


@app.get("/error")
def error():
    """의도적 500 에러 — 알럿/에러율 테스트용"""
    logger.error("error.triggered", reason="intentional")
    raise HTTPException(status_code=500, detail="intentional error")
