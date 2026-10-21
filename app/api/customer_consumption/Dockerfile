# api-customer-consumption (US-13, T-13.6), built from docker/Dockerfile.template (T-16.1)
# Build from the repo root:
#   docker build -f app/api/customer_consumption/Dockerfile -t voltiagrid/api-customer-consumption:local .

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
# The API imports the F4 models, the consumption model of the simulators and the F7 calendar.
COPY app ./app
COPY seed ./seed
COPY simulators ./simulators
COPY data/reference ./data/reference

USER api

# Configuration comes only from environment variables:
# DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES, DEMO_CUSTOMER_PASSWORD, DEMO_INTERNAL_PASSWORD, SIM_SEED, DEFECT_RATE
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2)"

CMD ["uvicorn", "app.api.customer_consumption.main:app", "--host", "0.0.0.0", "--port", "8001"]
