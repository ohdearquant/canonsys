# 011 Policy Resolution - Code Mapping

## Overview

The PolicyResolver determines **which policies apply** to a given context through a 7-stage
pipeline. It implements the Two-Key Model where Legal (PolicyDefinition) and Engineering
(PolicyAdapter) must align.

## Vocabulary Packages

| Package   | Path                                             | Purpose                          |
| --------- | ------------------------------------------------ | -------------------------------- |
| `policy`  | `hub/foundation/packages/policy/`  | Policy resolution and evaluation |
| `charter` | `hub/foundation/packages/charter/` | Charter lifecycle management     |
| `core`    | `hub/foundation/packages/core/`    | Charter resolution primitives    |

## Key Phrases

### Policy Package

| Phrase                        | File                                     | Purpose                               |
| ----------------------------- | ---------------------------------------- | ------------------------------------- |
| `resolve_policy`              | `phrases/resolve_policy.py`              | Resolve which policy version applies  |
| `get_applicable_policies`     | `phrases/get_applicable_policies.py`     | Get all matching policies for context |
| `require_policy_pass`         | `phrases/require_policy_pass.py`         | Gate: policy evaluation must pass     |
| `require_policy_active`       | `phrases/require_policy_active.py`       | Gate: policy must be active           |
| `evaluate_policy`             | `phrases/evaluate_policy.py`             | Execute policy against facts via OPA  |
| `evaluate_conditional_policy` | `phrases/evaluate_conditional_policy.py` | Conditional policy evaluation         |

### Charter Package

| Phrase              | File                           | Purpose                           |
| ------------------- | ------------------------------ | --------------------------------- |
| `activate_charter`  | `phrases/activate_charter.py`  | DRAFT -> ACTIVE transition        |
| `create_charter`    | `phrases/create_charter.py`    | Create new charter                |
| `bind_surface`      | `phrases/bind_surface.py`      | Bind control surface to charter   |
| `evaluate_decision` | `phrases/evaluate_decision.py` | Evaluate decision against charter |

### Core Package

| Phrase            | File                         | Purpose                                |
| ----------------- | ---------------------------- | -------------------------------------- |
| `resolve_charter` | `phrases/resolve_charter.py` | Resolve active charter for tenant      |
| `ratify_charter`  | `phrases/ratify_charter.py`  | Ratify charter with required approvals |

## Architectural Patterns

### 1. Two-Key Model

Neither Legal (PolicyDefinition) nor Engineering (PolicyAdapter) alone can enforce. Both must align
via the PolicyIndex.

### 2. Jurisdiction Specificity Ordering

Context jurisdictions are ordered most-specific-first (e.g., US-NYC, US-NY, US). Matching a more
specific jurisdiction gets higher score.

### 3. Charter as Whitelist + Overrides

Charter controls tenant activation:

- Only policies in `charter.policy_ids` are resolved
- Constraint overrides for enforcement/parameters/disable

### 4. Effective Dating

Policies have `effective_from` and `effective_until`. Checked against `ctx.timestamp`.

## Dependencies

**Depends on:**

- `canon.enforcement.executor` - canon_phrase decorator
- `kron.specs` - Operable for phrase specs
- `ADR-009-opa` - OPA policy engine for evaluation

**Depended by:**

- `ADR-012-single-enforcement` - Uses resolver via ServiceContext
- Gate resolution for situational gates

## Key Decisions

1. **In-Memory Index**: PolicyIndex is built in memory. Trade-off: memory vs latency.

2. **Charter Whitelist**: Policies not in charter.policy_ids are filtered out.

3. **Topological Sort**: Kahn's algorithm for prerequisites. Falls back on cycle detection.

4. **Specificity Scoring**: Jurisdiction position determines specificity.
