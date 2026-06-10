---
doc_type: ADR
title: "ADR-009: Embedded Regorus Over OPA Server"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["policy"]
charters: []
---

# ADR-009: Embedded Regorus Over OPA Server

## Status

Accepted

## Context

CanonSys requires policy evaluation for compliance gates in the Decision Kill Chain. Every business
action must pass through policy evaluation before execution. The Open Policy Agent (OPA) ecosystem
provides the industry-standard Rego language for policy authoring.

### Decision Drivers

- **Low Latency**: Policy evaluation sits in the critical path (<10ms p99 required)
- **High Availability**: Cannot be a single point of failure; fail closed on unavailability
- **Thread Safety**: Async Python services use thread pools; policy engines must be thread-safe
- **Privacy**: PII in policy inputs must not leak between evaluations
- **Fail-Closed Semantics**: Ambiguity must resolve to deny

## Decision

### D1: Use Embedded Regorus Instead of OPA Server

Use regorus (Rust-based OPA implementation) with Python bindings via PyO3, embedded in each process.

**Why not OPA Server**: HTTP roundtrip adds 1-10ms latency; introduces single point of failure;
requires connection pool management; cold start on restart.

**Why not OPA Wasm**: Incomplete Rego support; Wasm runtimes in Python add overhead; limited
debugging.

**Implementation**: See `libs/canon/src/canon/utils/opa/engine.py` - specifically:

- `EnginePool` - Thread-safe pool of pre-warmed regorus engines
- `PolicyEngine` - High-level evaluation facade
- `_evaluate_sync()` - Thread-local engine access

### D2: Thread-Safe Pool Pattern

Regorus engines are `!Send` in Rust - they cannot cross threads. Solution: exclusive checkout.

```python
with pool.checkout() as engine:
    engine.set_input(input_data)
    result = engine.eval_rule(query)
```

**Implementation**: `EnginePool.checkout()` context manager with blocking timeout.

### D3: Fail-Closed on Any Error

Policy evaluation errors result in deny, never allow:

```python
except Exception as e:
    if self._fail_closed:
        return PolicyResult(allowed=False, violation_code="EVALUATION_ERROR")
```

### D4: Input Clearing for Privacy

After every evaluation, input is cleared from the engine:

```python
finally:
    engine.set_input({})  # Clear for privacy
```

### D5: Safe Result Decoding

OPA returns results in envelope formats. Naive `bool(result)` is unsafe:

```python
# WRONG: {"value": False} evaluates to True!
bool({"value": False})  # True (non-empty dict)
```

**Implementation**: `libs/canon/src/canon/utils/opa/decoder.py` - `decode_bool()`, `decode_policy()`

## Vocabulary Mapping

| Phrase                         | Package  | Purpose                                      |
| ------------------------------ | -------- | -------------------------------------------- |
| `evaluate_policy`              | `policy` | Execute OPA evaluation via regorus engine    |
| `resolve_policy`               | `policy` | Determine applicable policies for context    |
| `require_policy_pass`          | `policy` | Gate requiring policy evaluation success     |
| `evaluate_conditional_policy`  | `policy` | Evaluate policy with runtime conditions      |
| `get_applicable_policies`      | `policy` | Query policies applicable to current context |
| `verify_policy_not_overridden` | `policy` | Check policy hasn't been superseded          |

## Control Surface Integration

OPA/Regorus is the universal policy runtime. All control surfaces use it for policy evaluation.

| Domain    | Policy Package Pattern | Example Rules                              |
| --------- | ---------------------- | ------------------------------------------ |
| People/HR | `canon.hr.*`           | `deny if { !input.legal_review_complete }` |
| Identity  | `canon.identity.*`     | `deny if { input.duration_hours > max }`   |
| Infra/SRE | `canon.infra.*`        | `deny if { !input.backup_verified }`       |
| Data Gov  | `canon.data.*`         | `deny if { input.legal_hold_present }`     |
| Security  | `canon.secops.*`       | `deny if { !input.root_cause_identified }` |

## Alternatives Considered

### Alternative 1: OPA Server (HTTP API)

Deploy OPA as sidecar, communicate via HTTP REST API.

Rejected: Network latency (1-10ms), single point of failure, serialization overhead, connection
pooling complexity, cold start issues.

### Alternative 2: OPA WebAssembly

Compile Rego to Wasm, run in-process.

Rejected: Incomplete Rego support, build complexity, limited debugging, Python Wasm runtime
overhead.

## Consequences

### Positive

- **Sub-millisecond Latency**: <1ms typical vs 5-15ms with HTTP
- **No Network Dependency**: Works even if network degraded
- **Atomic Initialization**: Pool initializes all or fails entirely
- **Defense in Depth**: Input clearing + poisoned engine replacement + fail-closed

### Negative

- **Deployment Complexity**: Must ship regorus wheel
- **Memory Overhead**: Each engine holds compiled policies (4x for pool of 4)
- **Policy Hot-Reload**: Adding policies drains pool temporarily

### Performance Characteristics

| Metric                 | Value                 |
| ---------------------- | --------------------- |
| Cold start (pool init) | ~100-500ms            |
| Warm evaluation        | <1ms p50, <2ms p99    |
| Pool checkout timeout  | 5s default            |
| Memory per engine      | ~10-50MB              |
| Concurrent evaluations | Pool size (default 4) |

## References

- **Vocabulary Package**: `hub/foundation/packages/policy/`
- **Engine Implementation**: `libs/canon/src/canon/utils/opa/engine.py`
- **Decoder**: `libs/canon/src/canon/utils/opa/decoder.py`
- **Related ADRs**: ADR-008-policy-gates, ADR-011-policy-resolution
- **regorus**: https://github.com/microsoft/regorus
