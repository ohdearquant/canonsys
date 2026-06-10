# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""KMS security enums and role-permission mappings.

References:
- NIST SP 800-57 (Key Management)
- NIST SP 800-53 (Access Control)
- FIPS 140-2/3 (Cryptographic Modules)
- CNIL Security Guide 2024 (Audit logging)
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ROLE_PERMISSIONS",
    "EncryptionAlgorithm",
    "KeyLifecycle",
    "KeyType",
    "Permission",
    "Role",
    "SecurityEventType",
    "ShredStatus",
]


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms.

    Per NIST SP 800-57 and FIPS 140-2/3, AES-256-GCM is the recommended
    default for authenticated encryption. ChaCha20-Poly1305 is available
    for mobile/embedded contexts but is NOT FIPS-approved.

    References:
        - NIST SP 800-38D: Recommendation for Block Cipher Modes (GCM)
        - FIPS 197: Advanced Encryption Standard (AES)
    """

    AES_256_GCM = "AES-256-GCM"
    """Default: AEAD with 256-bit key, 128-bit auth tag. FIPS-approved."""

    AES_256_CBC = "AES-256-CBC"
    """Legacy compatibility mode. Requires separate HMAC for authentication."""

    CHACHA20_POLY1305 = "ChaCha20-Poly1305"
    """Mobile/embedded optimization. NOT FIPS-approved."""


class KeyType(str, Enum):
    """Types of cryptographic keys in the key hierarchy.

    Key hierarchy per NIST SP 800-57:
    - MEK (Master) -> KEK (Key-Encrypting) -> DEK (Data)

    References:
        - NIST SP 800-57 Part 1 Rev. 5: Key Management
    """

    DEK = "dek"
    """Data Encryption Key - per-candidate for crypto-shredding support."""

    KEK = "kek"
    """Key Encryption Key - wraps DEKs, stored in HSM."""

    MEK = "mek"
    """Master Encryption Key - root of trust in HSM."""

    SIGNING = "signing"
    """Digital signature keys for non-repudiation."""


class KeyLifecycle(str, Enum):
    """Key lifecycle states per NIST SP 800-57.

    State transitions:
        PENDING_ACTIVATION -> ACTIVE -> DEACTIVATED -> DESTROYED
        ACTIVE -> COMPROMISED -> DESTROYED (emergency path)

    References:
        - NIST SP 800-57 Part 1 Rev. 5 Section 7: Key States
    """

    PENDING_ACTIVATION = "pending_activation"
    """Generated but not yet active. Pre-operational period."""

    ACTIVE = "active"
    """In use for encryption and decryption operations."""

    DEACTIVATED = "deactivated"
    """Post-rotation: decrypt-only, no new encryptions."""

    COMPROMISED = "compromised"
    """Emergency revocation due to suspected compromise."""

    DESTROYED = "destroyed"
    """Permanently deleted. Crypto-shredding complete."""


class ShredStatus(str, Enum):
    """Crypto-shredding request lifecycle states.

    Per EDPB 2025 Guidelines, crypto-shredding is accepted as
    GDPR Article 17 erasure when properly implemented.

    References:
        - EDPB 2025 Guidelines on crypto-shredding
        - NIST SP 800-88 Rev. 1: Cryptographic Erase
    """

    PENDING = "pending"
    """Request received, awaiting processing."""

    IN_PROGRESS = "in_progress"
    """Key destruction in progress."""

    COMPLETED = "completed"
    """Key destroyed, destruction certificate issued."""

    BLOCKED = "blocked"
    """Blocked by litigation hold per GDPR Art 17(3)(e)."""

    FAILED = "failed"
    """Technical failure during shredding operation."""


class SecurityEventType(str, Enum):
    """Types of security events for audit logging.

    Per CNIL Security Guide 2024, security audit logs must capture:
    - Who (operator ID)
    - When (timestamp)
    - What (action type, affected resources)

    References:
        - CNIL Security Guide 2024
        - GDPR Article 5(2): Accountability principle
    """

    # Key lifecycle events
    KEY_CREATED = "key_created"
    """New key generated in HSM."""

    KEY_ROTATED = "key_rotated"
    """Key rotation completed, old key deactivated."""

    KEY_DESTROYED = "key_destroyed"
    """Key permanently deleted from HSM."""

    KEY_ACCESSED = "key_accessed"
    """Key used for encryption/decryption operation."""

    KEY_EXPORTED = "key_exported"
    """Key exported (wrapped) from HSM. High-risk operation."""

    # Encryption operations
    ENCRYPT_SUCCESS = "encrypt_success"
    """Data encryption completed successfully."""

    ENCRYPT_FAILURE = "encrypt_failure"
    """Data encryption failed."""

    DECRYPT_SUCCESS = "decrypt_success"
    """Data decryption completed successfully."""

    DECRYPT_FAILURE = "decrypt_failure"
    """Data decryption failed (integrity or key error)."""

    # Crypto-shredding events
    SHRED_REQUESTED = "shred_requested"
    """Erasure request received."""

    SHRED_COMPLETED = "shred_completed"
    """Crypto-shredding successfully completed."""

    SHRED_BLOCKED = "shred_blocked"
    """Shredding blocked by litigation hold."""

    SHRED_FAILED = "shred_failed"
    """Shredding failed due to technical error."""

    # Backup handling events
    ERASURE_MARKER_CREATED = "erasure_marker_created"
    """Do-not-restore marker created for backup systems."""

    RESTORE_RECONCILED = "restore_reconciled"
    """Post-restore erasure reconciliation completed."""

    # Access control events
    ACCESS_GRANTED = "access_granted"
    """Permission check passed."""

    ACCESS_DENIED = "access_denied"
    """Permission check failed."""

    PRIVILEGE_ESCALATION = "privilege_escalation"
    """Elevated permissions requested or granted."""


class Permission(str, Enum):
    """Security permissions for sensitive operations.

    Permissions are grouped by resource type and follow principle
    of least privilege. Critical operations require dual authorization.

    References:
        - NIST SP 800-53: Access Control (AC)
    """

    # Key management permissions
    KEY_CREATE = "key:create"
    """Create new encryption keys."""

    KEY_ROTATE = "key:rotate"
    """Rotate existing keys (KEK rotation re-wraps DEKs)."""

    KEY_DESTROY = "key:destroy"
    """Destroy keys. CRITICAL: Requires dual authorization."""

    KEY_EXPORT = "key:export"
    """Export (wrapped) keys. CRITICAL: Requires dual authorization."""

    # Crypto-shredding permissions
    SHRED_REQUEST = "shred:request"
    """Submit erasure request."""

    SHRED_EXECUTE = "shred:execute"
    """Execute erasure (destroy key)."""

    SHRED_OVERRIDE = "shred:override"
    """Override litigation hold. CRITICAL: Requires dual authorization."""

    # Evidence access permissions
    EVIDENCE_READ = "evidence:read"
    """Read evidence metadata (not decrypted content)."""

    EVIDENCE_DECRYPT = "evidence:decrypt"
    """Decrypt evidence content."""

    EVIDENCE_EXPORT = "evidence:export"
    """Export evidence for legal proceedings."""

    # Audit permissions
    AUDIT_READ = "audit:read"
    """Read audit log entries."""

    AUDIT_EXPORT = "audit:export"
    """Export audit logs for DPA inspection."""

    # Litigation hold permissions
    HOLD_CREATE = "hold:create"
    """Create litigation hold."""

    HOLD_RELEASE = "hold:release"
    """Release litigation hold. CRITICAL: Requires dual authorization."""


class Role(str, Enum):
    """Security roles with associated permission sets.

    Role hierarchy follows principle of least privilege.
    SUPER_ADMIN has all permissions but should be used sparingly.

    References:
        - NIST SP 800-53: Role-Based Access Control
    """

    SYSTEM = "system"
    """Automated system processes (key creation, encryption)."""

    OPERATOR = "operator"
    """Standard operations (request erasure, read evidence)."""

    COMPLIANCE_OFFICER = "compliance_officer"
    """Compliance monitoring (audit logs, evidence access)."""

    DPO = "dpo"
    """Data Protection Officer (full DSR handling per GDPR)."""

    LEGAL_COUNSEL = "legal_counsel"
    """Legal team (evidence export, litigation holds)."""

    SECURITY_ADMIN = "security_admin"
    """Security operations (key management, audit)."""

    SUPER_ADMIN = "super_admin"
    """Full access. Use sparingly with dual authorization."""


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.SYSTEM: {
        Permission.KEY_CREATE,
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_DECRYPT,
    },
    Role.OPERATOR: {
        Permission.EVIDENCE_READ,
        Permission.SHRED_REQUEST,
    },
    Role.COMPLIANCE_OFFICER: {
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_DECRYPT,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.SHRED_REQUEST,
    },
    Role.DPO: {
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_DECRYPT,
        Permission.EVIDENCE_EXPORT,
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.SHRED_REQUEST,
        Permission.SHRED_EXECUTE,
    },
    Role.LEGAL_COUNSEL: {
        Permission.EVIDENCE_READ,
        Permission.EVIDENCE_DECRYPT,
        Permission.EVIDENCE_EXPORT,
        Permission.HOLD_CREATE,
        Permission.HOLD_RELEASE,
    },
    Role.SECURITY_ADMIN: {
        Permission.KEY_CREATE,
        Permission.KEY_ROTATE,
        Permission.KEY_DESTROY,
        Permission.AUDIT_READ,
    },
    Role.SUPER_ADMIN: set(Permission),  # All permissions
}
"""Role to permission mapping.

CRITICAL: Permissions requiring dual authorization:
- KEY_DESTROY
- KEY_EXPORT
- SHRED_OVERRIDE
- HOLD_RELEASE

References:
    - NIST SP 800-53 AC-3: Access Enforcement
"""
