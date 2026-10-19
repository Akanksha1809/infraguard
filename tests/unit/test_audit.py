from pathlib import Path

from infraguard.core.audit import list_events, record_event
from infraguard.storage.db import init_db


def test_record_and_list_events(db_path: Path) -> None:
    init_db(db_path)

    record_event(db_path, "run.started", {"module": "change_analysis"}, module="change_analysis")
    record_event(db_path, "run.completed", {"result": "ok"}, module="change_analysis")

    events = list_events(db_path)
    assert len(events) == 2
    assert events[0]["event_type"] == "run.completed"
    assert events[0]["payload"] == {"result": "ok"}
    assert events[1]["event_type"] == "run.started"
