# migrate-seed (US-14, T-14.1): one-shot job that creates the F4 tables and loads the seed.
# Build from the repo root:  docker build -f seed/Dockerfile -t voltiagrid-migrate-seed .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY seed ./seed
COPY data/raw/informations_households.csv ./data/raw/informations_households.csv

RUN useradd --create-home --uid 10001 seed
USER seed

# Idempotent: running it again creates nothing new (upserts by natural key).
CMD ["sh", "-c", "alembic upgrade head && python -m seed --mode ${MODE:-dev} --seed ${SEED:-42} --defect-rate ${DEFECT_RATE:-0.02}"]
