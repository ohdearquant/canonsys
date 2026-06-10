---
doc_type: TDS
title: "Technical Design Specification: Policy Resolution"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["policy", "charter", "core"]
charters: []
---

# Technical Design Specification: Policy Resolution

## 1. Overview

### 1.1 Purpose

The PolicyResolver determines which policies apply to a given context. It bridges the Two-Key Model
(Legal + Engineering) with runtime execution by transforming policy definitions into executable
ResolvedPolicy instances.

### 1.2 Design Principles

1. **Two-Key Binding**: Neither Legal nor Engineering alone can modify enforcement
2. **Charter-Gated**: Only policies activated in tenant's Charter are resolved
3. **Effective Dating**: Temporal filtering based on policy lifecycle
4. **Specificity Ordering**: More specific policies take precedence

## 2. Architecture

### 2.1 Two-Key Model

```
                       PolicyLibrary
                             |
     +----------------------+----------------------+
     |                                            |
PolicyDefinition                           PolicyAdapter
(Legal Key)                                (Engineering Key)
     |                                            |
     +----------------------+----------------------+
                            |
                     PolicyIndexEntry
                  (Bound Two-Key Unit)
                            |
                       PolicyIndex
                  (In-memory lookup)
                            |
                     PolicyResolver
                            |
                    ResolvedPolicy[]
                  (Ready for OPA eval)
```

### 2.2 Module Structure

| Module                                               | Purpose                      |
| ---------------------------------------------------- | ---------------------------- |
| `packages/policy/phrases/resolve_policy.py`          | Policy version resolution    |
| `packages/policy/phrases/get_applicable_policies.py` | Context-based policy lookup  |
| `packages/charter/phrases/activate_charter.py`       | Charter lifecycle management |
| `packages/core/phrases/resolve_charter.py`           | Active charter resolution    |

## 3. Seven-Stage Resolution Pipeline

```
Stage 1: Get Candidates     → All entries from PolicyIndex
Stage 2: Jurisdiction Filter → Match context jurisdictions
Stage 3: Action Filter       → Match context action type
Stage 4: Effective Dating    → Check effective_from/until
Stage 5: Charter Override    → Whitelist from Charter.policy_ids
Stage 6: Precedence          → Sort by priority + specificity
Stage 7: Convert             → ResolvedPolicy for OPA
```

## 4. Key Phrases

### 4.1 resolve_charter (core package)

Resolves the active charter for a tenant at a given point in time.

```python
result = await resolve_charter(
    {"tenant_id": tenant_id, "as_of": datetime.now()},
    ctx
)
# Returns: {found: bool, charter_id: UUID, status: str, effective_from: datetime}
```

See: `hub/foundation/packages/core/phrases/resolve_charter.py`

### 4.2 activate_charter (charter package)

Transitions a charter from DRAFT to ACTIVE, automatically retiring the previous active charter.

```python
result = await activate_charter(
    {"charter_id": charter_id, "effective_date": effective_date},
    ctx
)
# Returns: {charter_id, status, effective_from, activated_at, superseded_charter_id}
```

See: `hub/foundation/packages/charter/phrases/activate_charter.py`

### 4.3 resolve_policy (policy package)

Resolves which policy version to use for evaluation based on context.

```python
result = await resolve_policy(
    {"policy_id": "us.fcra.consent", "jurisdiction": "US-NYC"},
    ctx
)
# Returns: {policy_id, definition_hash, adapter_hash, rego_hash, release_version}
```

See: `hub/foundation/packages/policy/phrases/resolve_policy.py`

## 5. Specificity Algorithm

```python
def compute_specificity(entry, ctx) -> tuple[int, int, float]:
    # Jurisdiction: US-NYC (idx=0) scores higher than US (idx=2)
    jurisdiction_score = position_in_context_list(entry.jurisdictions, ctx.jurisdictions)

    # Action: explicit match > wildcard
    action_score = 1 if ctx.action in entry.actions else 0

    # Recency: newer wins ties
    recency = entry.effective_from.timestamp() if entry.effective_from else 0.0

    return (jurisdiction_score, action_score, recency)
```

## 6. Charter Integration

The Charter controls which policies are active for a tenant:

1. `resolve_charter` finds the active charter for tenant
2. Only policies in `Charter.policy_ids` are resolved
3. `activate_charter` handles charter lifecycle transitions

## 7. Integration Points

| Component       | Purpose                                    |
| --------------- | ------------------------------------------ |
| `PolicyEngine`  | Consumes ResolvedPolicy for OPA evaluation |
| `Charter`       | Provides tenant-level policy whitelist     |
| `ADR-008 Gates` | Gates consume resolution results           |
| `Evidence`      | Records which policies were active         |

## 8. References

- **Policy phrases**: `hub/foundation/packages/policy/phrases/`
- **Charter phrases**: `hub/foundation/packages/charter/phrases/`
- **Core phrases**: `hub/foundation/packages/core/phrases/`
- **Related**: ADR-008-policy-gates, ADR-009-opa
