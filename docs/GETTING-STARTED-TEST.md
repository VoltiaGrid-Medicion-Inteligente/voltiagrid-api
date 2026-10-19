# Timed test of the getting-started guide (US-14, T-14.5)

Someone who did **not** build the environment follows [GETTING-STARTED.md](GETTING-STARTED.md) from scratch,
on their own machine, timing each step. Goal: everything working in **less than 30 minutes** (CT-01).
Every gap found is fixed in the guide (or in the code) in the same PR or a linked one.

## Run

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Tester | (name) |
| Machine | (OS, RAM, Docker Desktop version) |
| Starting point | fresh clone, no images downloaded, no `.env` |

## Times

| Step of the guide | Start | End | Minutes | Worked first time? | Notes |
|---|---|---|---|---|---|
| 1. Prerequisites checked | | | | | |
| 2. Clone and configure (`make env`, edit `.env`) | | | | | |
| 3. `make up` until "Stack ready." | | | | | |
| 4. Token + `GET /me/consumption/daily` + 403 check | | | | | |
| **Total** | | | | | |

## Gaps found and fixes

| # | What blocked or confused the tester | Fix (file and change) | PR |
|---|---|---|---|
| 1 | | | |

## Result

- [ ] Total under 30 minutes
- [ ] `make ps` showed every service `(healthy)` and `migrate-seed` `Exited (0)`
- [ ] The 403 check passed
- [ ] Every gap above is fixed
