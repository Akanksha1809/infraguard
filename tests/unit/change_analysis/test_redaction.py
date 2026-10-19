from infraguard.modules.change_analysis.redaction import REDACTED, redact_value


def test_redacts_terraform_marked_sensitive_scalar() -> None:
    value = {"password": "super-secret", "instance_class": "db.t3.micro"}
    marks = {"password": True}

    redacted, paths = redact_value(value, marks)

    assert redacted["password"] == REDACTED
    assert redacted["instance_class"] == "db.t3.micro"
    assert paths == ["password"]


def test_redacts_unmarked_value_by_key_name_heuristic() -> None:
    value = {"api_token": "unmarked-secret", "name": "app"}
    marks = {}  # Terraform did not mark anything sensitive here.

    redacted, paths = redact_value(value, marks)

    assert redacted["api_token"] == REDACTED
    assert redacted["name"] == "app"
    assert paths == ["api_token"]


def test_redacts_nested_structures() -> None:
    # "connection_settings" does not itself match the key-name heuristic, so this exercises
    # recursive descent following Terraform's nested sensitivity marks.
    value = {"connection_settings": {"username": "admin", "password": "secret"}}
    marks = {"connection_settings": {"password": True}}

    redacted, _ = redact_value(value, marks)

    assert redacted["connection_settings"]["password"] == REDACTED
    assert redacted["connection_settings"]["username"] == "admin"


def test_key_name_heuristic_redacts_whole_subtree() -> None:
    # A key whose *name* looks sensitive (e.g. "credentials") is redacted wholesale, even
    # though Terraform marked nothing — over-redaction is the safe direction here.
    value = {"credentials": {"username": "admin", "password": "secret"}}

    redacted, paths = redact_value(value, marks=None)

    assert redacted["credentials"] == REDACTED
    assert paths == ["credentials"]


def test_redacts_list_items_marked_sensitive() -> None:
    value = {"tags": ["public", "secret-value"]}
    marks = {"tags": [False, True]}

    redacted, paths = redact_value(value, marks)

    assert redacted["tags"] == ["public", REDACTED]
    assert paths == ["tags[1]"]


def test_none_value_passes_through() -> None:
    redacted, paths = redact_value(None, True)
    assert redacted is None
    assert paths == []
