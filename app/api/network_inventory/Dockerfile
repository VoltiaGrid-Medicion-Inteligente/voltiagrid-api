# api-network-inventory (US-14, T-14.1)
# Build from the repo root:
#   docker build -f app/api/network_inventory/Dockerfile -t voltiagrid-api-network-inventory .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 10001 api
USER api

# Configuration from environment variables: DATABASE_URL, JWT_SECRET
EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=2)"

CMD ["uvicorn", "app.api.network_inventory.main:app", "--host", "0.0.0.0", "--port", "8003"]
