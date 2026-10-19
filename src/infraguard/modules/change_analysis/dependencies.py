"""Extract a resource dependency graph from a Terraform plan's `configuration` block.

Scope, stated plainly rather than silently assumed: this reads `depends_on` and the
implicit `references` Terraform records for each configuration expression, for **root
module resources only**. Resources inside a child module (`module.x.aws_instance.y`) are
not resolved — that needs recursive traversal of `module_calls`, which this version does
not implement. When that happens we emit a `ParseWarning` rather than pretending the
dependency graph is complete.
"""

import re
from typing import Any

from infraguard.modules.change_analysis.models import ParseWarning

_NON_RESOURCE_PREFIXES = {"var", "local", "each", "count", "path", "terraform", "self", "module"}
_INDEX_SUFFIX = re.compile(r"\[[^\]]*\]$")


def strip_index(address: str) -> str:
    """"aws_instance.web[0]" -> "aws_instance.web"."""
    return _INDEX_SUFFIX.sub("", address)


def _reference_to_base_address(reference: str) -> str | None:
    segments = reference.split(".")
    if not segments:
        return None
    if segments[0] in _NON_RESOURCE_PREFIXES:
        return None
    if segments[0] == "data":
        if len(segments) < 3:
            return None
        return f"data.{segments[1]}.{segments[2]}"
    if len(segments) < 2:
        return None
    return f"{segments[0]}.{segments[1]}"


def _collect_references(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        refs = node.get("references")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str):
                    base = _reference_to_base_address(ref)
                    if base:
                        found.add(base)
        for value in node.values():
            _collect_references(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_references(item, found)


def extract_base_dependency_edges(
    configuration: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    """Returns (dependent_base_address, depends_on_base_address) pairs, root module only."""
    if not isinstance(configuration, dict):
        return []
    root_module = configuration.get("root_module")
    if not isinstance(root_module, dict):
        return []
    resources = root_module.get("resources")
    if not isinstance(resources, list):
        return []

    edges: list[tuple[str, str]] = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        address = resource.get("address")
        if not isinstance(address, str):
            continue

        depends_on = resource.get("depends_on")
        if isinstance(depends_on, list):
            for dep in depends_on:
                if isinstance(dep, str):
                    edges.append((address, strip_index(dep)))

        referenced: set[str] = set()
        _collect_references(resource.get("expressions"), referenced)
        for base in referenced:
            if base != address:
                edges.append((address, base))

    return edges


def expand_edges_to_resource_changes(
    base_edges: list[tuple[str, str]], all_addresses: list[str]
) -> list[tuple[str, str]]:
    """Map base-address edges onto the actual (possibly indexed) resource_change addresses."""
    by_base: dict[str, list[str]] = {}
    for address in all_addresses:
        by_base.setdefault(strip_index(address), []).append(address)

    expanded: list[tuple[str, str]] = []
    for dependent_base, dependency_base in base_edges:
        for dependent in by_base.get(dependent_base, []):
            for dependency in by_base.get(dependency_base, []):
                expanded.append((dependent, dependency))
    return expanded


def module_scoped_warning_if_needed(all_addresses: list[str]) -> ParseWarning | None:
    if any(address.startswith("module.") for address in all_addresses):
        return ParseWarning(
            code="module_scoped_dependencies_unsupported",
            message=(
                "One or more resources are inside a child module (address starts with "
                "'module.'). Dependency extraction only resolves root-module "
                "configuration, so dependency edges for these resources may be "
                "incomplete. This is a known limitation, not a confirmed absence of "
                "dependencies."
            ),
        )
    return None
