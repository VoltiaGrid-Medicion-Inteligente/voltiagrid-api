# api-network-inventory (US-14, T-14.1), built from docker/Dockerfile.template (T-16.1)
# Build from the repo root:
#   docker build -f app/api/network_inventory/Dockerfile -t voltiagrid/api-network-inventory:local .

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

USER api

# Configuration from environment variables: DATABASE_URL, JWT_SECRET
EXPOSE 8003
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=2)"

CMD ["uvicorn", "app.api.network_inventory.main:app", "--host", "0.0.0.0", "--port", "8003"]
