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

RUN useradd --create-home --uid 10001 simulator
USER simulator

CMD ["python", "-m", "simulators.concentrator"]
