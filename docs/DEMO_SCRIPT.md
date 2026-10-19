# Demo Script

A reproducible, interview-ready walkthrough of InfraGuard. `make demo` (`scripts/demo.sh`)
runs every command below in sequence against the committed example inputs — nothing here
depends on the interviewer's own environment beyond `uv` and, optionally, Docker.

```bash
git clone <this repo> && cd infraguard
make install
make test      # 203 tests, ~18s — optional, but a reasonable "prove it works" first step
make demo
```

## The pitch (30 seconds)

"InfraGuard answers three questions an SRE actually asks before a risky change: *can this
Terraform change break something*, *what happens if a piece of my infrastructure fails*,
and *can I actually recover if disaster strikes* — not just 'do I have backups.' All three
run locally, no cloud account, no API key, and nothing here claims more certainty than the
static analysis actually supports."

## Module A — Terraform Change Impact Analysis

```bash
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json
```

**Say:** "This `plan.json` isn't hand-written — it's the real output of
`terraform init && terraform plan -out=tfplan && terraform show -json tfplan > plan.json`
against a local-only Terraform config using the `random`/`local` providers (no cloud
account needed to regenerate it yourself)."

**Point at:** the `unknown_after_values` findings (every resource has attributes only
known after apply — a true gap, not a false positive) and the policy decision line
(`warn`, exit code 0). Then, optionally:

```bash
uv run infraguard analyze-change --plan tests/fixtures/change_analysis/delete_database.json
```

**Say:** "This one deletes a database — CRITICAL severity, exit code 1. The decision always
names which findings triggered it, never an unexplained score."

## Module B — Failure-Domain Simulation

```bash
uv run infraguard simulate-failure --topology examples/topologies/fragile-single-instance.yaml --failure app
uv run infraguard simulate-failure --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml --failure db
uv run infraguard simulate-failure --topology examples/topologies/multi-zone-redundant.yaml --failure-domain zone-a
```

**Say, while pointing at the three outputs in turn:** "Same client-to-database shape, three
redundancy designs. First one: losing the single app instance takes down everything above
it — total outage. Second one: the app tier *is* redundant, two instances, but they share
one database with no redundancy of its own — so losing the database still cascades to a
total outage, because tier-level redundancy alone doesn't save you from a shared-dependency
bottleneck. Third one: every tier is duplicated across two zones — losing an entire zone at
once produces **zero cascaded findings**. Same simulator, same code path, genuinely
different results because the topology is genuinely different."

## Module C — Disaster Recovery Readiness

```bash
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence examples/recovery/evidence.json --as-of 2026-10-19T12:00:00Z
```

**Say:** "Six workloads, six different outcomes, on purpose. The one I'd point to first is
`billing-db`: it has a backup, the backup passed its integrity check — and it's still
`insufficient_evidence`, because **nobody has ever actually tested a restore**. A backup's
existence is never treated as evidence it's recoverable — that's the whole point of this
module."

**If Docker is available**, show the real thing instead of a fixture:

```bash
uv run infraguard recovery-lab drill --workload-id orders-db \
    --policy examples/recovery/policy.yaml --evidence-out /tmp/live-evidence.json
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence /tmp/live-evidence.json
uv run infraguard recovery-lab stop
```

**Say:** "That just spun up a real disposable Postgres container, backed it up, truncated
the table, restored the backup, and verified a checksum — for real, not a fixture. The
resulting evidence says `source: live_lab`, and the readiness report labels it as such
explicitly rather than ever implying it's equivalent to the earlier fixture-based result."

## Platform integration

```bash
uv run infraguard runs
uv run infraguard report --run-id <any id from the list above>
uv run infraguard policy
```

**Say:** "Every run from every module just persisted to one SQLite history, retrievable by
id through the CLI or the same API — `GET /api/v1/reports/{run_id}`. And `policy` shows
you exactly which thresholds are actually configurable (Module A's) versus which rules are
fixed (Modules B and C) — stated honestly rather than pretending one unified engine exists."

## If asked "what would you add next"

Point at [docs/ROADMAP.md](ROADMAP.md)'s "Not planned unless a real need appears" section
and [docs/DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) — both name specific things left out on
purpose (a database-replacement data-loss scenario alongside the truncate one, nested-module
Terraform dependency resolution, an API-triggered lab drill) and why, which is usually a
stronger answer than a vague "more features."
