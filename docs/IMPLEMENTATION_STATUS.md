# Implementation Status

Last updated: 2026-10-19

## Current state

**Milestone 0 (Repository and environment audit) — in progress, awaiting review.**

No application code exists yet. This file, `docs/ROADMAP.md`, and `docs/ARCHITECTURE.md`
are the only project artifacts so far.

## Repository audit

- Working directory (`/Users/akanksha./Documents/InfraGuard`) was completely empty before
  this session — no source files, no config, no `.git`.
- Not yet a git repository. Proposal: `git init` with an initial commit of the Milestone 0
  docs, once reviewed, so all subsequent milestones are tracked incrementally.

## Local toolchain audit (macOS, Darwin 24.6.0, Apple Silicon/arm64)

| Tool | Found | Version | Notes / Decision |
|---|---|---|---|
| `python3` (system) | yes | 3.9.6 (`/usr/bin/python3`, Apple CLT) | Too old to target directly (EOL soon, misses newer typing syntax). **Not used as the project interpreter.** |
| Homebrew Python | yes | 3.12.15 (`/opt/homebrew/bin/python3.12`) | Usable directly, but see `uv` below. |
| `uv` | yes | 0.12.24 | **Chosen packaging/venv tool.** Can provision and pin a Python 3.12 interpreter and manage a lockfile without Poetry. Replaces the `poetry`-style flow implied by the brief; Poetry itself is not installed and not needed. |
| `poetry` | no | — | Not installed; not required since `uv` covers the same job with less setup. |
| `pip` | yes | 21.2.4 (tied to system Python 3.9) | Not used directly; `uv` manages dependencies. |
| `git` | yes | 2.50.1 | — |
| `make` | yes | GNU Make 3.81 (Apple CLT, circa 2006) | Old but sufficient for simple, portable Makefile targets (`install`, `lint`, `test`, `demo`). Avoid relying on modern GNU Make 4.x–only features. |
| `docker` (CLI) | yes | 29.6.1, context `colima` | Daemon is up via Colima (not Docker Desktop). 1 running + 16 stopped containers already exist on this machine from unrelated prior work — **InfraGuard will never touch containers/volumes it did not create itself**, and all lab resources will use an explicit, InfraGuard-prefixed project name. |
| `docker compose` (CLI plugin subcommand) | no | — | `docker compose version` reports "unknown command" under this CLI/Colima context, even though a plugin shim is present in `~/.docker/cli-plugins/`. |
| `docker-compose` (standalone binary) | yes | 5.3.1 (`/opt/homebrew/bin/docker-compose`) | **Fallback that works today.** Module C tooling/Makefile will try `docker compose` first and fall back to `docker-compose` automatically, documented plainly rather than assumed. |
| `psql` / `pg_ctl` (local Postgres client/server) | no | — | No bare-metal PostgreSQL install on this machine at all. This is actually convenient: it enforces the constraint that the recovery lab's Postgres only ever runs **inside Docker**, never against a host install. The Python app will speak to Postgres via a Python driver (`psycopg[binary]`, bundles its own libpq) rather than shelling out to `psql`. |
| `terraform` | yes | 1.15.8 | Used only to *generate* example `plan.json` fixtures for docs/demo (`terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json`). InfraGuard itself never invokes `terraform` at runtime — it only parses the JSON produced by that workflow, and tests run against committed static fixture files so they need no network or Terraform install. |

### Implication for the "must still work if Docker is unavailable" requirement

Confirmed as a real scenario on this very machine's history (Docker only recently available
via Colima) — Module A (change analysis) and Module B (failure simulation) have zero Docker
or Postgres dependency by construction, so this requirement is straightforward to satisfy:
those modules only need the `uv`-managed Python environment.

## What is NOT yet built

Everything in Modules A/B/C, the shared platform (models, policy engine, SQLite persistence,
API, CLI), and all tests. Milestone 1 starts that work after this audit is reviewed.

## Planned first-run commands (not functional yet)

These are the target commands once Milestone 1 (foundation) and Milestone 2 (Module A) land —
listed now so the roadmap's acceptance criteria are concrete, not because they run today:

```bash
# Milestone 1+
uv sync                       # create venv, install deps from pyproject.toml/uv.lock
uv run pytest                 # run unit test suite
uv run infraguard --help      # CLI entry point

# Milestone 2 (Module A demo)
uv run infraguard analyze-change --plan examples/terraform/plan.json
```

No command above has been executed as a real InfraGuard command yet (`uv`, `docker`,
`terraform`, `git` version checks above were run directly against the OS to audit tooling,
not against this project).
