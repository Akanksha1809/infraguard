"""Entry point tying parsing, the dependency graph, risk rules, scoring, and policy
together into one `Report`. This is the only function the CLI and API call.
"""

import json
from pathlib import Path
from typing import Any

from infraguard.core.graph import build_graph
from infraguard.core.models import Report
from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.parser import parse_plan
from infraguard.modules.change_analysis.policy import PolicyConfig, evaluate_policy
from infraguard.modules.change_analysis.risk_score import compute_risk_score
from infraguard.modules.change_analysis.rules import run_rules

MAX_PLAN_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB; a hand-authored plan is never this large.


def analyze_plan(
    raw_plan: dict[str, Any], policy: PolicyConfig | None = None, *, source: str | None = None
) -> Report:
    policy = policy or PolicyConfig()
    parsed = parse_plan(raw_plan)

    all_addresses = [rc.address for rc in parsed.resource_changes]
    graph = build_graph(all_addresses, parsed.dependency_edges)

    findings = run_rules(parsed, graph)
    score, score_explanation = compute_risk_score(findings)
    decision = evaluate_policy(findings, policy)

    action_counts: dict[str, int] = {}
    for rc in parsed.resource_changes:
        action_counts[rc.action.value] = action_counts.get(rc.action.value, 0) + 1

    assumptions = [
        "Resource categories (database, storage, IAM, networking, compute) are determined "
        "by substring pattern matching on the resource type name, not a real provider schema.",
        "Dependency edges come from Terraform's own 'references' and 'depends_on' metadata "
        "in the plan's configuration block, root module only.",
        "A missing or absent field in the plan is never treated as evidence that a change "
        "is safe.",
    ]
    limitations = [
        "Resources inside child modules are not resolved for dependency analysis (see any "
        "'module_scoped_dependencies_unsupported' finding).",
        "Attributes unknown until apply cannot be risk-assessed from the plan alone (see any "
        "'unknown_after_values' finding).",
        "This analysis is based solely on the supplied plan JSON; it does not inspect actual "
        "cloud state, IAM policy semantics, or network reachability.",
    ]
    next_steps = [
        "Review each HIGH or CRITICAL finding before applying this plan.",
        "Re-run analysis if the plan is regenerated, since attribute values and dependencies "
        "may change.",
    ]
    if decision.decision == "error":
        next_steps.insert(0, "Fix the input plan JSON — this run failed closed on invalid input.")

    return Report(
        module="change_analysis",
        inputs={
            "source": source,
            "terraform_version": parsed.terraform_version,
            "format_version": parsed.format_version,
            "resource_change_count": len(parsed.resource_changes),
            "action_counts": action_counts,
            "risk_score": {"score": score, "explanation": score_explanation},
            "policy": policy.model_dump(mode="json"),
        },
        findings=findings,
        assumptions=assumptions,
        limitations=limitations,
        policy_decision=decision,
        next_steps=next_steps,
    )


def analyze_plan_file(path: Path, policy: PolicyConfig | None = None) -> Report:
    if not path.exists():
        raise InputValidationError(f"Plan file not found: {path}")

    size = path.stat().st_size
    if size > MAX_PLAN_SIZE_BYTES:
        raise InputValidationError(
            f"Plan file '{path}' is {size} bytes, exceeding the {MAX_PLAN_SIZE_BYTES}-byte limit.",
            details={"size_bytes": size, "max_bytes": MAX_PLAN_SIZE_BYTES},
        )

    try:
        raw_plan = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"Plan file '{path}' is not valid JSON: {exc}") from exc

    return analyze_plan(raw_plan, policy, source=str(path))
