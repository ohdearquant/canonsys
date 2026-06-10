# 018-Cryptography-RSA - Code Mapping

## Vocabulary Packages

| Package         | Path                                                   | Key Phrases                                                       |
| --------------- | ------------------------------------------------------ | ----------------------------------------------------------------- |
| `certification` | `hub/foundation/packages/certification/` | sign_certificate, request_timestamp_attestation, emit_certificate |

## Phrase Locations

### Certification Package

| Phrase                          | File                                       | Pattern | Regulatory Basis |
| ------------------------------- | ------------------------------------------ | ------- | ---------------- |
| `sign_certificate`              | `phrases/sign_certificate.py`              | action  | eIDAS Art. 41    |
| `request_timestamp_attestation` | `phrases/request_timestamp_attestation.py` | action  | RFC 3161         |
| `record_attestation`            | `phrases/record_attestation.py`            | action  | SOX 302/404      |
| `emit_certificate`              | `phrases/emit_certificate.py`              | action  | SOX 404          |
| `certify_decision`              | `phrases/certify_decision.py`              | action  | Employment law   |

## Core Utility Locations

| Module  | File                                  | Purpose                                           |
| ------- | ------------------------------------- | ------------------------------------------------- |
| Hashing | `libs/canon/src/canon/utils/hashing.py`         | compute_hash, compute_chain_hash                  |
| Signing | `libs/canon/src/canon/utils/security/signer.py` | sign_payload, verify_signature, generate_key_pair |
| Keys    | `libs/canon/src/canon/utils/security/keys.py`   | SigningKey, KeyRegistry                           |
| KMS     | `libs/canon/src/canon/utils/kms/`               | Key Management Service                            |

## Key Functions

### Hashing (utils/hashing.py)

| Function                                          | Purpose                                            |
| ------------------------------------------------- | -------------------------------------------------- |
| `compute_hash(obj, algorithm)`                    | SHA-256 hash with deterministic JSON serialization |
| `compute_chain_hash(payload_hash, previous_hash)` | Chain hash linking for evidence trails             |

### Signing (utils/security/signer.py)

| Function                                               | Purpose                                 |
| ------------------------------------------------------ | --------------------------------------- |
| `generate_key_pair()`                                  | Generate RSA-4096 key pair (PEM format) |
| `sign_payload(payload, private_key_pem)`               | RSA-4096 + PKCS1v15 + SHA-256 signing   |
| `verify_signature(payload, signature, public_key_pem)` | Fail-closed signature verification      |

### Key Management (utils/security/keys.py)

| Class         | Purpose                                                  |
| ------------- | -------------------------------------------------------- |
| `SigningKey`  | Frozen dataclass for signing key metadata                |
| `KeyRegistry` | Manages signing keys with versioning and validity checks |

## KMS Module Structure

| File           | Purpose                                         |
| -------------- | ----------------------------------------------- |
| `enums.py`     | KeyLifecycle, KeyType, Permission, Role         |
| `keys.py`      | DataEncryptionKey (DEK), KeyEncryptionKey (KEK) |
| `protocols.py` | HSMProvider, KeyStorage, AuditStorage           |
| `config.py`    | KMSConfig                                       |
| `service.py`   | KeyManagementService with crypto_shred()        |

## Key Architectural Patterns

### Fail-Closed Verification

```python
except Exception:
    return False  # Any error = invalid signature
```

No exceptions propagate. Attackers cannot distinguish error types.

### Deterministic Hashing

```python
json_dumpb(obj, sort_keys=True, deterministic_sets=True)
```

Same input always produces same hash. Dict key ordering and set iteration don't affect hash.

### Prospective Revocation

```python
def is_key_valid_at(self, key: SigningKey, timestamp: datetime) -> bool:
    return key.revoked_at is None or timestamp < key.revoked_at
```

Signatures made before revocation remain valid.

### Chain Hash Pattern

```
chain_hash = HASH("{payload_hash}:{previous_hash or 'GENESIS'}")
```

Creates tamper-evident chain where each entry links to previous.

## Algorithm Choices Summary

| Parameter | Value    | Rationale                           |
| --------- | -------- | ----------------------------------- |
| Key Size  | RSA-4096 | NIST recommends 3072+ post-2030     |
| Padding   | PKCS1v15 | Universal HSM/KMS compatibility     |
| Hash      | SHA-256  | Ubiquitous, sufficient security     |
| Format    | PEM      | Human-readable, copy-paste friendly |
| Max Input | 10 MB    | SOC2 CC7.1 DoS prevention           |

## Dependencies

**Depends on:**

- `cryptography` - Python cryptography library (hazmat primitives)
- `kron.utils.json_dumpb` - Deterministic JSON serialization

**Depended by:**

- `canon.entities.entity.ContentModel._rehash()` - Content hash computation
- `canon.features.evidence.actions` - Evidence chain hashes
- `canon.entities.charter.CharterContent` - Ratification hash
- `certification` vocabulary package - Certificate signing

## Related Documents

- **ADR**: `ADR-018-cryptography-rsa.md`
- **TDS**: `TDS-018-cryptography-rsa.md`
- **Related**: ADR-003-immutability, ADR-006-evidence-chain-cep, ADR-020-timestamp-tsa
