# api-customer-consumption (US-13, T-13.6)
# Build from the repo root:
#   docker build -f app/api/customer_consumption/Dockerfile -t voltiagrid-api-customer-consumption .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# The API imports the F4 models, the consumption model of the simulators and the F7 calendar.
COPY app ./app
COPY seed ./seed
COPY simulators ./simulators
COPY data/reference ./data/reference

RUN useradd --create-home --uid 10001 api
USER api

# Configuration comes only from environment variables:
# DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES, DEMO_CUSTOMER_PASSWORD, DEMO_INTERNAL_PASSWORD, SIM_SEED, DEFECT_RATE
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2)"

CMD ["uvicorn", "app.api.customer_consumption.main:app", "--host", "0.0.0.0", "--port", "8001"]
