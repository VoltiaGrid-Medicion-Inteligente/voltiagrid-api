# Contributing Guidelines — VoltaGrid API

> Language: [🇺🇸 English](CONTRIBUTING.md) | [🇪🇸 Español](CONTRIBUTING.es.md)

This guide covers the full workflow: `git clone` → setup → branch → commit → PR → review → merge.
It combines [Conventional Commits](https://www.conventionalcommits.org/) (like the CoDecide reference repo) with the team's **Jira (KAN)** workflow.

---

## 0. Prerequisites

- Git, Python 3.12, Docker + Docker Compose.
- A GitHub account with access to `VoltiaGrid-Medicion-Inteligente/voltiagrid-api`.
- A Jira account. Your local git email **must match** your Jira email, otherwise Smart Commits won't link:
  ```bash
  git config user.name "Your Name"
  git config user.email "you@jira-email.com"
  ```

## 1. Clone and setup (first time only)

```bash
# HTTPS (simplest)
git clone https://github.com/VoltiaGrid-Medicion-Inteligente/voltiagrid-api.git
cd voltiagrid-api

# or SSH (if you use SSH keys)
# git clone git@github.com:VoltiaGrid-Medicion-Inteligente/voltiagrid-api.git
# cd voltiagrid-api

cp .env.example .env
docker compose up -d
alembic upgrade head
python -m seed --mode dev --seed 42 --defect-rate 0
python -m pytest tests/ -v
```

Rules:

- **Never commit `.env`.** Only `.env.example` (no secrets) goes to git (CT-02).
- Same code runs locally or on RDS — only `DATABASE_URL` changes.
- If `psycopg` is blocked on Windows, run seed/tests inside Docker (see `README.md` Quick Start).

## 2. Branch Strategy

```
main ────────────── stable branch, PRs merge here (demo / release)
  ├── feature/KAN-12-short-description
  ├── fix/KAN-13-short-description
  ├── refactor/KAN-14-short-description
  ├── docs/KAN-15-short-description
  └── chore/KAN-16-short-description
```

### Branch Naming Convention

```
<type>/KAN-<number>-<short-description>
```

| Type | When to use | Example |
|------|-------------|---------|
| `feature/` | New functionality / user story | `feature/KAN-12-meter-consumer` |
| `fix/` | Bug fix | `fix/KAN-13-login-redirect-loop` |
| `refactor/` | Restructure without behavior change | `refactor/KAN-14-extract-meter-service` |
| `chore/` | Tooling, dependencies, config, CI | `chore/KAN-16-upgrade-pytest` |
| `docs/` | Documentation only | `docs/KAN-15-document-f3-simulator` |
| `test/` | Tests only | `test/KAN-16-seed-hash-test` |

- Jira key in **UPPERCASE** (`KAN-12`, not `kan-12`) so Jira auto-links branch → issue.
- Description in **kebab-case**, short but meaningful, English preferred.
- All branches come from up-to-date `main`.

### Rules

- **Never push directly to `main`.** All changes via Pull Request.
- Any commit pushed directly to `main` will be reverted/deleted.
- One branch per Jira issue/task. If the task grows, split the issue, don't grow the branch.
- Keep `main` green: pull before branching.

Create a branch:

```bash
git checkout main
git pull origin main
git checkout -b feature/KAN-12-meter-consumer
```

## 3. Conventional Commits + Jira

### Format

```
KAN-<number> <type>(<scope>): <description>
```

- The `KAN-XX` prefix keeps Jira automation (branch/commit/PR all linked).
- The rest follows Conventional Commits.

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Neither fix nor feature |
| `style` | Formatting only (no production change) |
| `docs` | Documentation only |
| `chore` | Build, deps, tooling, CI |
| `test` | Add/modify tests |
| `perf` | Performance improvement |

### Scopes (this repo)

API/DB: `api`, `models`, `schemas`, `services`, `repositories`, `migrations`, `auth`
Ingestion: `seed`, `simulators`, `rabbitmq`, `consumers`
Cross-cutting: `config`, `docker`, `ci`, `docs`, `deps`, `tests`

### Examples (copy the style)

```
KAN-12 feat(consumers): add meter reading consumer with manual ack
KAN-13 fix(rabbitmq): ignore duplicate message_id on requeue
KAN-14 refactor(seed): extract upsert by natural key helper
KAN-15 docs(api): document transformer load endpoint
KAN-16 test(seed): compare table hash across two runs
KAN-15 chore(config): add DATABASE_URL override by CLI
```

### Rules

- **Jira key first, UPPERCASE** (`KAN-12`, not `kan-12`).
- **Description in English, imperative present tense:** "add" not "added"/"adds".
- **Lowercase description, no trailing period**, concise (<72 chars if possible).
- One logical change per commit. Two unrelated fixes → two commits.
- Small commits preferred. 20+ files in one commit → split it.

Good split:

```
KAN-12 feat(models): add meter and transformer tables
KAN-12 feat(seed): wire meter assignment 50-80 per transformer
```

Bad:

```
KAN-12 feat: add lots of stuff   # 35 files, 1200 additions
```

Fix a message before pushing:

```bash
git commit --amend -m "KAN-12 feat(seed): correct message"
# if already pushed to YOUR branch only:
git push --force-with-lease
```

### Smart Commits (Jira automation)

Only works if `git config user.email` == Jira email:

```
KAN-12 #comment ready for review
KAN-12 #done
```

Use them in a separate commit or in the PR description — don't mix with code changes silently.

## 4. Pull Request Workflow

1. Update from `main`, run checks:

   ```bash
   git checkout feature/KAN-12-meter-consumer
   git pull --rebase origin main
   python -m pytest tests/ -v
   ```

2. Push and open a PR **targeting `main**:

   ```bash
   git push -u origin feature/KAN-12-meter-consumer
   ```

3. PR title = same as commit format (Jira key + Conventional):

   ```
   KAN-12 feat(consumers): add meter reading consumer with manual ack
   ```

4. PR description (required template):

   ```markdown
   ## What
   Brief description of the change.

   ## Why
   Reason + Jira issue (e.g. KAN-12).

   ## How to test
   1. cp .env.example .env
   2. docker compose up -d
   3. python -m pytest tests/ -v

   ## Screenshots / evidence (if applicable)
   ```

5. Wait for review + green CI (lint, tests, secret scan). Address comments with **new commits**, don't rewrite history under review.
6. Maintainer merges into `main` via reviewed PR (squash by default, keeping `KAN-XX` in title). `main` must always stay green and demo-ready.

### Pre-PR checklist

- [ ] Branch from latest `main`, name `type/KAN-XX-kebab-case`.
- [ ] Commits `KAN-XX type(scope): english imperative description`.
- [ ] `pytest` green locally (or in Docker).
- [ ] No secrets/`.env`/credentials in diff (`git status`, `git diff --check`).
- [ ] Seed still idempotent if you touched it (run twice, 0 duplicates).
- [ ] PR targets `main`, title + template filled.

## 5. What gets your PR rejected

- Direct push to `main`.
- Missing Jira key or lowercase key (`kan-12`).
- Non-Conventional message (`added stuff`, `fix style.`, capitalised sentence).
- Giant commit, mixed concerns, or untested business rule (every RN-* needs at least one automated test).
- Secrets in code/images, or hardcoded `DATABASE_URL`.
