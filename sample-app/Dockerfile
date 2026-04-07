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

# builder에서 설치된 패키지만 복사
COPY --from=builder /root/.local /root/.local
COPY main.py .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
