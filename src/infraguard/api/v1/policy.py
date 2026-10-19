from typing import Any

from fastapi import APIRouter

from infraguard.core.rule_registry import RULES
from infraguard.modules.change_analysis.policy import PolicyConfig

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("")
def get_policy() -> dict[str, Any]:
    default_policy = PolicyConfig()
    return {
        "change_analysis_default_policy": default_policy.model_dump(mode="json"),
        "note": (
            "Only change_analysis has a configurable severity-threshold CI policy "
            "(overridable per-run). failure_simulation and disaster_recovery have a "
            "fixed rule set, listed below."
        ),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "module": rule.module,
                "default_severity": rule.default_severity,
                "description": rule.description,
            }
            for rule in RULES
        ],
    }
