"""Shared error hierarchy and the structured error shape returned by the API.

Every InfraGuard-raised error carries a stable `code` and a human `message`, so API and CLI
responses are consistent and callers can branch on `code` rather than parsing prose.
"""

from typing import Any


class InfraGuardError(Exception):
    """Base class for all expected InfraGuard errors."""

    code: str = "infraguard_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class InputValidationError(InfraGuardError):
    """Input failed structural or semantic validation before analysis could run."""

    code = "input_validation_error"
    status_code = 422


class NotFoundError(InfraGuardError):
    """A referenced run, report, or resource does not exist."""

    code = "not_found"
    status_code = 404


class UnsupportedInputError(InfraGuardError):
    """Input is well-formed but describes something InfraGuard does not yet understand.

    Raised instead of silently treating unsupported input as safe.
    """

    code = "unsupported_input"
    status_code = 422
