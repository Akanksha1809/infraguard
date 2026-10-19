"""A static, hand-maintained catalog of every rule_id InfraGuard can emit, across all three
modules. This is what `infraguard policy show` / `GET /api/v1/policy` surface as the
"policy inspection" capability: not a single configurable engine (only Module A's
severity thresholds are actually configurable — see `policy_config` below), but a complete,
honest reference of what each module checks and why. Keep this in sync with
docs/POLICY_REFERENCE.md and the per-module rule functions when either changes.
"""

from typing import NamedTuple


class RuleInfo(NamedTuple):
    rule_id: str
    module: str
    default_severity: str
    description: str


RULES: tuple[RuleInfo, ...] = (
    # --- change_analysis ---------------------------------------------------------
    RuleInfo(
        "destructive_delete", "change_analysis", "varies by category (MEDIUM-CRITICAL)",
        "A resource is being deleted.",
    ),
    RuleInfo(
        "destructive_replace", "change_analysis", "varies by category (MEDIUM-CRITICAL)",
        "A resource is being replaced (destroy+create in either order).",
    ),
    RuleInfo(
        "sensitive_category_mutation", "change_analysis", "MEDIUM",
        "A create/update/delete/replace touches a database/storage/IAM/networking resource.",
    ),
    RuleInfo(
        "unknown_after_values", "change_analysis", "MEDIUM",
        "One or more attributes are unknown until apply; risk cannot be fully assessed.",
    ),
    RuleInfo(
        "unsupported_resource_type", "change_analysis", "MEDIUM",
        "A destructive change targets a resource type with no category-specific rule.",
    ),
    RuleInfo(
        "dependents_affected", "change_analysis", "HIGH",
        "Other resources statically depend on one being deleted or replaced.",
    ),
    RuleInfo(
        "parse_warning.*", "change_analysis", "MEDIUM",
        "A resource_changes entry could not be fully parsed; strict policy fails closed on it.",
    ),
    # --- failure_simulation --------------------------------------------------------
    RuleInfo(
        "single_point_of_failure", "failure_simulation", "HIGH",
        "Failing this one component alone causes at least one other component to go down.",
    ),
    RuleInfo(
        "dependency_without_redundancy", "failure_simulation", "MEDIUM",
        "A required dependency's target has no redundancy_group peers.",
    ),
    RuleInfo(
        "component_failed_explicit", "failure_simulation", "HIGH",
        "A component was explicitly failed by the simulated scenario.",
    ),
    RuleInfo(
        "component_down_cascaded", "failure_simulation", "HIGH",
        "A component goes down as a consequence of a required dependency's group being fully down.",
    ),
    RuleInfo(
        "capacity_degraded", "failure_simulation", "MEDIUM",
        "A redundancy group's surviving capacity is reduced but not zero, for this scenario.",
    ),
    RuleInfo(
        "topology_warning.*", "failure_simulation", "LOW-MEDIUM",
        "A structural topology issue: a dependency cycle, a single-member redundancy group, etc.",
    ),
    # --- disaster_recovery -----------------------------------------------------------
    RuleInfo(
        "no_backup_evidence", "disaster_recovery", "CRITICAL",
        "No backup evidence exists for a workload.",
    ),
    RuleInfo(
        "backup_integrity_not_checked", "disaster_recovery", "HIGH",
        "The latest backup's integrity was never checked (unknown, not assumed fine).",
    ),
    RuleInfo(
        "backup_integrity_failed", "disaster_recovery", "CRITICAL",
        "The latest backup explicitly failed its integrity check.",
    ),
    RuleInfo(
        "backup_stale", "disaster_recovery", "HIGH",
        "The latest backup is older than the policy's max_backup_age_hours.",
    ),
    RuleInfo(
        "retention_below_policy", "disaster_recovery", "MEDIUM",
        "A backup's declared retention is below the policy's requirement.",
    ),
    RuleInfo(
        "no_restore_test", "disaster_recovery", "CRITICAL",
        "No restore drill exists at all — a backup's existence is never evidence it's recoverable.",
    ),
    RuleInfo(
        "restore_test_failed_verification", "disaster_recovery", "CRITICAL",
        "Drill(s) exist, but none passed verification.",
    ),
    RuleInfo(
        "restore_test_stale", "disaster_recovery", "HIGH",
        "The latest verified drill is older than the required interval.",
    ),
    RuleInfo(
        "recovery_objective_unmeasured", "disaster_recovery", "MEDIUM",
        "A verified drill didn't record duration/data-loss, so RTO/RPO can't be evaluated.",
    ),
    RuleInfo(
        "recovery_objective_not_met", "disaster_recovery", "CRITICAL",
        "A verified drill's measured duration or data loss exceeds RTO/RPO.",
    ),
    RuleInfo(
        "missing_recovery_dependency", "disaster_recovery", "HIGH",
        "A workload depends on another workload with no recovery policy of its own.",
    ),
    RuleInfo(
        "fixture_based_evidence_used", "disaster_recovery", "LOW",
        "At least one drill behind this result is fixture-sourced, not from the live lab.",
    ),
    RuleInfo(
        "evidence_for_unconfigured_workload", "disaster_recovery", "MEDIUM",
        "Backup/drill evidence references a workload_id with no recovery policy.",
    ),
    RuleInfo(
        "invalid_policy_objective", "disaster_recovery", "HIGH",
        "A policy's rto_minutes or rpo_minutes is zero or negative.",
    ),
)
