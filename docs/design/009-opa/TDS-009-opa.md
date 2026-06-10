---
doc_type: TDS
title: "Technical Design Specification: OPA/Regorus Engine"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["policy"]
charters: []
---

# Technical Design Specification: OPA/Regorus Engine

## 1. Overview

### 1.1 Purpose

The OPA integration provides **policy evaluation** for the Decision Kill Chain. CanonSys uses
**regorus** (Rust-based OPA) for embedded evaluation without network latency.

### 1.2 Scope

- EnginePool: Thread-safe pool of pre-warmed regorus engines
- PolicyEngine: High-level facade for policy evaluation
- Decoder: Safe result unwrapping with fail-closed semantics
- ResolvedPolicy: Policy ready for evaluation

### 1.3 Design Principles

1. **Embedded Execution**: No network latency, no single-point-of-failure
2. **Thread-Safe**: Pool provides exclusive engine checkout
3. **Fail-Closed**: Any error results in deny
4. **Pre-Warmed**: Policies loaded once at initialization
5. **Privacy-First**: Input cleared after every evaluation

## 2. Architecture

### 2.1 Module Structure

| Module                  | Purpose                                          |
| ----------------------- | ------------------------------------------------ |
| `utils/opa/engine.py`   | EnginePool, PolicyEngine, ResolvedPolicy         |
| `utils/opa/decoder.py`  | Safe result decoding, DecodedDecision            |
| `utils/opa/resolver.py` | PolicyResolver, PolicyIndex                      |
| `utils/opa/gate.py`     | OPAGate for policy-as-gate integration           |
| `enforcement/types.py`  | EnforcementLevel, PolicyResult, AggregatedResult |

### 2.2 Component Diagram

```
EnginePool ──> regorus.Engine (per-thread)
     │
PolicyEngine ──> EnginePool
     │         ├──> decode_policy()
     │         └──> PolicyResult
     │
PolicyResolver ──> ResolvedPolicy ──> PolicyEngine
```

## 3. EnginePool - Thread-Safe Engine Management

### 3.1 The Regorus !Send Constraint

Regorus engines are `!Send` - they cannot cross threads. EnginePool provides **exclusive checkout**:

```python
@contextmanager
def checkout(self) -> Generator[regorus.Engine, None, None]:
    engine = self._available.get(timeout=self._config.checkout_timeout)
    try:
        yield engine
    finally:
        engine.set_input({})  # Clear for privacy
        self._available.put(engine)
```

### 3.2 Configuration

```python
@dataclass(frozen=True, slots=True)
class EnginePoolConfig:
    size: int = 4                    # CANON_OPA_POOL_SIZE
    max_size: int = 16               # CANON_OPA_MAX_POOL_SIZE
    checkout_timeout: float = 5.0    # CANON_OPA_CHECKOUT_TIMEOUT
    fail_closed: bool = True         # Required for compliance
```

### 3.3 Pre-Warming

Engines have policies loaded once at initialization:

```python
def _create_engine(self) -> regorus.Engine:
    engine = regorus.Engine()
    for filename, content in self._policies.items():
        engine.add_policy(filename, content)
    return engine
```

### 3.4 Poisoned Engine Replacement

On exception or failed input clearing, engine is discarded:

```python
if poisoned:
    replacement = self._create_engine()
    self._available.put(replacement)
```

## 4. Decoder - Safe Result Unwrapping

### 4.1 The Envelope Problem

```python
# VULNERABILITY: {"value": False} evaluates to True
bool({"value": False})  # True (non-empty dict)
```

### 4.2 Safe Decoders

```python
def decode_bool(raw: Any, *, default: bool = False) -> bool:
    val = unwrap_opa_result(raw)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    raise OPAResultDecodeError(f"expected boolean, got {type(val)}")
```

### 4.3 Unified Policy Decoding

```python
def decode_policy(
    *,
    decision_raw: Any | None,
    allow_raw: Any | None,
    deny_raw: Any | None = None,
) -> DecodedDecision:
    # Priority: decision object > allow + deny_reasons fallback
```

## 5. PolicyEngine - Evaluation Facade

### 5.1 Single Policy Evaluation

```python
async def evaluate_single(
    self,
    policy: ResolvedPolicy,
    input_data: dict[str, Any],
    rule: str = "allow",
) -> PolicyResult:
    result = await concurrency.run_sync(
        self._evaluate_sync, policy, input_data, rule
    )
    return PolicyResult(
        policy_id=policy.policy_id,
        allowed=result.get("allow", False),
        # ...
    )
```

### 5.2 Fail-Closed on Error

```python
except Exception as e:
    if self._fail_closed:
        return PolicyResult(
            allowed=False,
            violation_code="EVALUATION_ERROR",
            violation_message=f"Policy evaluation failed: {e}",
        )
```

## 6. Vocabulary Integration

The OPA engine is infrastructure that policy phrases query:

| Phrase                    | How It Uses OPA                              |
| ------------------------- | -------------------------------------------- |
| `evaluate_policy`         | Calls `PolicyEngine.evaluate_single()`       |
| `resolve_policy`          | Creates `ResolvedPolicy` for evaluation      |
| `require_policy_pass`     | Gate wrapper around `evaluate_policy`        |
| `get_applicable_policies` | Queries PolicyIndex, prepares for evaluation |

## 7. Integration Points

### 7.1 Dependencies

| Component                      | Purpose                          |
| ------------------------------ | -------------------------------- |
| `regorus`                      | Rust OPA implementation          |
| `kron.utils.concurrency`       | Thread pool execution (run_sync) |
| `canon.enforcement.types` | PolicyResult, AggregatedResult   |

### 7.2 Dependents

| Component                | Purpose                               |
| ------------------------ | ------------------------------------- |
| Policy package phrases   | Use PolicyEngine for evaluation       |
| `012-single-enforcement` | Services use PolicyEngine             |
| Control surface charters | Policy Logic sections compile to Rego |

## 8. Testing Requirements

| Test Category                | Coverage Target |
| ---------------------------- | --------------- |
| Pool initialization          | 100%            |
| Checkout/return cycle        | 100%            |
| Engine poisoning/replacement | 100%            |
| Fail-closed on error         | 100%            |
| Envelope unwrapping          | 100%            |
| Type-safe decoding           | 100%            |
| Privacy (input clearing)     | 100%            |

## 9. References

- **Implementation**: `libs/canon/src/canon/utils/opa/engine.py`
- **Decoder**: `libs/canon/src/canon/utils/opa/decoder.py`
- **Policy Package**: `hub/foundation/packages/policy/`
- **Related**: TDS-008-policy-gates, TDS-011-policy-resolution
