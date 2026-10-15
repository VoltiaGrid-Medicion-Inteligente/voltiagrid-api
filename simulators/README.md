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