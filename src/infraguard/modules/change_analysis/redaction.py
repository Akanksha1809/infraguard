"""Redact sensitive values before they ever reach a report.

Two independent signals are honored, because neither alone is trustworthy:

1. Terraform's own `before_sensitive`/`after_sensitive` marks (from the plan JSON) — these
   are authoritative where present, but a provider can simply fail to mark something
   sensitive.
2. A heuristic key-name pattern (password, secret, token, key, credential, cert, dsn, ...) —
   catches values Terraform didn't mark, at the cost of occasionally over-redacting a
   harmless field. Over-redaction is the safe direction; under-redaction is not.

Per the project's safety rule, a *missing* sensitive mark is never treated as proof a value
is safe to show.
"""

import re
from typing import Any

REDACTED = "***REDACTED***"

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|credential|private[_-]?key|access[_-]?key"
    r"|api[_-]?key|connection[_-]?string|\bdsn\b|cert(ificate)?)",
    re.IGNORECASE,
)


def _redact(value: Any, marks: Any, prefix: str, redacted_paths: list[str]) -> Any:
    if marks is True:
        redacted_paths.append(prefix or "<root>")
        return REDACTED

    if isinstance(value, dict):
        marks_dict = marks if isinstance(marks, dict) else {}
        result = {}
        for key, child_value in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            if SENSITIVE_KEY_PATTERN.search(key):
                redacted_paths.append(child_prefix)
                result[key] = REDACTED
            else:
                result[key] = _redact(
                    child_value, marks_dict.get(key, False), child_prefix, redacted_paths
                )
        return result

    if isinstance(value, list):
        marks_list = marks if isinstance(marks, list) else []
        result = []
        for i, child_value in enumerate(value):
            child_prefix = f"{prefix}[{i}]"
            child_marks = marks_list[i] if i < len(marks_list) else False
            result.append(_redact(child_value, child_marks, child_prefix, redacted_paths))
        return result

    return value


def redact_value(value: Any, marks: Any) -> tuple[Any, list[str]]:
    """Redact `value` using `marks` (Terraform's sensitivity structure, or None/False) plus
    the key-name heuristic. Returns (redacted_value, sorted list of redacted paths).
    """
    if value is None:
        return None, []
    redacted_paths: list[str] = []
    redacted = _redact(value, marks, prefix="", redacted_paths=redacted_paths)
    return redacted, sorted(set(redacted_paths))
