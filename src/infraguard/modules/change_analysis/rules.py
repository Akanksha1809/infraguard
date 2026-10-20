"""Deterministic risk rules. Each rule is a pure function of one `ResourceChange` (plus
shared context like the dependency graph) to a list of `Finding`s — no hidden state, no
randomness, so the same plan always produces the same findings.

`rc.before`/`rc.after` are already redacted by `parser.py` before a `ResourceChange` ever
reaches a rule (see `redaction.py`), so including them in a finding's `evidence` — as
`destructive_delete` and `destructive_replace` do, since a reviewer deciding whether a
deletion/replacement is intentional needs to see what's actually changing — never risks
leaking a secret value into a report.
"""

from dataclasses import dataclass

import networkx as nx

from infraguard.core.graph import dependents_of
from infraguard.core.models import Confidence, Finding, Severity
from infraguard.modules.change_analysis.categories import categorize
from infraguard.modules.change_analysis.models import (
    ChangeAction,
    ParsedPlan,
    ResourceCategory,
    ResourceChange,
)

_DESTRUCTIVE_SEVERITY: dict[ResourceCategory, Severity] = {
    ResourceCategory.DATABASE: Severity.CRITICAL,
    ResourceCategory.STORAGE: Severity.CRITICAL,
    ResourceCategory.IAM: Severity.HIGH,
    ResourceCategory.NETWORKING: Severity.HIGH,
    ResourceCategory.COMPUTE: Severity.MEDIUM,
    ResourceCategory.OTHER: Severity.MEDIUM,
}

_SENSITIVE_CATEGORIES = {
    ResourceCategory.DATABASE,
    ResourceCategory.STORAGE,
    ResourceCategory.IAM,
    ResourceCategory.NETWORKING,
}


@dataclass
class RuleContext:
    graph: nx.DiGraph


