"""Parse a Terraform `show -json` plan document into a `ParsedPlan`.

Fatal structural problems (not a JSON object, no `resource_changes` list) raise
`InputValidationError` — there is nothing safe to report on. Per-resource problems (a
single malformed `resource_changes` entry) are recoverable: that entry is skipped and
recorded as a `ParseWarning` so the caller's policy can decide whether skipped entries are
acceptable, rather than the parser silently deciding for them.
"""

from typing import Any

from infraguard.errors import InputValidationError
from infraguard.modules.change_analysis.dependencies import (
    expand_edges_to_resource_changes,
    extract_base_dependency_edges,
    module_scoped_warning_if_needed,
)
from infraguard.modules.change_analysis.models import (
    ChangeAction,
    ParsedPlan,
    ParseWarning,
    ResourceChange,
)
from infraguard.modules.change_analysis.redaction import redact_value

_ACTION_MAP: dict[tuple[str, ...], ChangeAction] = {
    ("no-op",): ChangeAction.NO_OP,
    ("create",): ChangeAction.CREATE,
    ("read",): ChangeAction.READ,
    ("update",): ChangeAction.UPDATE,
    ("delete",): ChangeAction.DELETE,
    ("delete", "create"): ChangeAction.REPLACE,
    ("create", "delete"): ChangeAction.REPLACE,
}


def _parse_resource_change(entry: dict[str, Any]) -> tuple[ResourceChange | None, ParseWarning | None]:
    address = entry.get("address")
    if not isinstance(address, str) or not address:
        return None, ParseWarning(
            code="resource_change_missing_address",
            message="A resource_changes entry has no usable 'address'; it was skipped.",
            resource_address=None,
        )

    resource_type = entry.get("type")
    resource_name = entry.get("name")
    mode = entry.get("mode")
    change = entry.get("change")

    if not isinstance(resource_type, str) or not isinstance(resource_name, str):
        return None, ParseWarning(
            code="resource_change_missing_type_or_name",
            message=f"Resource '{address}' is missing 'type' or 'name'; it was skipped.",
            resource_address=address,
        )
    if not isinstance(mode, str):
        mode = "managed"
    if not isinstance(change, dict):
        return None, ParseWarning(
            code="resource_change_missing_change_block",
            message=f"Resource '{address}' has no 'change' block; it was skipped.",
            resource_address=address,
        )

    raw_actions = change.get("actions")
    if not isinstance(raw_actions, list) or not all(isinstance(a, str) for a in raw_actions):
        return None, ParseWarning(
            code="resource_change_invalid_actions",
            message=f"Resource '{address}' has an invalid 'actions' list; it was skipped.",
            resource_address=address,
        )

    action = _ACTION_MAP.get(tuple(raw_actions), ChangeAction.UNKNOWN)
    warning = None
    if action is ChangeAction.UNKNOWN:
        warning = ParseWarning(
            code="unrecognized_action_combination",
            message=(
                f"Resource '{address}' has an action combination {raw_actions!r} that is "
                "not recognized. Treating as UNKNOWN rather than guessing create/update/"
                "delete semantics."
            ),
            resource_address=address,
        )

    before_redacted, before_paths = redact_value(change.get("before"), change.get("before_sensitive"))
    after_redacted, after_paths = redact_value(change.get("after"), change.get("after_sensitive"))

    after_unknown_paths = _flatten_unknown(change.get("after_unknown"))

    resource_change = ResourceChange(
        address=address,
        module_address=entry.get("module_address"),
        resource_type=resource_type,
        resource_name=resource_name,
        mode=mode,
        raw_actions=raw_actions,
        action=action,
        create_before_destroy=tuple(raw_actions) == ("create", "delete"),
        before=before_redacted,
        after=after_redacted,
        after_unknown_paths=after_unknown_paths,
        sensitive_paths=sorted(set(before_paths) | set(after_paths)),
        replace_paths=[
            ".".join(str(p) for p in path) if isinstance(path, list) else str(path)
            for path in (change.get("replace_paths") or [])
        ],
    )
    return resource_change, warning


def _flatten_unknown(node: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if node is True:
        paths.append(prefix or "<root>")
    elif isinstance(node, dict):
        for key, value in node.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            paths.extend(_flatten_unknown(value, child_prefix))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            paths.extend(_flatten_unknown(value, f"{prefix}[{i}]"))
    return paths


def parse_plan(raw: Any) -> ParsedPlan:
    if not isinstance(raw, dict):
        raise InputValidationError(
            "Plan JSON root must be an object (as produced by 'terraform show -json')."
        )

    if "resource_changes" not in raw:
        raise InputValidationError(
            "Plan JSON is missing the required 'resource_changes' field. A valid "
            "'terraform show -json' plan always includes it, even as an empty list — "
            "its absence means this is not a usable plan document, not that there are "
            "zero changes."
        )
    resource_changes_raw = raw["resource_changes"]
    if not isinstance(resource_changes_raw, list):
        raise InputValidationError(
            "Plan JSON 'resource_changes' must be a list.",
            details={"found_type": type(resource_changes_raw).__name__},
        )

    resource_changes: list[ResourceChange] = []
    warnings: list[ParseWarning] = []
    for entry in resource_changes_raw:
        if not isinstance(entry, dict):
            warnings.append(
                ParseWarning(
                    code="resource_change_not_an_object",
                    message="A resource_changes entry was not a JSON object; it was skipped.",
                )
            )
            continue
        resource_change, warning = _parse_resource_change(entry)
        if resource_change is not None:
            resource_changes.append(resource_change)
        if warning is not None:
            warnings.append(warning)

    all_addresses = [rc.address for rc in resource_changes]
    base_edges = extract_base_dependency_edges(raw.get("configuration"))
    dependency_edges = expand_edges_to_resource_changes(base_edges, all_addresses)

    module_warning = module_scoped_warning_if_needed(all_addresses)
    if module_warning:
        warnings.append(module_warning)

    return ParsedPlan(
        terraform_version=raw.get("terraform_version"),
        format_version=raw.get("format_version"),
        resource_changes=resource_changes,
        dependency_edges=dependency_edges,
        warnings=warnings,
    )
