#!/usr/bin/env bash
# Reproducible demo tour of all three InfraGuard modules, run from a clean checkout.
# See docs/DEMO_SCRIPT.md for the narrated, interview-ready walkthrough of the same steps.
#
# Nothing here is fabricated: every command below is the real CLI, run against the
# committed example inputs. `set -e` is on throughout except around the one step that is
# EXPECTED to exit non-zero (disaster-recovery assessment: some example workloads are
# deliberately not ready, by design — see docs/DISASTER_RECOVERY.md).
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=./demo-output
DB="$OUT/infraguard.db"
rm -rf "$OUT"
mkdir -p "$OUT"

section() {
    echo
    echo "================================================================"
    echo "  $1"
    echo "================================================================"
}

section "1/4  Terraform Change Impact Analysis (Module A)"
echo "+ infraguard analyze-change --plan examples/terraform/sample/plan.json"
uv run infraguard analyze-change --plan examples/terraform/sample/plan.json \
    --out "$OUT" --db-path "$DB"

section "2/4  Failure-Domain Simulation (Module B) — 3 topologies, 3 different outcomes"
echo "+ fragile-single-instance.yaml, failing 'app' (expect full cascade)"
uv run infraguard simulate-failure --topology examples/topologies/fragile-single-instance.yaml \
    --failure app --out "$OUT" --db-path "$DB"
echo
echo "+ redundant-app-shared-db-bottleneck.yaml, failing 'db' (expect full cascade despite app-tier redundancy)"
uv run infraguard simulate-failure \
    --topology examples/topologies/redundant-app-shared-db-bottleneck.yaml \
    --failure db --out "$OUT" --db-path "$DB"
echo
echo "+ multi-zone-redundant.yaml, failing failure-domain 'zone-a' (expect ZERO cascade)"
uv run infraguard simulate-failure --topology examples/topologies/multi-zone-redundant.yaml \
    --failure-domain zone-a --out "$OUT" --db-path "$DB"

section "3/4  Disaster Recovery Readiness (Module C) — 6 workloads, 6 distinct outcomes"
echo "+ infraguard assess-recovery (exit code 1 expected: 4/6 example workloads are not ready, by design)"
set +e
uv run infraguard assess-recovery --policy examples/recovery/policy.yaml \
    --evidence examples/recovery/evidence.json --as-of 2026-10-19T12:00:00Z \
    --out "$OUT" --db-path "$DB"
assess_rc=$?
set -e
echo "(exit code: $assess_rc — expected non-zero; see the per-workload breakdown above)"

section "4/4  Platform integration — run history and policy inspection"
echo "+ infraguard runs"
uv run infraguard runs --db-path "$DB"
echo
echo "+ infraguard policy --module change_analysis"
uv run infraguard policy --module change_analysis

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    section "Bonus: live Docker/Postgres recovery lab (Docker detected)"
    echo "+ infraguard recovery-lab drill --workload-id orders-db ..."
    uv run infraguard recovery-lab drill --workload-id orders-db \
        --policy examples/recovery/policy.yaml \
        --evidence-out "$OUT/live-evidence.json" --backups-dir "$OUT/lab-backups"
    echo
    echo "+ infraguard recovery-lab stop (tears down only this lab's own container/volume)"
    uv run infraguard recovery-lab stop
else
    section "Bonus: live Docker/Postgres recovery lab — SKIPPED (Docker not available here)"
    echo "assess-recovery above still worked fully using fixture evidence; see docs/DISASTER_RECOVERY.md."
fi

section "Demo complete"
echo "Generated reports are in $OUT/ (gitignored; re-run this script any time)."
