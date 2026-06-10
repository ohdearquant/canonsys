---
doc_type: ADR
title: "ADR-011: Policy Resolution Strategy"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["policy", "charter", "core"]
charters: []
---

# ADR-011: Policy Resolution Strategy

## Status

Accepted

## Context

When multiple policies apply to a single decision context, CanonSys must deterministically resolve
which policies take precedence. Consider a hiring decision in New York City:

- **Federal policy**: FCRA consent requirements (US-wide)
- **State policy**: NY Fair Chance Act waiting periods (NY-wide)
- **Local policy**: NYC LL144 bias audit requirements (NYC-specific)

The system must determine which policies are active, filter by context, resolve conflicts, and
produce a deterministic result regardless of policy registration order.

### Decision Drivers

- Legal precedent: lex specialis (specific overrides general)
- Audit defensibility: resolution must be explainable
- Fail-closed semantics: ambiguity blocks action
- Charter-driven tenant control: tenants activate policies via Charter

## Decision

### D1: Most-Specific-Wins Rule

Specificity is scored on three dimensions:

1. **Explicit priority**: Higher priority wins
2. **Jurisdiction specificity**: US-NYC > US-NY > US
3. **Action specificity**: Explicit action match wins over wildcard
4. **Recency**: Newer effective_from date wins ties

**Implementation**: See vocabulary package `policy` - specifically:

- `resolve_policy` - Resolves which policy version to use for evaluation
- `get_applicable_policies` - Gets all policies matching a context

### D2: Deny-by-Default When Ambiguous

When policy resolution produces ambiguous results, the action is blocked:

- No matching policies but action requires policy check: **DENY**
- Policy evaluation throws exception: **DENY**
- Conflicting policies with equal specificity: **DENY**

**Implementation**: See vocabulary package `policy`:

- `require_policy_pass` - Fails if policy evaluation does not pass
- `require_policy_active` - Fails if policy is not in active state

### D3: Resolution Order (Resource > Role > Tenant)

The resolution hierarchy (most specific to least specific):

1. **Resource-level**: Policies attached to specific entities
2. **Role-level**: Policies based on actor role
3. **Tenant-level**: Default policies in Charter

**Charter Integration**: Charter controls tenant-level policy activation:

- `resolve_charter` - Resolves active charter for tenant
- `activate_charter` - Transitions charter from DRAFT to ACTIVE

### D4: Explicit Policy Chaining

Policies declare relationships via prerequisites and mutual exclusion:

```python
# FCRA flow: consent verified before adverse action
fcra_adverse_action = PolicyIndexEntry(
    policy_id="us.fcra.adverse_action",
    prerequisites=("us.fcra.consent_verified",),
)
```

## Vocabulary Mapping

| Phrase                    | Package   | Purpose                                             |
| ------------------------- | --------- | --------------------------------------------------- |
| `resolve_charter`         | `core`    | Resolve active charter for tenant at point in time  |
| `activate_charter`        | `charter` | Transition charter DRAFT to ACTIVE, retire previous |
| `resolve_policy`          | `policy`  | Resolve which policy version applies for context    |
| `get_applicable_policies` | `policy`  | Get all matching policies for jurisdiction/action   |
| `require_policy_pass`     | `policy`  | Gate that requires policy evaluation to pass        |
| `require_policy_active`   | `policy`  | Gate that requires policy to be active              |
| `evaluate_policy`         | `policy`  | Execute policy against facts via OPA                |

## Alternatives Considered

### Alternative 1: First-Match Wins

Order-dependent, unpredictable. Rejected.

### Alternative 2: Merge All Applicable

Combinatorial explosion, conflicts. Rejected.

## Consequences

### Positive

- Predictable resolution for any jurisdiction combination
- Matches legal intuition (specific overrides general)
- Charter provides tenant-wide baseline control
- Auditable specificity scoring

### Negative

- Scoring algorithm adds complexity
- Policy authors must understand dependency model
- Edge cases in jurisdiction hierarchy require documentation

## References

- **Vocabulary Package**: `hub/foundation/packages/policy/`
- **Vocabulary Package**: `hub/foundation/packages/charter/`
- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Related ADRs**: ADR-008-policy-gates, ADR-009-opa
