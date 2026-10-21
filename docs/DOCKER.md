# Docker images: team template (US-16)

Every component we build gets its image from **`docker/Dockerfile.template`**. Copy it next to the
component as `Dockerfile`, keep the two stages and change only the marked parts.

## What the template does and why

| Practice | In the template | Why |
|---|---|---|
| Slim base | `python:3.12-slim` in both stages | The full `python:3.12` image is several times bigger and brings compilers we do not use. |
| Multi-stage | `build` installs the dependencies in `/opt/venv`; `runtime` copies only that folder and the code | pip, its cache and anything needed only to install never reach the final image. |
| Only runtime dependencies | the image installs `requirements.txt`; pytest, ruff and pre-commit are in `requirements-dev.txt` | Test and lint tools are not part of a running service. |
| Only the code it imports | explicit `COPY app ./app` (plus `seed`, `simulators` or `data/reference` when imported) | Smaller image and nothing unexpected inside. |
| `.dockerignore` | excludes `.git`, `.env*`, `tests`, `docs`, `collections`, `scripts`, markdown files | Keeps secrets and noise out of the build context. |
| Non-root user | `useradd --uid 10001` + `USER` | A compromised process cannot write outside its home. |
| Configuration from the environment | no `ENV` with values, no `.env` copied | The same image runs locally and on AWS; secrets are injected at run time. |
| Healthcheck | `HEALTHCHECK` calling `/health` with the Python standard library | Slim images have no curl; compose and ECS can tell when the service is ready. |

## Images of this repo

| Image (compose) | Dockerfile |
|---|---|
| `voltiagrid/migrate-seed:local` | `seed/Dockerfile` |
| `voltiagrid/f3-simulator:local` | `simulators/concentrator/Dockerfile` |
| `voltiagrid/api-customer-consumption:local` | `app/api/customer_consumption/Dockerfile` |
| `voltiagrid/api-network-inventory:local` | `app/api/network_inventory/Dockerfile` |
| `voltiagrid/api-transformer-metering:local` | `simulators/transformer_api/Dockerfile` |

Build them all with `docker compose build`.

## Running the tests after this change

The test tools moved to `requirements-dev.txt`. To run tests on your machine:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

`make test` and the CI already use `requirements-dev.txt`.

## Image sizes before and after the template (T-16.2)

Measured on: 2026-10-20, by Maria Muñoz, Docker Desktop (engine 29.8.2). Sizes as shown by `docker images` (uncompressed).

| Image | Before (single stage, all requirements) | After (template) | Change |
|---|---|---|---|
| migrate-seed | 353MB | 329MB | -24MB |
| f3-simulator | 353MB | 329MB | -24MB |
| api-customer-consumption | 353MB | 329MB | -24MB |
| api-network-inventory | 352MB | 328MB | -24MB |
| api-transformer-metering | 353MB | 329MB | -24MB |

How it was measured (PowerShell, repo root, Docker Desktop running):

```powershell
# 1. BEFORE: the commit just before T-16.1 was merged
git switch --detach <sha-before-T-16.1>
docker compose build
docker images --format "table {{.Repository}}\t{{.Size}}" | Select-String voltiagrid

# 2. AFTER: develop with the template
git switch develop
docker compose build
docker images --format "table {{.Repository}}\t{{.Size}}" | Select-String voltiagrid
```

Before the template the images were named `voltiagrid-api-<service>` (compose default);
after it they are `voltiagrid/<service>:local`.
