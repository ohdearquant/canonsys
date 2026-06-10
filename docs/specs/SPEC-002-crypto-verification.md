# Crypto Verification Appendix (UCS-v1)

**Author**: Jason La Barbera **Captured**: 2026-01-13 **Status**: Documentation Pass (Infrastructure
Already Present)

_TSA + RSA foundation exists. This documents the binding semantics._

---

## 1. Current State (What We Have)

| Component        | Status         | Location                 |
| ---------------- | -------------- | ------------------------ |
| RSA-4096 Signing | ✅ Implemented | `core/crypto/`           |
| TSA (RFC 3161)   | ✅ Implemented | Evidence chain           |
| Hash Chains      | ✅ Implemented | `core/entities/chain.py` |

**Net effect**: Authenticity, integrity, and time are already defensible. This appendix formalizes
the guarantees.

---

## 2. What Must Be Recorded Per Certificate

Every UCS certificate seal block must include:

```json
{
  "seal": {
    "signature": "RSA-4096_SIGNATURE",
    "key_id": "key-2024-prod-001",
    "key_version": "3",
    "signed_at_utc": "2024-10-22T14:30:00Z",
    "tsa_identity": "DigiCert Timestamp Authority",
    "tsa_response_hash": "sha256:...",
    "previous_cert_hash": "sha256:..."
  }
}
```

### Required Fields

| Field               | Purpose                 | Why It Matters                            |
| ------------------- | ----------------------- | ----------------------------------------- |
| `key_id`            | Which key signed        | Enables key rotation without invalidation |
| `key_version`       | Version of that key     | Tracks key lifecycle                      |
| `signed_at_utc`     | When signature was made | Must fall within key validity window      |
| `tsa_identity`      | Whose clock was used    | Judges want to know whose time you trust  |
| `tsa_response_hash` | Hash of TSA response    | Proves timestamp wasn't fabricated        |

---

## 3. Key Validity Window Binding

**Rule**: `signed_at_utc` MUST fall within the signing key's validity window.

```
key_valid_from ≤ signed_at_utc ≤ key_valid_until
```

### Validator Check (Phase 6)

```python
def validate_key_validity(seal: dict, key_registry: KeyRegistry) -> bool:
    key = key_registry.get(seal["key_id"], seal["key_version"])
    if key is None:
        return False  # Unknown key
    if key.revoked:
        return False  # Key revoked
    if not (key.valid_from <= seal["signed_at_utc"] <= key.valid_until):
        return False  # Outside validity window
    return True
```

---

## 4. Revocation Semantics (Critical)

**Revocation is PROSPECTIVE, not retroactive.**

| Scenario          | Effect                                                  |
| ----------------- | ------------------------------------------------------- |
| Key revoked today | Certificates signed before revocation remain valid      |
| Key compromised   | Mark compromise date; certs after that date are suspect |
| Key expired       | Certificates signed within validity window remain valid |

### Why This Matters

If revocation were retroactive, a single key compromise would invalidate years of termination
decisions. That's legally untenable.

**Rule**: Once a certificate is validly sealed, its validity is frozen at that moment.

---

## 5. TSA Identity Recording

**Every certificate must record the TSA identity.**

Why judges care:

- "Whose clock did you use?" has a clear answer
- Third-party timestamp = no "company manipulated the time" argument
- RFC 3161 compliance = industry standard

### Recommended TSAs

| Provider   | Notes                                |
| ---------- | ------------------------------------ |
| DigiCert   | Industry standard, widely recognized |
| Sectigo    | Good compliance record               |
| GlobalSign | European presence                    |

**Do NOT use internal clocks for legal timestamps.**

---

## 6. Verification Flow (Read Path)

When verifying a certificate:

1. **Signature Check**: RSA signature valid over payload
2. **Key Check**: `key_id` + `key_version` exists and was valid at `signed_at_utc`
3. **TSA Check**: `tsa_response_hash` matches stored TSA response
4. **Chain Check**: `previous_cert_hash` resolves (if present)

All four must pass. Any failure = `INVALID`.

---

## 7. Key Rotation Protocol

Keys should rotate on schedule, not on compromise.

| Key Type           | Rotation Period | Overlap Period |
| ------------------ | --------------- | -------------- |
| Production signing | 12 months       | 30 days        |
| Backup signing     | 24 months       | 60 days        |

**Overlap period**: Both old and new keys are valid during transition.

---

## 8. What This Removes

With proper key binding and TSA recording:

- ❌ "Was the key valid at the time?" → Answered by `signed_at_utc` + key registry
- ❌ "Could the timestamp be faked?" → Third-party TSA, RFC 3161
- ❌ "What if the key is compromised?" → Prospective revocation, not retroactive

**This is FRE-safe territory.**

---

## 9. Implementation Checklist

- [ ] Add `key_id`, `key_version` to seal block
- [ ] Add `tsa_identity`, `tsa_response_hash` to seal block
- [ ] Implement key validity window check in validator Phase 6
- [ ] Document prospective revocation policy
- [ ] Set up key rotation schedule

---

## 10. Related Documents

- [SPEC: UCS Validator Enforcement](./SPEC-ucs-validator-enforcement.md)
- [SPEC: Universal Certificate Schema](./SPEC-universal-certificate-schema.md)
