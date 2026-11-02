# f3-consumer (US-29, T-29.2), built from docker/Dockerfile.template (T-16.1)
# Build from the repo root:
#   docker build -f ingestion/Dockerfile -t voltiagrid/f3-consumer:local .

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

RUN useradd --create-home --uid 10001 consumer \
    && mkdir -p /lake/raw && chown -R consumer /lake
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY ingestion ./ingestion
COPY simulators ./simulators

USER consumer

# Configuration from environment variables: RABBITMQ_URL, RAW_DIR or RAW_BUCKET, CONSUMER_PREFETCH,
# RAW_BATCH_SIZE, RAW_BATCH_SECONDS
CMD ["python", "-m", "ingestion"]
