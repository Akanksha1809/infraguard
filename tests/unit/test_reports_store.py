from pathlib import Path

from infraguard.core.models import Report
from infraguard.core.persistence import persist_report
from infraguard.core.reports_store import list_runs, load_report, save_report
from infraguard.storage.db import init_db


def test_save_and_load_report_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    report = Report(module="change_analysis")

    save_report(db_path, report)
    loaded = load_report(db_path, report.run_id)

    assert loaded is not None
    assert loaded.run_id == report.run_id
    assert loaded.module == "change_analysis"


def test_load_report_returns_none_for_unknown_run_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    assert load_report(db_path, "does-not-exist") is None


def test_list_runs_filters_by_module_and_orders_recent_first(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    r1 = Report(module="change_analysis")
    r2 = Report(module="failure_simulation")
    save_report(db_path, r1)
    save_report(db_path, r2)

    all_runs = list_runs(db_path)
    assert {r["run_id"] for r in all_runs} == {r1.run_id, r2.run_id}

    filtered = list_runs(db_path, module="change_analysis")
    assert [r["run_id"] for r in filtered] == [r1.run_id]


def test_list_runs_respects_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    for _ in range(5):
        save_report(db_path, Report(module="change_analysis"))
    assert len(list_runs(db_path, limit=2)) == 2


def test_persist_report_initializes_schema_on_a_fresh_path(tmp_path: Path) -> None:
    # persist_report must work even if init_db was never called first (the CLI's only path).
    db_path = tmp_path / "brand-new.db"
    assert not db_path.exists()
    report = Report(module="disaster_recovery")

    persist_report(db_path, report)

    loaded = load_report(db_path, report.run_id)
    assert loaded is not None
    assert loaded.module == "disaster_recovery"


def test_persist_report_records_an_audit_event(tmp_path: Path) -> None:
    from infraguard.core.audit import list_events

    db_path = tmp_path / "test.db"
    report = Report(module="change_analysis")

    persist_report(db_path, report)

    events = list_events(db_path)
    assert any(e["event_type"] == "change_analysis.run_completed" for e in events)
