# 멀티스테이지 빌드 — 이미지 크기 최소화
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ──────────────────────────────────────────────
# 런타임 이미지
# ──────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY billing-exporter.py .
COPY currency.py .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

CMD ["python", "billing-exporter.py"]
