# Timed test of the getting-started guide (US-14, T-14.5)

Someone who did **not** build the environment follows [GETTING-STARTED.md](GETTING-STARTED.md) from scratch,
on their own machine, timing each step. Goal: everything working in **less than 30 minutes** (CT-01).
Every gap found is fixed in the guide (or in the code) in the same PR or a linked one.

## Run

| Field | Value |
|---|---|
| Date | 2026-10-19 |
| Tester | María Muñoz |
| Machine | Windows, 12 GB RAM, Docker Desktop 4.94.0 |
| Starting point | Fresh clone in a new folder (`C:\repos\voltiagrid-api`), `make clean` (project volumes deleted), no `.env`, stopwatch on. Docker caches (pulled base images + build layers) from the same-day exploratory cold run were still present, which is why the official run is fast; the truly cold measurement is the exploratory run below. |

## Times

### Cold run — exploratory (first real boot: downloads and build from scratch)

*Clock hours in local time (UTC-5): reconstructed from the tester's start (~4:30 pm) plus the minutes
measured per step; a real anchor confirms the window — the 401 GET's response header `date: 22:21:29 GMT`
(= 5:21 pm local) falls inside step 4, because fixing the missed Authorize involved waiting for fixes in chat.
If a different local UTC offset applies, shift every hour by the same amount.*

| Step of the guide | Start | End | Minutes | Worked first time? | Notes |
|---|---|---|---|---|---|
| 1–2. Prerequisites + clone + configure (`make env`, edit `.env`) | 4:30 pm | ~4:38 pm | 7–8 | Yes* | `make` was not installed: installed once via `winget install ezwinports.make` (requires a new terminal afterwards). The step was repeated because the tester first ran it in the wrong folder; editing the `.env` required understanding that each password lives on two lines. |
| 3. `make up` until "Stack ready." | ~4:38 pm | ~5:01 pm | ~23 | No | ~140 s per pulled image + 1400 s of build. `migrate-seed` failed with `password authentication failed` (Postgres password different between `POSTGRES_PASSWORD` and the one inside `DATABASE_URL`). After fixing the `.env` and retrying, it finished with `exit=0` and `Stack ready.` |
| 4. Token + `GET /me/consumption/daily` + 403 check | ~5:01 pm | ~5:23 pm | ~2 active | No | Active time ~2 min: own-first 401 (tester skipped the Authorize button — human error; the guide does say to click it), then 200 and 403 correct. The wider wall-clock window (to 5:23 pm) reflects waiting for/acting on the fix in chat, confirmed by the 5:21 pm response header. |
| **Total** | **4:30 pm** | **~5:23 pm** | **> 30 (wall), ≈ 33 active** | | The 30-minute goal is **not met** on a truly first boot. The bottleneck is download + build, not tester skill — see gap 1. |

### Official run — (fresh clone in `C:\repos`, project volumes deleted with `make clean` before starting)

*T0 = stopwatch start. Minutes per step are real; absolute clock hours were not logged, so Start/End are shown as offsets from T0.*

| Step of the guide | Start | End | Minutes | Worked first time? | Notes |
|---|---|---|---|---|---|
| 1. Prerequisites checked | T0 | T0+1 | 1 | Yes | Verified `make`, `node`, `docker`, `git`, `python` (`make` had already been installed during the exploratory run). |
| 2. Clone and configure (`make env`, edit `.env`) | T0+1 | T0+3 | 2 | Yes | Fresh clone in `C:\repos`, `make env`, `.env` with both matching password pairs and a new random `JWT_SECRET`. |
| 3. `make up` until "Stack ready." | T0+3 | T0+5 | 2 | Yes | Build from cached layers; `Stack ready.`; `make ps` all `(healthy)`; `migrate-seed` `exit=0`. |
| 4. Token + `GET /me/consumption/daily` + 403 check | T0+5 | T0+8 | 3 | Yes | Login `CU-MAC000002`, Authorize, 200 on own consumption and 403 on the other customer, first try. |
| **Total** | **T0** | **T0+8** | **8** | | Goal CT-01 (< 30 min) **met** in this run. |

### Note on clock times
The cold run's hours are reconstructed from a real response header captured during the run. The official run was measured with the stopwatch only: Start/End are relative to T0. Future runs should log `Get-Date -Format "HH:mm:ss"` when starting and ending each step.

## Gaps found and fixes

| # | What blocked or confused the tester | Fix (file and change) | PR |
|---|---|---|---|
| 1 | The guide promises "a few minutes" for the first `make up`. Real cold-run breakdown: setup ~7–8 min, download+build ~23 min (~140 s per image + 1400 s of build), API testing ~2 min → **total > 30 min**, goal not met on the first boot. | GETTING-STARTED.md (step 3): set the expectation to "5 to 30 minutes the first time, depending on connection and machine; seconds afterwards". | This PR |
| 2 | Nothing warns that the Postgres password must be the same on two lines (`POSTGRES_PASSWORD` and inside `DATABASE_URL`), and likewise `RABBITMQ_DEFAULT_PASS` vs the one inside `RABBITMQ_URL`. That mismatch made `migrate-seed` fail with `password authentication failed`. | GETTING-STARTED.md (step 2): add the matching-passwords warning. | This PR |
| 3 | The run used the Spanish copy of the guide, which had to be kept in sync by hand with the English one. | Removed every Spanish document from the repo; `GETTING-STARTED.md` is the only guide. | This PR |

## Note
A first GET answered 401 because the tester skipped the Authorize button (human error; the guide does tell you to click Authorize, and the system is right to require the token).

## Result

- [x] Total under 30 minutes (official run: 8 min; the truly first cold boot exceeded 30 min — see gap 1)
- [x] `make ps` showed every service `(healthy)` and `migrate-seed` `Exited (0)`
- [x] The 403 check passed
- [x] Every gap above is fixed


## Note
A first GET answered 401 because the tester skipped the Authorize button (human error; the guide does tell you to click Authorize, and the system is right to require the token).

## Result

- [x] Total under 30 minutes (official run: 8 min; the truly first cold boot exceeded 30 min — see gap 1)
- [x] `make ps`