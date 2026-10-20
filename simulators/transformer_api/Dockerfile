# api-transformer-metering, F5 (US-15, T-15.4)
# Build from the repo root:
#   docker build -f simulators/transformer_api/Dockerfile -t voltiagrid-api-transformer-metering .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY seed ./seed
COPY simulators ./simulators

RUN useradd --create-home --uid 10001 api
USER api

# Configuration from environment variables: DATABASE_URL, SIM_SEED
EXPOSE 8005
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health', timeout=2)"

# One worker on purpose: loss injections live in memory.
CMD ["uvicorn", "simulators.transformer_api.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
