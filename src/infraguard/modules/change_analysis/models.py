"""Models for a parsed Terraform plan. These describe what `terraform show -json` told us —
not yet a risk judgment, which belongs to rules.py.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChangeAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    READ = "read"
    NO_OP = "no-op"
    UNKNOWN = "unknown"


class ResourceCategory(StrEnum):
    """Pattern-matched from the resource `type` string. This is a heuristic, not an
    authoritative provider schema — see docs/CHANGE_ANALYSIS.md for the exact patterns and
    their limitations.
    """

    DATABASE = "database"
    STORAGE = "storage"
    IAM = "iam"
    NETWORKING = "networking"
    COMPUTE = "compute"
    OTHER = "other"


class ParseWarning(BaseModel):
    code: str
    message: str
    resource_address: str | None = None
    fails_closed: bool = True
    """Whether a strict policy should treat this warning as reason to fail closed. True
    (the default) for genuine parse/data problems, where part of the input could not be
    understood at all. False for a known, stated coverage limitation — the input itself is
    fine, InfraGuard's analysis of it is just incomplete in a documented way (e.g. an
    unresolved module-scoped dependency). Defaulting to True keeps "never fail open"
    intact for anything not explicitly marked otherwise."""


class ResourceChange(BaseModel):
    address: str
    module_address: str | None = None
    resource_type: str
    resource_name: str
    mode: str  # "managed" | "data"
    raw_actions: list[str]
    action: ChangeAction
    create_before_destroy: bool = False
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_unknown_paths: list[str] = Field(default_factory=list)
    sensitive_paths: list[str] = Field(default_factory=list)
    replace_paths: list[str] = Field(default_factory=list)


class ParsedPlan(BaseModel):
    terraform_version: str | None = None
    format_version: str | None = None
    resource_changes: list[ResourceChange] = Field(default_factory=list)
    dependency_edges: list[tuple[str, str]] = Field(default_factory=list)
    """Each edge is (dependent_address, depends_on_address)."""
    warnings: list[ParseWarning] = Field(default_factory=list)
