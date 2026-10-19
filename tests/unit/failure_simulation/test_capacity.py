from infraguard.modules.failure_simulation.capacity import compute_capacity
from infraguard.modules.failure_simulation.validator import parse_topology


def test_capacity_computed_when_all_members_declare_it(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    results = compute_capacity(topology, down={"app-1"})
    app_group = next(r for r in results if r.label == "app")
    assert app_group.total_capacity == 100
    assert app_group.surviving_capacity == 50
    assert app_group.percent_remaining == 50.0


def test_capacity_unknown_when_any_member_missing_it(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("missing_capacity.yaml"))
    results = compute_capacity(topology, down=set())
    app_group = next(r for r in results if r.label == "app")
    assert app_group.percent_remaining is None
    assert app_group.note is not None
    assert "Incomplete" in app_group.note


def test_full_capacity_when_nothing_down(load_fixture) -> None:
    topology, _ = parse_topology(load_fixture("redundant_pair.yaml"))
    results = compute_capacity(topology, down=set())
    app_group = next(r for r in results if r.label == "app")
    assert app_group.percent_remaining == 100.0
