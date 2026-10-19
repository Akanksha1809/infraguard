from infraguard.core.rule_registry import RULES


def test_rule_ids_are_unique() -> None:
    rule_ids = [r.rule_id for r in RULES]
    assert len(rule_ids) == len(set(rule_ids))


def test_every_rule_has_a_module_and_description() -> None:
    for rule in RULES:
        assert rule.module in ("change_analysis", "failure_simulation", "disaster_recovery")
        assert rule.description
        assert rule.default_severity


def test_all_three_modules_are_represented() -> None:
    modules = {r.module for r in RULES}
    assert modules == {"change_analysis", "failure_simulation", "disaster_recovery"}
