# api-transformer-metering, F5 (US-15, T-15.4), built from docker/Dockerfile.template (T-16.1)
# Build from the repo root:
#   docker build -f simulators/transformer_api/Dockerfile -t voltiagrid/api-transformer-metering:local .

# ---------- build stage ----------
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 api
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY seed ./seed
COPY simulators ./simulators

USER api

# Configuration from environment variables: DATABASE_URL, SIM_SEED
EXPOSE 8005
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health', timeout=2)"

# One worker on purpose: loss injections live in memory.
CMD ["uvicorn", "simulators.transformer_api.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
