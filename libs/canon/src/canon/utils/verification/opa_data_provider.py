"""OPA data provider for UCS validator.

Builds the data context required by ucs_validator.rego:
- data.roles: Workflow type -> allowed issuer roles
- data.ceps: CEP metadata keyed by cep_id
- data.signing_keys: Key validity windows keyed by key_id

Usage:
    provider = UCSDataProvider()
    provider.add_cep(cep_id="cep-123", final_hash="abc...", ...)
    provider.add_signing_key(key_id="key-456", ...)

    opa_data = provider.build_opa_data()
    # Pass to OPA engine: engine.add_data(opa_data)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Role definitions - which roles can issue which workflow types
# Keys must match input.context.workflow_type values exactly
DEFAULT_ROLES: dict[str, list[str]] = {
    "TERMINATION_DECISION": [
        "HRBP_DIRECTOR",
        "VP_HR",
        "CHRO",
        "LEGAL_COUNSEL",
    ],
    "INVESTIGATION_CLOSE": [
        "EMPLOYEE_RELATIONS_INVESTIGATOR",
        "ER_DIRECTOR",
        "LEGAL_COUNSEL",
    ],
    "PIP_FAIL": [
        "HRBP_DIRECTOR",
        "VP_HR",
        "MANAGER_L3",  # Only L3+ managers
    ],
    "EXEC_OVERRIDE": [
        "CHRO",
        "CEO",
        "GENERAL_COUNSEL",
    ],
}


class UCSDataProvider:
    """Provides data context for UCS OPA validator.

    Builds the data structures expected by ucs_validator.rego:
    - data.roles[workflow_type] -> list of allowed role strings
    - data.ceps[cep_id] -> CEP record with final_hash, type, status, valid_until_utc
    - data.signing_keys[key_id] -> key record with validity timestamps

    CEPs and signing keys are transient (per-evaluation), while roles
    are persistent configuration.
    """

    def __init__(
        self,
        roles: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the data provider.

        Args:
            roles: Custom role authorization map. Defaults to DEFAULT_ROLES.
        """
        self._roles = roles if roles is not None else DEFAULT_ROLES.copy()
        self._ceps: dict[str, dict[str, Any]] = {}
        self._signing_keys: dict[str, dict[str, Any]] = {}

    def set_roles(self, roles: dict[str, list[str]]) -> None:
        """Set role authorization map.

        Args:
            roles: Mapping of workflow_type -> list of allowed roles.
        """
        self._roles = roles

    def add_cep(
        self,
        cep_id: str,
        final_hash: str,
        cep_type: str,
        status: str = "ACTIVE",
        valid_until_utc: datetime | None = None,
    ) -> None:
        """Add CEP to data context.

        Args:
            cep_id: Unique CEP identifier (key in data.ceps).
            final_hash: Content hash for integrity verification.
            cep_type: CEP type (e.g., "POLICY_SIGN_OFF", "ER_CLEARANCE").
            status: Lifecycle status (default "ACTIVE").
            valid_until_utc: Expiration timestamp (optional).
        """
        self._ceps[cep_id] = {
            "cep_id": cep_id,
            "final_hash": final_hash,
            "type": cep_type,
            "status": status,
            "valid_until_utc": (valid_until_utc.isoformat() if valid_until_utc else None),
        }

    def add_signing_key(
        self,
        key_id: str,
        valid_from_utc: datetime,
        valid_to_utc: datetime | None = None,
        revoked_at_utc: datetime | None = None,
    ) -> None:
        """Add signing key to data context.

        Args:
            key_id: Unique key identifier (key in data.signing_keys).
            valid_from_utc: Start of validity window.
            valid_to_utc: End of validity window (None = no expiry).
            revoked_at_utc: Revocation timestamp (None = not revoked).
        """
        self._signing_keys[key_id] = {
            "key_id": key_id,
            "valid_from_utc": valid_from_utc.isoformat(),
            "valid_to_utc": valid_to_utc.isoformat() if valid_to_utc else None,
            "revoked_at_utc": (revoked_at_utc.isoformat() if revoked_at_utc else None),
        }

    def build_opa_data(self) -> dict[str, Any]:
        """Build complete OPA data context.

        Returns:
            Dict with 'roles', 'ceps', and 'signing_keys' for OPA engine.
        """
        return {
            "roles": self._roles,
            "ceps": self._ceps,
            "signing_keys": self._signing_keys,
        }

    def clear(self) -> None:
        """Clear transient data (ceps, keys). Roles persist."""
        self._ceps.clear()
        self._signing_keys.clear()

    @property
    def roles(self) -> dict[str, list[str]]:
        """Get current role authorization map (read-only copy)."""
        return self._roles.copy()

    @property
    def cep_count(self) -> int:
        """Number of CEPs in context."""
        return len(self._ceps)

    @property
    def signing_key_count(self) -> int:
        """Number of signing keys in context."""
        return len(self._signing_keys)


__all__ = ["DEFAULT_ROLES", "UCSDataProvider"]
