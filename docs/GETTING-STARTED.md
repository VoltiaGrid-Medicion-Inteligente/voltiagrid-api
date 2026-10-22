# Getting started: the whole system on your machine

Goal (CT-01): someone who did not build the environment has everything running in **less than 30 minutes**.

## 1. Prerequisites (install once)

| Tool                                    | Version | Check                    |
| --------------------------------------- | ------- | ------------------------ |
| Docker Desktop (with Docker Compose v2) | 4.30+   | `docker compose version` |
| Git                                     | any     | `git --version`          |
| Python                                  | 3.12    | `python --version`       |
| GNU make                                | 4.x     | `make --version`         |
| Node.js (only for the test collection)  | 18+     | `node --version`         |

On Windows, install make with `winget install ezwinports.make` and open a new terminal.
Docker Desktop must be **running** (whale icon steady) before any command.

## 2. Clone and configure

```bash
git clone https://github.com/VoltiaGrid-Medicion-Inteligente/voltiagrid-api.git
cd voltiagrid-api
make env
```

`make env` creates `.env` from `.env.example` (only if it does not exist). Open `.env` and replace every
`change-me` value. For `JWT_SECRET` generate a long random value:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Heads-up (KAN-185): the Postgres password appears on **two lines** — `POSTGRES_PASSWORD` and inside
> `DATABASE_URL` (between `voltia:` and `@localhost`) — and must be **the same** on both. Same for
> `RABBITMQ_DEFAULT_PASS` and the one inside `RABBITMQ_URL`. If they do not match, `make up` fails with
> `password authentication failed` in `migrate-seed`.

`.env` is git-ignored: never commit it and never paste its values in issues or chats.

## 3. Start everything

```bash
make up
```

It builds the images, starts Postgres and RabbitMQ, runs the migrations and the seed (`migrate-seed`),
then starts the APIs and the F3 simulator, and waits until every API answers `/health`.
The first run downloads images and builds the project images: depending on your connection and machine
this can take **5 to 30 minutes**; later runs take seconds (cached).

Check: `make ps` shows every service `(healthy)` and `migrate-seed` as `Exited (0)`.

## 4. Use it

| What                     | URL                        | Notes                                   |
| ------------------------ | -------------------------- | --------------------------------------- |
| Customer consumption API | http://localhost:8001/docs | `POST /auth/token` gives the JWT |
| Control center API | http://localhost:8002/docs | load per transformer and overload alerts, internal users |
| Network inventory API | http://localhost:8003/docs | internal users |
| F5 transformer metering API | http://localhost:8005/docs | energy delivered every 15 min, loss injection |

Try it in the customer consumption `/docs`:

1. `POST /auth/token` with `{"username": "CU-MAC000002", "password": "<DEMO_CUSTOMER_PASSWORD>"}` and copy `access_token`.
2. Click **Authorize**, paste the token and run `GET /me/consumption/daily?month=2013-02`.
3. Run `GET /customers/CU-MAC000003/consumption/daily?month=2013-02` with the same token: it must answer **403**.

## 5. Make targets

| Command      | What it does                                                              |
| ------------ | ------------------------------------------------------------------------- |
| `make up`    | Build and start everything; migrations and seed run on their own          |
| `make ps`    | Services and their health                                                 |
| `make logs`  | Follow all logs; one service: `make logs s=api-customer-consumption`      |
| `make seed`  | Run migrations and the seed again (idempotent: creates no duplicates)     |
| `make test`  | Run the test suite in a container against the stack database              |
| `make down`  | Stop the containers; data stays in the volumes                            |
| `make clean` | Stop and delete the volumes: next `make up` starts from an empty database |

## 6. Troubleshooting

| Symptom                                                                          | Cause and fix                                                                                                                                                                                                                      |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `failed to connect to the docker API` / `open //./pipe/dockerDesktopLinuxEngine` | Docker Desktop is not running. Start it and wait until it says *Engine running*. |
| `Bind for 0.0.0.0:5433 failed: port is already allocated` | Another container or a local Postgres uses the port. `docker ps` to find it and stop it, or change the left side of the port in `docker-compose.yml`. Same for 5672, 15672, 8001, 8002, 8003, 8005. |
| `make: command not found` | make is not installed or the terminal was open before installing it. `winget install ezwinports.make` and open a new terminal. Without make, run the commands of the table in `Makefile` by hand (`docker compose up -d --build`). |
| `migrate-seed` exited with an error | `make logs s=migrate-seed`. Usually a wrong value in `.env`; fix it and run `make seed`. |