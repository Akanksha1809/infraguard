# Threat Model

Scope: InfraGuard is a local analysis tool, not a service that manages real infrastructure.
It never calls a cloud provider API, never holds cloud credentials, and never runs
`terraform apply`/`terraform destroy`. The threats worth modeling are correspondingly
narrower than for a production control plane — but real, since it does parse
attacker-influenceable files and run subprocesses.

## Inputs, and how much they're trusted

| Input | Where it comes from | Trust level |
|---|---|---|
| Terraform plan JSON (Module A) | A file path (CLI) or a JSON body (API) | Untrusted structurally — parsed defensively, never executed. |
| Topology YAML/JSON (Module B) | Same | Untrusted structurally. |
| Recovery policy / evidence YAML/JSON (Module C) | Same | Untrusted structurally. |
| Policy override YAML (Module A) | A file path | Untrusted; validated with the same Pydantic schema as everything else. |
| `--as-of` / API `as_of` (Module C) | CLI flag / API field | Low risk (a timestamp); parsed via `datetime.fromisoformat`, rejected if malformed. |

None of these inputs are ever passed to a shell, `eval`'d, or used to construct a dynamic
import path. They are parsed as JSON/YAML into typed Pydantic models; anything that doesn't
fit the schema is a structured validation error, not a crash (see each module's docs:
CHANGE_ANALYSIS.md / FAILURE_SIMULATION.md / DISASTER_RECOVERY.md's "Validation" sections).

## Sensitive data

- **Terraform plan values** can legitimately contain secrets (database passwords, API
  keys) that a provider embedded in `before`/`after`. These are redacted before they ever
  reach a report or get logged — see CHANGE_ANALYSIS.md's "Secret redaction" section for
  the two-signal approach (Terraform's own sensitivity marks + a key-name heuristic).
  **This is the one place in the codebase where mishandling would have real consequences**,
  so it has its own dedicated test file
  (`tests/unit/change_analysis/test_redaction.py`).
- **Recovery evidence** (Module C) is not expected to carry secrets in normal use, but a
  `location` field on a `BackupEvidence` is free text and is not redacted — document your
  own backups' storage locations without embedding credentials in them. This is stated
  here rather than silently assumed safe.
- **The recovery lab's Postgres credentials** (`docker/recovery_lab/docker-compose.yml`,
  `lab/constants.py`) are a hardcoded, publicly-committed, localhost-only password for a
  throwaway container with no real data. This is a deliberate choice, not an oversight —
  see DESIGN_DECISIONS.md.
- **Structured logging** (`logging_config.py`) logs request/response metadata, not request
  bodies — a Terraform plan or recovery evidence document is never logged verbatim, so
  redaction failures in a report wouldn't be compounded by also leaking into logs.

## Trust boundaries

1. **CLI ↔ local filesystem.** The CLI reads files the user names explicitly (`--plan`,
   `--topology`, `--policy`, `--evidence`). Size limits exist on every module's file loader
   (`MAX_PLAN_SIZE_BYTES`, `MAX_TOPOLOGY_SIZE_BYTES`, `MAX_DOCUMENT_SIZE_BYTES`) to bound
   memory/parse time against an oversized file.
2. **API ↔ network.** `uvicorn` binds to `127.0.0.1` by default (`infraguard serve`); a
   caller must explicitly pass `--host` to expose it further. Every POST endpoint enforces
   the same size limits as the CLI via a `Content-Length` check before parsing the body.
3. **InfraGuard ↔ Docker daemon** (Module C's optional lab only). This is the widest
   boundary in the codebase: the lab issues real `docker compose` / `docker exec` commands.
   It is scoped as narrowly as code can make it — see "Lab-specific threats" below.
4. **InfraGuard ↔ SQLite.** All queries are parameterized (`?` placeholders); no SQL is
   ever built by string-formatting user input. The one place a resource "name" is
   interpolated into SQL text is `lab/dataset.py`'s seed data — and that data is entirely
   code-generated (deterministic synthetic rows), never derived from external input.

## Lab-specific threats (Module C's local Docker lab)

This is the part of the codebase with the most real-world blast-radius potential, because
it runs real subprocesses against a real Docker daemon — see docs/DISASTER_RECOVERY.md's
"Local recovery lab" section for the full design. Threats considered:

- **Could the lab be pointed at the user's real Postgres or an unrelated container?** No —
  project name, compose file path, container name, database name, and table name are all
  hardcoded constants (`lab/constants.py`), never CLI flags, env vars, or request
  parameters. There is no code path that accepts an external project/container name.
- **Could the "controlled data-loss scenario" escalate to something broader?**
  `induce_data_loss()` is exactly one hardcoded `TRUNCATE TABLE orders;` statement against
  the lab's own database. It takes no parameters.
- **Could teardown remove something outside the lab?** `stop_lab()` calls
  `docker compose -p infraguard-recovery-lab ... down -v`, which only ever affects
  resources carrying that project name — verified by actually running it on a machine with
  several unrelated pre-existing containers and confirming only the lab's own container and
  volume were removed (see IMPLEMENTATION_STATUS.md's Milestone 5 section for the literal
  before/after `docker ps`/`docker volume ls` check).
- **Does backup/restore need secrets on the host?** No — `pg_dump`/`pg_restore`/`psql` run
  *inside* the container via `docker exec`, so no local PostgreSQL client or credential
  file is ever needed on the host.

## What InfraGuard explicitly does not defend against

- A malicious Docker daemon or a compromised `postgres:16-alpine` image — InfraGuard trusts
  whatever Docker image it's told to pull, like any tool that uses Docker.
- Someone with shell access to the machine while a drill is running (they could, trivially,
  `docker exec` into the same container themselves — no isolation beyond what Docker itself
  provides).
- Terraform plan files or topology files from a source the user doesn't already trust
  enough to read on their own machine; InfraGuard parses them defensively (no code
  execution, no deserialization of arbitrary Python objects — only `yaml.safe_load`/
  `json.loads` and Pydantic validation) but does not sandbox the parsing process itself.
