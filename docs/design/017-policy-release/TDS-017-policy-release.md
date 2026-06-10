---
doc_type: TDS
title: "Technical Design Specification: Policy Release and Two-Key Model"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["policy", "charter", "core"]
charters: []
---

# Technical Design Specification: Policy Release and Two-Key Model

## 1. Overview

### 1.1 Purpose

PolicyRelease is the versioned, immutable snapshot of policies that tenants activate via Charter.
This specification covers the policy versioning lifecycle, the Two-Key Model for separation of
concerns, and the binding mechanism between legal requirements and engineering implementation.

### 1.2 Scope

- PolicyRelease entity and lifecycle
- PolicyDefinition (Legal Key) and PolicyAdapter (Engineering Key)
- Two-Key Model for policy changes
- Charter binding to releases via vocabulary phrases

### 1.3 Design Principles

1. **Immutable After Publish**: Like git tags - once published, content is frozen
2. **Two-Key Model**: Neither Legal nor Engineering can unilaterally change enforcement
3. **Explicit Binding**: Charter explicitly selects policy_ids from releases
4. **Version Lock**: Adapters lock to specific PolicyDefinition versions
5. **Cryptographic Integrity**: Content hashes verify tamper-evidence

## 2. Vocabulary Phrases

### 2.1 Policy Package Phrases

| Phrase                           | Purpose               | Inputs                        | Outputs                    |
| -------------------------------- | --------------------- | ----------------------------- | -------------------------- |
| `create_policy_release`          | Create draft release  | version, description          | release_id, status         |
| `publish_policy_release`         | Freeze and publish    | release_id                    | published_at, content_hash |
| `create_policy_definition`       | Legal policy spec     | policy_id, version, authority | definition_id, status      |
| `create_policy_adapter`          | Engineering impl      | policy_id, definition_version | adapter_id, version_lock   |
| `require_policy_active`          | Gate: policy active   | policy_id                     | satisfied: bool            |
| `require_policy_version_current` | Gate: version lock    | adapter_id, definition_id     | satisfied: bool            |
| `evaluate_policy`                | Evaluate against data | policy_id, input_data         | decision, reason           |

### 2.2 Charter Package Phrases

| Phrase             | Purpose              | Inputs                       | Outputs                       |
| ------------------ | -------------------- | ---------------------------- | ----------------------------- |
| `create_charter`   | Create draft charter | tenant_id, policy_release_id | charter_id, status            |
| `activate_charter` | DRAFT -> ACTIVE      | charter_id, effective_date   | status, superseded_charter_id |

### 2.3 Core Package Phrases

| Phrase           | Purpose            | Inputs                  | Outputs                        |
| ---------------- | ------------------ | ----------------------- | ------------------------------ |
| `ratify_charter` | Record signatories | charter_id, signatories | ratification_hash, ratified_at |

## 3. Lifecycle State Machines

### 3.1 PolicyRelease Lifecycle

```
DRAFT -> PUBLISHED -> ACTIVE -> DEPRECATED
  |                      |
  +--> [add_policy] -----+--> [immutable]
```

- **DRAFT**: Content mutable via `add_policy`, `remove_policy`
- **PUBLISHED**: Content frozen via `publish_policy_release`
- **ACTIVE**: Current recommended release
- **DEPRECATED**: Legacy, migration needed

### 3.2 Charter Lifecycle

```
DRAFT -> RATIFIED -> ACTIVE -> RETIRED
           |            |
           +--> ratify_charter
                        +--> activate_charter
```

- **DRAFT**: Can modify policy_ids, roles, constraints
- **RATIFIED**: Signatories recorded, ratification_hash computed
- **ACTIVE**: Governing tenant (only one active per tenant)
- **RETIRED**: Superseded by newer charter

## 4. Two-Key Model

### 4.1 Principle

> Neither key alone can modify enforcement behavior. Both must align for a policy to be active.

### 4.2 Separation of Concerns

| Aspect     | Key 1 (Legal)              | Key 2 (Engineering)             |
| ---------- | -------------------------- | ------------------------------- |
| Owner      | Legal / Compliance         | Engineering                     |
| Contains   | Requirements, citations    | Rego code, gate implementations |
| Can modify | WHAT must be checked       | HOW to check it                 |
| Phrase     | `create_policy_definition` | `create_policy_adapter`         |

### 4.3 Version Lock Pattern

PolicyAdapter locks to specific PolicyDefinition version:

```python
# Enforced by require_policy_version_current phrase
result = await require_policy_version_current({
    "adapter_id": adapter_id,
    "definition_id": definition_id,
}, ctx)

if not result["satisfied"]:
    raise VersionLockError("Adapter version doesn't match definition")
```

## 5. Charter Binding

### 5.1 Activation Flow

```python
# 1. Create charter draft
charter = await create_charter({
    "tenant_id": tenant_id,
    "policy_release_id": "2026.01",
    "policy_ids": ["nyc_fca_waiting", "gdpr_consent"],
}, ctx)

# 2. Ratify with signatories
await ratify_charter({
    "charter_id": charter["id"],
    "signatories": [
        {"user_id": legal_counsel, "role": "legal_approver"},
        {"user_id": cto, "role": "technical_approver"},
    ],
}, ctx)

# 3. Activate (retires previous active charter)
await activate_charter({
    "charter_id": charter["id"],
    "effective_date": effective_date,
}, ctx)
```

### 5.2 Selective Policy Activation

Not all tenants need all policies from a release:

- NYC company: Needs NYC Fair Chance Act, not EU GDPR
- EU company: Needs GDPR, not NYC laws
- Global company: May need both

Charter allows selective activation via `policy_ids` list.

## 6. Integrity Verification

### 6.1 Content Hash Chain

- **PolicyRelease**: `content_hash` computed from policies + metadata
- **Charter**: `ratification_hash` computed from content + signatories
- Both use `compute_hash()` with deterministic JSON serialization

### 6.2 Ratification Hash

Computed by `ratify_charter` phrase:

```python
ratification_data = {
    "charter_id": str(charter_id),
    "content_hash": row.get("content_hash"),
    "signatories": signatory_data,
    "ratified_at": now.isoformat(),
}
ratification_hash = compute_hash(ratification_data)
```

## 7. Integration Points

| Component            | Integration                                     |
| -------------------- | ----------------------------------------------- |
| ADR-009-opa          | Regorus engine loads bundles from PolicyRelease |
| ADR-008-policy-gates | Gates reference policies from active release    |
| ADR-025-charter      | Charter DSL compiles to validated DAGs          |
| Evidence system      | Rollback evidence captured with CEP             |

## 8. Anti-Patterns

### Do NOT

- Modify PolicyRelease after publishing (immutability violation)
- Deploy PolicyAdapter without matching PolicyDefinition version
- Skip Charter ratification for compliance-sensitive tenants
- Allow unilateral policy changes (bypasses Two-Key Model)

### Correct Patterns

- Create new release version for any content change
- Always verify version lock via `require_policy_version_current`
- Require both Legal and Engineering approval for policy changes

## 9. References

- **Vocabulary Packages**:
  - `hub/foundation/packages/policy/`
  - `hub/foundation/packages/charter/`
  - `hub/foundation/packages/core/`
- **Core Entities**: `libs/canon/src/canon/entities/policy/definition.py`, `libs/canon/src/canon/entities/charter/charter.py`
- **Related**: TDS-008-policy-gates, TDS-025-charter, ADR-009-opa
