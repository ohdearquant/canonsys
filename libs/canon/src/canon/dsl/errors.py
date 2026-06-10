"""Charter DSL exception hierarchy.

All DSL errors carry position information (line/column) for
domain-expert-friendly error messages.

All exceptions inherit from ConfigurationError (CanonError hierarchy)
so they can be caught with `except CanonError`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from canon.exceptions import ConfigurationError

if TYPE_CHECKING:
    from .tokens import Token

__all__ = (
    "CharterDSLError",
    "CyclicDependencyError",
    "DuplicatePhaseError",
    "DuplicateWorkflowError",
    "InvalidGrantTTLError",
    "InvalidRoleError",
    "InvalidWaitingPeriodError",
    "LexError",
    "ParseError",
    "ResolveError",
    "UndeclaredPhraseError",
    "UnknownDocumentTypeError",
    "UnknownFeatureError",
    "UnknownPackageError",
    "UnknownPhaseError",
    "UnknownPolicyError",
    "UnknownSchemaError",
    "UnknownTriggerError",
)


class CharterDSLError(ConfigurationError):
    """Base exception for Charter DSL errors.

    Inherits from ConfigurationError so DSL errors are caught by
    `except CanonError` handlers.
    """

    default_message = "Charter DSL error"

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        self.line = line
        self.column = column
        if line is not None:
            loc = f"line {line}"
            if column is not None:
                loc += f", column {column}"
            full_message = f"{loc}: {message}"
        else:
            full_message = message
        super().__init__(
            full_message,
            details={"line": line, "column": column} if line is not None else None,
        )


class LexError(CharterDSLError):
    """Tokenization error."""


class ParseError(CharterDSLError):
    """Parse error with token position."""

    def __init__(self, message: str, token: Token) -> None:
        self.token = token
        super().__init__(message, line=token.line, column=token.column)


class ResolveError(CharterDSLError):
    """Base resolution error."""


class UnknownFeatureError(ResolveError):
    """Feature name not found in vocabulary registry."""

    def __init__(
        self,
        feature_name: str,
        *,
        suggestion: str | None = None,
        line: int | None = None,
    ) -> None:
        self.feature_name = feature_name
        self.suggestion = suggestion
        msg = f"Unknown vocabulary feature: '{feature_name}'"
        if suggestion:
            msg += f". Did you mean '{suggestion}'?"
        super().__init__(msg, line=line)


class UnknownSchemaError(ResolveError):
    """Output type not found in schema catalog."""

    def __init__(
        self,
        type_name: str,
        namespace: str,
        version: str,
        *,
        line: int | None = None,
    ) -> None:
        self.type_name = type_name
        self.namespace = namespace
        self.version = version
        super().__init__(
            f"Unknown schema '{type_name}' in catalog {namespace}@{version}",
            line=line,
        )


class UnknownPackageError(ResolveError):
    """Package name not found in package registry."""

    def __init__(self, package_name: str, *, line: int | None = None) -> None:
        self.package_name = package_name
        super().__init__(
            f"Unknown vocabulary package: '{package_name}'",
            line=line,
        )


class UnknownPhaseError(ResolveError):
    """Phase name referenced but not defined in workflow."""

    def __init__(
        self,
        phase_name: str,
        workflow_name: str,
        *,
        line: int | None = None,
    ) -> None:
        self.phase_name = phase_name
        self.workflow_name = workflow_name
        super().__init__(
            f"Unknown phase '{phase_name}' in workflow '{workflow_name}'",
            line=line,
        )


class UnknownTriggerError(ResolveError):
    """Trigger name referenced in await but not declared in triggers section."""

    def __init__(
        self,
        trigger_name: str,
        *,
        declared_triggers: tuple[str, ...] | None = None,
        line: int | None = None,
    ) -> None:
        self.trigger_name = trigger_name
        self.declared_triggers = declared_triggers
        msg = f"Unknown trigger '{trigger_name}' - must be declared in triggers section"
        if declared_triggers:
            msg += f". Declared triggers: {', '.join(declared_triggers)}"
        super().__init__(msg, line=line)


class CyclicDependencyError(ResolveError):
    """Phase dependencies form a cycle."""

    def __init__(self, cycle: tuple[str, ...]) -> None:
        self.cycle = cycle
        path = " -> ".join(cycle)
        super().__init__(f"Cyclic dependency: {path}")


class UnknownPolicyError(ResolveError):
    """Policy ID not found in policy registry."""

    def __init__(self, policy_id: str, *, line: int | None = None) -> None:
        self.policy_id = policy_id
        super().__init__(
            f"Unknown policy: '{policy_id}'",
            line=line,
        )


class InvalidRoleError(ResolveError):
    """Role references actions not defined in any workflow."""

    def __init__(
        self,
        role_name: str,
        invalid_actions: tuple[str, ...],
        *,
        line: int | None = None,
    ) -> None:
        self.role_name = role_name
        self.invalid_actions = invalid_actions
        actions = ", ".join(invalid_actions)
        super().__init__(
            f"Role '{role_name}' references unknown actions: {actions}",
            line=line,
        )


class DuplicateWorkflowError(ResolveError):
    """Duplicate workflow name in charter."""

    def __init__(self, workflow_name: str, *, line: int | None = None) -> None:
        self.workflow_name = workflow_name
        super().__init__(
            f"Duplicate workflow name: '{workflow_name}'",
            line=line,
        )


class DuplicatePhaseError(ResolveError):
    """Duplicate phase name within a workflow."""

    def __init__(
        self,
        phase_name: str,
        workflow_name: str,
        *,
        line: int | None = None,
    ) -> None:
        self.phase_name = phase_name
        self.workflow_name = workflow_name
        super().__init__(
            f"Duplicate phase '{phase_name}' in workflow '{workflow_name}'",
            line=line,
        )


class InvalidWaitingPeriodError(ResolveError):
    """Waiting period has invalid range."""

    def __init__(
        self,
        min_value: int,
        max_value: int,
        reason: str,
        *,
        line: int | None = None,
    ) -> None:
        self.min_value = min_value
        self.max_value = max_value
        self.reason = reason
        super().__init__(
            f"Invalid waiting period {min_value}..{max_value}: {reason}",
            line=line,
        )


class UndeclaredPhraseError(ResolveError):
    """Phrase used but not declared in any imported package."""

    def __init__(
        self,
        phrase_name: str,
        *,
        declared_packages: tuple[str, ...] | None = None,
        suggested_package: str | None = None,
        line: int | None = None,
    ) -> None:
        self.phrase_name = phrase_name
        self.declared_packages = declared_packages
        self.suggested_package = suggested_package
        msg = f"Undeclared phrase: '{phrase_name}' is not exported by any imported package"
        if declared_packages:
            msg += f". Imported packages: {', '.join(declared_packages)}"
        if suggested_package:
            msg += f". Did you mean to import '{suggested_package}'?"
        super().__init__(msg, line=line)


class UnknownDocumentTypeError(ResolveError):
    """Document type not found in known document types."""

    def __init__(
        self,
        document_type: str,
        *,
        known_types: tuple[str, ...] | None = None,
        line: int | None = None,
    ) -> None:
        self.document_type = document_type
        self.known_types = known_types
        msg = f"Unknown document type: '{document_type}'"
        if known_types:
            msg += f". Known types: {', '.join(known_types)}"
        super().__init__(msg, line=line)


class InvalidGrantTTLError(ResolveError):
    """Grant TTL is outside valid range."""

    def __init__(
        self,
        ttl_minutes: int,
        reason: str,
        *,
        line: int | None = None,
    ) -> None:
        self.ttl_minutes = ttl_minutes
        self.reason = reason
        super().__init__(
            f"Invalid grant TTL {ttl_minutes}m: {reason}",
            line=line,
        )
