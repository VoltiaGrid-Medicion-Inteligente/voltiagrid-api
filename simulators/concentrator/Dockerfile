# f3-simulator (US-11, T-11.6), built from docker/Dockerfile.template (T-16.1)
# Build from the repo root:
#   docker build -f simulators/concentrator/Dockerfile -t voltiagrid/f3-simulator:local .

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

RUN useradd --create-home --uid 10001 simulator
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY app ./app
COPY seed ./seed
COPY simulators ./simulators

USER simulator

# Configuration from environment variables: DATABASE_URL, RABBITMQ_URL, SIM_*, DEFECT_RATE
CMD ["python", "-m", "simulators.concentrator"]
