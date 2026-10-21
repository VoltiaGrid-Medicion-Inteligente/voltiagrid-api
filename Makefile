# Local ecosystem commands (US-14, T-14.3). Run them from the repo root.
# Windows: install GNU make once with `winget install ezwinports.make` and reopen the terminal.

COMPOSE := docker compose
PYTHON  ?= python
s       ?=

# Values for the test container come from .env (the same file docker compose reads).
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: help env up down clean seed logs ps test

help:
	@echo "make up      build and start everything (Postgres, RabbitMQ, migrations + seed, APIs, simulators)"
	@echo "make down    stop and remove the containers (data stays in the volumes)"
	@echo "make clean   like down, but also deletes the volumes (database and queues start empty)"
	@echo "make seed    run migrations and the seed again (idempotent)"
	@echo "make logs    follow the logs of every service, or one: make logs s=api-customer-consumption"
	@echo "make ps      show the services and their health"
	@echo "make test    run the test suite in a container against the stack database"

env:
ifeq (,$(wildcard .env))
	$(PYTHON) -c "import shutil; shutil.copy('.env.example', '.env')"
	@echo ".env created from .env.example: change the change-me values before sharing anything."
endif

up: env
	$(COMPOSE) up -d --build
	$(PYTHON) scripts/wait_for_stack.py
	$(COMPOSE) ps

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v

seed:
	$(COMPOSE) run --rm migrate-seed

logs:
	$(COMPOSE) logs -f --tail=100 $(s)

ps:
	$(COMPOSE) ps -a

test:
	docker run --rm --network voltia -v "$(CURDIR):/app" -w /app -e DATABASE_URL=postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@db:5432/$(POSTGRES_DB) python:3.12-slim sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests -q"
