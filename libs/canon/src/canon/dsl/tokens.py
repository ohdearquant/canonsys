"""Charter DSL token types and token representation.

Defines the lexical elements of the Charter DSL:
- Keywords (charter, workflow, phase, require, action, etc.)
- Literals (identifiers, strings, integers, floats)
- Punctuation (colon, comma, dot, range, parens, brackets)
- Comparators (==, !=, >, <, >=, <=)
- Indentation (INDENT, DEDENT, NEWLINE)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

__all__ = (
    "BOOLEAN_LITERALS",
    "KEYWORDS",
    "Token",
    "TokenType",
)


class TokenType(Enum):
    """Token types for Charter DSL."""

    # --- Keywords ---
    CHARTER = auto()
    SCHEMAS = auto()
    PACKAGES = auto()
    POLICIES = auto()
    TRIGGERS = auto()  # Event trigger declarations
    WORKFLOW = auto()
    PHASE = auto()
    REQUIRE = auto()
    AWAIT = auto()  # require await event_name
    ACTION = auto()
    OUTPUT = auto()
    CERTIFY = auto()
    EVIDENCE = auto()
    GRANTS = auto()
    FOR = auto()
    SITUATIONS = auto()
    WHEN = auto()
    WAITING_PERIOD = auto()
    ROLES = auto()
    BREAK_GLASS = auto()
    REQUIRES_MFA = auto()
    ACTIONS = auto()
    IMMUTABLE = auto()
    DAYS = auto()
    HOURS = auto()
    PASSED = auto()
    COMPLETE = auto()
    TRUE = auto()
    FALSE = auto()
    OR = auto()  # require X or Y

    # --- Literals ---
    IDENT = auto()
    STRING = auto()
    DOCSTRING = auto()  # Triple-quoted string for documentation
    INT = auto()
    FLOAT = auto()

    # --- Punctuation ---
    COLON = auto()
    COMMA = auto()
    DOT = auto()
    DOTDOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    AT = auto()
    DASH = auto()

    # --- Comparators ---
    EQ = auto()
    NEQ = auto()
    GT = auto()
    GTE = auto()
    LT = auto()
    LTE = auto()

    # --- Indentation ---
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()

    # --- Control ---
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "charter": TokenType.CHARTER,
    "schemas": TokenType.SCHEMAS,
    "packages": TokenType.PACKAGES,
    "policies": TokenType.POLICIES,
    "triggers": TokenType.TRIGGERS,
    "workflow": TokenType.WORKFLOW,
    "phase": TokenType.PHASE,
    "require": TokenType.REQUIRE,
    "await": TokenType.AWAIT,
    "action": TokenType.ACTION,
    "output": TokenType.OUTPUT,
    "certify": TokenType.CERTIFY,
    "evidence": TokenType.EVIDENCE,
    "grants": TokenType.GRANTS,
    "for": TokenType.FOR,
    "situations": TokenType.SITUATIONS,
    "when": TokenType.WHEN,
    "waiting_period": TokenType.WAITING_PERIOD,
    "roles": TokenType.ROLES,
    "break_glass": TokenType.BREAK_GLASS,
    "requires_mfa": TokenType.REQUIRES_MFA,
    "actions": TokenType.ACTIONS,
    "immutable": TokenType.IMMUTABLE,
    "days": TokenType.DAYS,
    "hours": TokenType.HOURS,
    "passed": TokenType.PASSED,
    "complete": TokenType.COMPLETE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "or": TokenType.OR,
}

BOOLEAN_LITERALS: dict[str, bool] = {
    "true": True,
    "false": False,
}


@dataclass(frozen=True, slots=True)
class Token:
    """Token with type, value, and source position."""

    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
