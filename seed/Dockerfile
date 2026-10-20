# migrate-seed (US-14, T-14.1), built from docker/Dockerfile.template (T-16.1):
# one-shot job that creates the F4 tables and loads the seed.
# Build from the repo root:  docker build -f seed/Dockerfile -t voltiagrid/migrate-seed:local .

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

RUN useradd --create-home --uid 10001 seed
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY seed ./seed
COPY data/raw/informations_households.csv ./data/raw/informations_households.csv

USER seed

# Configuration from environment variables: DATABASE_URL, MODE, SEED, DEFECT_RATE.
# Idempotent: running it again creates nothing new (upserts by natural key).
CMD ["sh", "-c", "alembic upgrade head && python -m seed --mode ${MODE:-dev} --seed ${SEED:-42} --defect-rate ${DEFECT_RATE:-0.02}"]
