# Configuration review: ports, variables and secrets (US-14, T-14.6)

Reviewed files: `docker-compose.yml`, `.env.example`, `.gitignore`, every `Dockerfile`, `Makefile`.
Repeat this review whenever a service, a port or a variable is added.

## Checklist

| # | Check | How | Result |
|---|---|---|---|
| 1 | No real credential in any committed file | `gitleaks` over the full history (command below) and reading the files | OK: no leaks |
| 2 | `.env` is never committed, variants neither | `.gitignore` has `.env` and `.env.*`, keeps `.env.example` | OK |
| 3 | `.env.example` only has placeholders | every secret is `change-me` or `change-me-to-a-long-random-string` | OK |
| 4 | Every variable used by compose exists in `.env.example` | `docker compose config` with a copy of `.env.example` | OK |
| 5 | A missing secret stops compose with a clear message | secrets use `${VAR:?message}`; remove `JWT_SECRET` from `.env` and run `docker compose config` | OK: `required variable JWT_SECRET is missing` |
| 6 | No secret is written inside `docker-compose.yml` | values come from `${...}` only | OK |
| 7 | Ports listen only on the local machine | every `ports:` entry starts with `127.0.0.1:` | OK |
| 8 | No secret is copied into an image | Dockerfiles copy code only; `.dockerignore` excludes `.env`, `.git`, `tests`, `docs` | OK (T-16.3 scans the built images) |
| 9 | Containers do not run as root | every Dockerfile has `USER` with uid 10001 | OK |
| 10 | Tests never use the real secret | `tests/conftest.py` overrides `JWT_SECRET` and the demo passwords | OK |

## Ports

| Port (host) | Service | Exposed to |
|---|---|---|
| 5433 | Postgres | 127.0.0.1 |
| 5672 | RabbitMQ AMQP | 127.0.0.1 |
| 15672 | RabbitMQ management | 127.0.0.1 |
| 8001 | api-customer-consumption | 127.0.0.1 |
| 8002 | api-control-center | 127.0.0.1 |
| 8003 | api-network-inventory | 127.0.0.1 |
| 8005 | api-transformer-metering (F5) | 127.0.0.1 |

## Secret scan

```bash
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:v8.18.4 detect --source /repo --redact --verbose
```

Expected last line: `no leaks found`. On PowerShell `${PWD}` works as written. The same scan runs in CI (`secrets` job).