def rule_destructive_delete(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if rc.action is not ChangeAction.DELETE:
        return []
    category = categorize(rc.resource_type)
    return [
        Finding(
            rule_id="destructive_delete",
            severity=_DESTRUCTIVE_SEVERITY[category],
            confidence=Confidence.CONFIRMED,
            summary=f"{rc.address} will be deleted",
            detail=(
                f"Terraform plans to delete '{rc.address}' ({rc.resource_type}). This is "
                "read directly from the plan's action list, not inferred."
            ),
            affected_resources=[rc.address],
            evidence={
                "action": list(rc.raw_actions),
                "resource_type": rc.resource_type,
                "before": rc.before,
            },
            remediation=(
                "Confirm this deletion is intentional and that any data or downstream "
                "dependents have been migrated or backed up first."
            ),
        )
    ]


def rule_destructive_replace(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if rc.action is not ChangeAction.REPLACE:
        return []
    category = categorize(rc.resource_type)
    ordering = (
        "create-before-destroy"
        if rc.create_before_destroy
        else "destroy-before-create, which can cause downtime between the two steps"
    )
    detail = f"Terraform plans to replace '{rc.address}' ({rc.resource_type}), {ordering}."
    if rc.replace_paths:
        detail += f" Attribute(s) reported as forcing replacement: {', '.join(rc.replace_paths)}."
    else:
        detail += (
            " The plan did not report which attribute forced replacement — treat this as "
            "a full-resource risk rather than a narrowly scoped one; an absent field is "
            "not evidence of a smaller blast radius."
        )
    return [
        Finding(
            rule_id="destructive_replace",
            severity=_DESTRUCTIVE_SEVERITY[category],
            confidence=Confidence.CONFIRMED,
            summary=f"{rc.address} will be replaced ({ordering.split(',')[0]})",
            detail=detail,
            affected_resources=[rc.address],
            evidence={
                "action": list(rc.raw_actions),
                "resource_type": rc.resource_type,
                "replace_paths": rc.replace_paths,
                "before": rc.before,
                "after": rc.after,
            },
            remediation=(
                "Confirm the replacement is intentional. If destroy-before-create, plan "
                "for the resulting downtime; if this resource holds state or data, ensure "
                "it is backed up or migrated first."
            ),
        )
    ]


def rule_sensitive_category_mutation(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if rc.action in (ChangeAction.NO_OP, ChangeAction.READ, ChangeAction.UNKNOWN):
        return []
    category = categorize(rc.resource_type)
    if category not in _SENSITIVE_CATEGORIES:
        return []
    return [
        Finding(
            rule_id="sensitive_category_mutation",
            severity=Severity.MEDIUM,
            confidence=Confidence.HEURISTIC,
            summary=f"{rc.address} ({category.value}) is being modified",
            detail=(
                f"'{rc.address}' matched the {category.value} category by a pattern on its "
                f"resource type ('{rc.resource_type}'), which is a heuristic, not a "
                "guaranteed classification. Changes in this category (database, storage, "
                "IAM, networking) warrant review regardless of action type."
            ),
            affected_resources=[rc.address],
            evidence={"category": category.value, "action": list(rc.raw_actions)},
            remediation="Have someone familiar with this resource's blast radius review the change.",
        )
    ]


def rule_unknown_after_values(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if rc.action in (ChangeAction.NO_OP, ChangeAction.READ, ChangeAction.DELETE):
        return []
    if not rc.after_unknown_paths:
        return []
    shown = rc.after_unknown_paths[:20]
    truncated = len(rc.after_unknown_paths) > 20
    return [
        Finding(
            rule_id="unknown_after_values",
            severity=Severity.MEDIUM,
            confidence=Confidence.CONFIRMED,
            summary=f"{len(rc.after_unknown_paths)} attribute(s) of {rc.address} are unknown until apply",
            detail=(
                f"'{rc.address}' has {len(rc.after_unknown_paths)} attribute(s) whose final "
                "value Terraform cannot determine from this plan alone (they depend on "
                "values only known after apply). InfraGuard cannot assess risk for these "
                "specific attributes from static plan data — this is a gap, not a clean bill "
                "of health."
            ),
            affected_resources=[rc.address],
            evidence={
                "unknown_paths": shown,
                "unknown_path_count": len(rc.after_unknown_paths),
                "truncated": truncated,
            },
            remediation="Re-run analysis after apply, or inspect these attributes manually.",
        )
    ]


def rule_unsupported_resource_type(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if categorize(rc.resource_type) is not ResourceCategory.OTHER:
        return []
    if rc.action not in (ChangeAction.DELETE, ChangeAction.REPLACE):
        return []
    return [
        Finding(
            rule_id="unsupported_resource_type",
            severity=Severity.MEDIUM,
            confidence=Confidence.UNKNOWN,
            summary=f"'{rc.resource_type}' has no category-specific rule",
            detail=(
                f"'{rc.address}' ({rc.resource_type}) did not match any known resource "
                "category pattern. InfraGuard has no resource-specific risk knowledge for "
                "it; the absence of a specific finding here is not evidence that this "
                "destructive change is safe."
            ),
            affected_resources=[rc.address],
            evidence={"resource_type": rc.resource_type, "action": list(rc.raw_actions)},
            remediation="Manually review this change; it falls outside InfraGuard's modeled categories.",
        )
    ]


def rule_dependents_affected(rc: ResourceChange, ctx: RuleContext) -> list[Finding]:
    if rc.action not in (ChangeAction.DELETE, ChangeAction.REPLACE):
        return []
    dependents = dependents_of(ctx.graph, rc.address)
    if not dependents:
        return []
    verb = "deleted" if rc.action is ChangeAction.DELETE else "replaced"
    return [
        Finding(
            rule_id="dependents_affected",
            severity=Severity.HIGH,
            confidence=Confidence.HEURISTIC,
            summary=f"{len(dependents)} resource(s) depend on {rc.address}",
            detail=(
                f"Based on static dependency references found in the plan's configuration, "
                f"the following resource(s) depend on '{rc.address}', which is being "
                f"{verb}. Dependency extraction covers explicit depends_on and implicit "
                "references within the root module only — see docs/CHANGE_ANALYSIS.md for "
                "what is and is not resolved."
            ),
            affected_resources=sorted(dependents),
            evidence={"dependency_source": "static reference analysis, root module only"},
            remediation="Review each affected resource to confirm it tolerates this change.",
        )
    ]


def rule_parse_warnings(parsed_plan: ParsedPlan) -> list[Finding]:
    findings = []
    for warning in parsed_plan.warnings:
        findings.append(
            Finding(
                rule_id=f"parse_warning.{warning.code}",
                severity=Severity.MEDIUM,
                confidence=Confidence.UNKNOWN,
                summary=f"Parse warning: {warning.code}",
                detail=warning.message,
                affected_resources=[warning.resource_address] if warning.resource_address else [],
                evidence={"code": warning.code},
                remediation=(
                    "Fix the input plan JSON, or treat the skipped/ambiguous data as "
                    "unassessed rather than safe."
                ),
            )
        )
    return findings


_RESOURCE_RULES = (
    rule_destructive_delete,
    rule_destructive_replace,
    rule_sensitive_category_mutation,
    rule_unknown_after_values,
    rule_unsupported_resource_type,
    rule_dependents_affected,
)


def run_rules(parsed_plan: ParsedPlan, graph: nx.DiGraph) -> list[Finding]:
    ctx = RuleContext(graph=graph)
    findings: list[Finding] = []
    for resource_change in parsed_plan.resource_changes:
        for rule in _RESOURCE_RULES:
            findings.extend(rule(resource_change, ctx))
    findings.extend(rule_parse_warnings(parsed_plan))
    return findings
