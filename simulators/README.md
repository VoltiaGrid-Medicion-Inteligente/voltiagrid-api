# Simulators

Simulated sources of the VoltiaGrid platform. All of them use the same seed
(`SIM_SEED`) and the same consumption model (`simulators/common/consumption.py`),
so their numbers agree with each other.

| Source | Package | What it does | Story |
|---|---|---|---|
| F3 | `simulators/concentrator` | Every 30 minutes, one JSON message per concentrator (one per transformer) with the readings of its meters, published to RabbitMQ | US-11 |
| F5 | `simulators/transformer_api` | REST API with the energy delivered to each transformer every 15 minutes | US-15 |

## Before running

The simplest way is the whole stack: `make up` (see `docs/GETTING-STARTED.md`).
To run a simulator from your terminal instead:

```bash
make env                        # then edit the passwords in .env
docker compose up -d db rabbitmq migrate-seed
```

## F3 concentrator simulator

```bash
# 4 intervals, 2 seconds apart, published to RabbitMQ
python -m simulators.concentrator --ticks 4 --tick-seconds 2

# no RabbitMQ and no database: 200,000 synthetic meters, one interval, log only
python -m simulators.concentrator --no-db --meters 200000 --dry-run --ticks 1

# outage: 1,000 meters lose the link for 24 hours, then resend in bulk (CA-08)
python -m simulators.concentrator --outage-meters 1000 --outage-hours 24 --ticks 49 --tick-seconds 0
```

- Message contract: `simulators/concentrator/schema/reading_batch.v1.json` (JSON Schema). Every message is validated before it is published.
- RabbitMQ: exchange `readings` (topic), queues `readings.live` and `readings.resend`, dead letters to `readings.dead`. Persistent messages, publisher confirms, `mandatory=True`.
- Defects (rate `DEFECT_RATE`, default 0.02): gaps, missing days, duplicates with a different value and a higher `reading_seq`, skewed clocks, nulls and out-of-range values.
- Web console: http://localhost:15672 (user and password from `.env`) to see the queues fill.

## F5 transformer metering API

```bash
python -m uvicorn simulators.transformer_api.main:app --port 8005
# interactive docs: http://localhost:8005/docs
```

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/transformers` | Transformer codes and how many meters each one feeds |
| GET | `/transformers/{code}/energy?start=...&end=...` | Delivered kWh every 15 minutes (range of 7 days or less, dates with time zone) |

- delivered = sum of the transformer's meters. It equals what F3 sends for the same meters and seed.
- Without a database: `SIM_SYNTHETIC_METERS=5500 python -m uvicorn simulators.transformer_api.main:app --port 8005`