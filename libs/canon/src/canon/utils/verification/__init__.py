"""Validators for CanonSys compliance checks.

Submodules:
- opa: OPA/Rego policy validators
- sql: SQL-based validators
- opa_data_provider: Data context builder for UCS validator
- ucs_transform: UCS-v1 transform functions for OPA validation
- ucs_validator: UCS-v1 certificate validator (Python wrapper for Rego)
"""

from .opa_data_provider import DEFAULT_ROLES, UCSDataProvider
from .ucs_transform import (
    build_authority_block,
    build_context_block,
    build_evidence_pointers,
    build_meta_block,
    build_seal_block,
    tokenize_subject,
    transform_to_ucs,
)
from .ucs_validator import UCSValidator, ValidationResult, ValidationStatus

__all__ = [
    "DEFAULT_ROLES",
    "UCSDataProvider",
    "UCSValidator",
    "ValidationResult",
    "ValidationStatus",
    "build_authority_block",
    "build_context_block",
    "build_evidence_pointers",
    "build_meta_block",
    "build_seal_block",
    "tokenize_subject",
    "transform_to_ucs",
]
