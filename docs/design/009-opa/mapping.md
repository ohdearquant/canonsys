# 009 OPA/Regorus Engine - Code Mapping

## Overview

The OPA integration uses **regorus** (Rust-based OPA) for embedded policy evaluation. This is
infrastructure that policy phrases query - the engine that makes vocabulary executable.

## Vocabulary Package

**Package**: `hub/foundation/packages/policy/`

| Phrase                         | File                                      | Purpose                            |
| ------------------------------ | ----------------------------------------- | ---------------------------------- |
| `evaluate_policy`              | `phrases/evaluate_policy.py`              | Execute OPA evaluation via regorus |
| `resolve_policy`               | `phrases/resolve_policy.py`               | Determine applicable policies      |
| `require_policy_pass`          | `phrases/require_policy_pass.py`          | Gate requiring policy success      |
| `require_policy_active`        | `phrases/require_policy_active.py`        | Verify policy is active            |
| `evaluate_conditional_policy`  | `phrases/evaluate_conditional_policy.py`  | Evaluate with conditions           |
| `get_applicable_policies`      | `phrases/get_applicable_policies.py`      | Query applicable policies          |
| `verify_policy_not_overridden` | `phrases/verify_policy_not_overridden.py` | Check not superseded               |
| `derive_risk_tier`             | `phrases/derive_risk_tier.py`             | Calculate risk tier                |

## Infrastructure Code

| Module                             | Purpose                         |
| ---------------------------------- | ------------------------------- |
| `libs/canon/src/canon/utils/opa/engine.py`   | EnginePool, PolicyEngine facade |
| `libs/canon/src/canon/utils/opa/decoder.py`  | Safe result decoding            |
| `libs/canon/src/canon/utils/opa/resolver.py` | PolicyResolver, PolicyIndex     |
| `libs/canon/src/canon/utils/opa/gate.py`     | OPAGate for policy-as-gate      |
| `libs/canon/src/canon/enforcement/types.py`  | EnforcementLevel, PolicyResult  |

## Key Classes

### Engine Pool (engine.py)

- `EnginePoolConfig` - Configuration: size, policies_path, checkout_timeout
- `EnginePool` - Thread-safe pool of pre-warmed regorus engines
  - `checkout()` - Context manager for exclusive engine use
  - `get_thread_engine()` - Thread-local engine access

### Policy Engine (engine.py)

- `ResolvedPolicy` - Policy ready for evaluation
- `PolicyEngine` - High-level evaluation facade
  - `evaluate_single()` - Single policy evaluation
  - `evaluate_policies()` - Multi-policy aggregation

### Decoder (decoder.py)

- `unwrap_opa_result()` - Unwrap OPA/regorus envelopes
- `decode_bool()` - Boolean with fail-closed
- `decode_policy()` - Unified decoding entry point
- `DecodedDecision` - Normalized output

## Architectural Patterns

### 1. Thread-Safe Pool

Regorus engines are `!Send`. Pool provides exclusive checkout:

```python
with pool.checkout() as engine:
    engine.set_input(input_data)
    result = engine.eval_rule(query)
```

### 2. Fail-Closed Semantics

Any error = deny:

```python
if self._fail_closed:
    return PolicyResult(allowed=False, ...)
```

### 3. Privacy: Clear Input After Eval

```python
finally:
    engine.set_input({})
```

### 4. Safe Envelope Unwrapping

Never use `bool(raw_result)` - use `decode_bool()`.

## How Phrases Use OPA

```python
# In evaluate_policy phrase
async def evaluate_policy(policy_id: str, input_data: dict, ctx: Ctx) -> PolicyResult:
    engine = get_policy_engine()
    policy = await resolve_policy(policy_id, ctx)
    return await engine.evaluate_single(policy, input_data)
```

## Dependencies

**Depends on**:

- `regorus` - Rust OPA implementation
- `kron.utils.concurrency` - Thread pool execution

**Depended by**:

- Policy package phrases
- All control surface policy evaluation
