# Gate Semantics Reference

**Version**: 1.0 | **Status**: Canonical | **Last Updated**: 2026-02-08

Quick reference for behavioral contracts of query and gate prefixes. For the full vocabulary
taxonomy, see `FEATURE_CONVENTIONS.md`.

---

## The Rule

**The prefix determines the behavior. No exceptions.**

| Prefix | Returns | Raises on failure? | Mutates state? |
|--------|---------|-------------------|----------------|
| `verify_*` | `{verified/passed/has_*: bool, reason: str \| None, ...}` | **NEVER** | Never |
| `check_*` | `{status: enum, ...}` | **NEVER** | Never |
| `derive_*` | `{value: T, ...}` | **NEVER** | Never |
| `require_*` | `{satisfied: True, ...}` (success only) | **ALWAYS on failure** | Never |

---

## verify_* -- Binary Validity Check (Query Layer)

**Contract**: Return structured result with boolean outcome. MUST NOT raise for expected outcomes.

```python
async def verify_consent_for_scope(subject_id, scope, ctx) -> dict:
    """Returns {has_consent: True/False, reason: ...}. Never raises."""

    row = await select_one(...)
    if not row:
        # CORRECT: return result, never raise
        return {"has_consent": False, "reason": "No consent token found"}

    return {"has_consent": True, "token_id": row["id"]}
```

**Why**: Callers need to branch on the result without try/except. Queries observe state; they
do not enforce policy.

**Common mistake**:
```python
# WRONG: verify_* must not raise for "not found"
async def verify_config(config_id, ctx):
    row = await select_one(...)
    if not row:
        raise ValueError("Config not found")  # VIOLATION

# CORRECT: return structured result
async def verify_config(config_id, ctx):
    row = await select_one(...)
    if not row:
        return {"verified": False, "reason": "Config not found"}
```

---

## require_* -- Assert Precondition (Gate Layer)

**Contract**: Raise domain exception on failure. Return `satisfied=True` ONLY on success.
The return value is a success receipt, not a boolean check.

```python
from canon.enforcement.errors import RequirementNotMetError

async def require_consent_valid(subject_id, scope, ctx) -> dict:
    """Returns {satisfied: True} or raises. Never returns satisfied=False."""

    result = await verify_consent_for_scope(subject_id, scope, ctx)

    # CORRECT: raise on failure
    if not result["has_consent"]:
        raise ConsentRequiredError(subject_id, scope)

    return {"satisfied": True, "token_id": result["token_id"]}
```

**Why**: Gates enforce policy. If a require_* returns, the condition is proven true.
No further checking needed by the caller.

**Common mistake**:
```python
# WRONG: require_* must not return failure as data
async def require_deadline_met(deadline_at, ctx):
    is_overdue = now() > deadline_at
    return {"satisfied": not is_overdue, "reason": "..."}  # VIOLATION

# CORRECT: raise on failure, return only on success
async def require_deadline_met(deadline_at, ctx):
    if now() > deadline_at:
        raise RequirementNotMetError(
            requirement="deadline_met",
            reason="Deadline has passed",
        )
    return {"satisfied": True}
```

---

## check_* -- Status Evaluation (Query Layer)

**Contract**: Return status or metrics. MUST NOT raise for expected outcomes. MUST NOT modify state.

```python
async def check_waiting_period_elapsed(notice_id, ctx) -> dict:
    """Returns {elapsed: True/False, remaining_hours: int}. Never raises."""

    record = await get_waiting_period(notice_id, ctx)
    elapsed = now() > record.end_at
    remaining = max(0, (record.end_at - now()).total_seconds() / 3600)

    return {"elapsed": elapsed, "remaining_hours": remaining}
```

**Key distinction from verify_***: `verify_*` checks existence/validity (binary).
`check_*` evaluates conditions/status (may include metrics, enums, or multi-valued results).

---

## derive_* -- Compute from Inputs (Query Layer)

**Contract**: Pure computation from provided inputs. No state queries, no side effects, no raises.

```python
async def derive_risk_score(factors, ctx) -> dict:
    """Compute risk score. Pure function, no DB access."""

    score = sum(f.weight * f.value for f in factors) / len(factors)
    return {"score": score, "factor_count": len(factors)}
```

---

## Pattern: verify_* + require_* Pair

The canonical pattern is to implement a verify_* query and wrap it with a require_* gate:

```python
# Query: returns result, never raises
async def verify_executive_attestation(options, ctx) -> dict:
    attestation = await select_one(...)
    if not attestation:
        return {"verified": False, "reason": "No attestation found"}
    return {"verified": True, "attestation_id": attestation["id"]}


# Gate: wraps query, raises on failure
async def require_executive_attestation(options, ctx) -> dict:
    result = await verify_executive_attestation(options, ctx)
    if not result["verified"]:
        raise ExecutiveAttestationRequiredError(reason=result["reason"])
    return result
```

This separation allows callers to choose: query the state (verify_*) or enforce the rule (require_*).

---

## Exception Hierarchy for Gates

```
CanonError
  ValidationError
    RequirementNotMetError    # Generic gate failure (require_*)
  InvariantViolation
    TimingViolation           # Timing-specific (waiting periods, deadlines)
      LifecycleViolation      # Lifecycle-specific (expiry, recertification)
    ConsentViolation          # Consent-specific
```

Use `RequirementNotMetError` for generic gates. Use domain-specific exceptions when available
(e.g., `ConsentExpiredError`, `WaitingPeriodNotElapsedError`).

---

## Enforcement Checklist

When implementing a new phrase, verify:

- [ ] **verify_***: No `raise` statements in the function body (except for unexpected errors like DB connection failures)
- [ ] **verify_***: Returns structured dict with boolean outcome field and optional `reason`
- [ ] **require_***: Has at least one `raise` statement for the failure path
- [ ] **require_***: Return path only reached on success (`satisfied=True`)
- [ ] **check_***: No `raise` statements, no state mutations
- [ ] **derive_***: No DB queries, no side effects, no raises
