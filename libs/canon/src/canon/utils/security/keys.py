"""Signing key management for certificate seals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = (
    "KeyRegistry",
    "SigningKey",
)


@dataclass(frozen=True, slots=True)
class SigningKey:
    """Signing key with version and validity window.

    Revocation is PROSPECTIVE: certificates signed before revocation remain valid.
    """

    key_id: str
    version: int
    valid_from: datetime
    valid_until: datetime
    public_key_pem: str
    revoked_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "key_id": self.key_id,
            "version": self.version,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "public_key_pem": self.public_key_pem,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class KeyRegistry:
    """Manages signing keys with lookup and validity checks."""

    def __init__(
        self,
        keys: Sequence[SigningKey],
        current_key_id: str | None = None,
    ) -> None:
        self._keys: dict[tuple[str, int], SigningKey] = {}
        self._latest_versions: dict[str, int] = {}
        self._current_key_id = current_key_id

        for key in keys:
            self._keys[(key.key_id, key.version)] = key
            if key.key_id not in self._latest_versions:
                self._latest_versions[key.key_id] = key.version
            else:
                self._latest_versions[key.key_id] = max(
                    self._latest_versions[key.key_id],
                    key.version,
                )

    def get_key(self, key_id: str, version: int | None = None) -> SigningKey | None:
        """Get key by ID. If version is None, returns latest version."""
        if version is None:
            latest = self._latest_versions.get(key_id)
            if latest is None:
                return None
            version = latest
        return self._keys.get((key_id, version))

    def get_current_key(self) -> SigningKey | None:
        """Get current key for new signatures."""
        if self._current_key_id is None:
            return None
        return self.get_key(self._current_key_id)

    def is_key_valid_at(self, key: SigningKey, timestamp: datetime) -> bool:
        """Check if key was valid at timestamp (prospective revocation)."""
        if not (key.valid_from <= timestamp <= key.valid_until):
            return False
        return key.revoked_at is None or timestamp < key.revoked_at
