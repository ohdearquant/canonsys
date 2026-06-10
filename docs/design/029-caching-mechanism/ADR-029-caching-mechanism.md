---
doc_type: ADR
title: "ADR-029: Decision-Scope Caching for Governance Scalability"
version: "2.0.0"
status: active
created: "2026-01-16"
updated: "2026-01-29"
decision_date: "2026-01-16"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-009-opa"
successors:
  - "TDS-029-caching-mechanism"
supersedes: null
superseded_by: null

tags:
  - scalability
  - caching
  - enterprise
  - performance
related:
  - "TDS-029-caching-mechanism"
  - "ADR-009-opa"
  - "CONSTRAINTS-001-enterprise-ilities"
pr: null

quality:
  confidence: 0.95
  sources: 3
  docs: full
---

## Context

### Problem Statement

Enterprise infrastructure requires governance overhead to scale with decision classes, not
individual API calls. The enterprise-ilities constraints framework (CONSTRAINTS-001 Section 5)
mandates:

- **Govern decisions, not every micro-operation**
- **Amortize certification across scopes, time windows, or classes**
- **Avoid linear overhead per API call**
- **Support deterministic capacity planning**

**Red Flag**: "Every API call must synchronously check policy" -- this creates O(n) scaling where n
= request volume, making governance a bottleneck.

**Why This Matters**: At 1000 RPS with 10-50ms gate latency, governance becomes the dominant cost.
Caching provides O(1) amortization.

### Background

**Current State** (before this decision):

- Every gate evaluation was synchronous
- Every policy check was fresh
- No amortization of stable decisions
- O(n) overhead where n = request count

**Driving Forces**:

1. **Performance**: Gate evaluations add 10-50ms latency. At high RPS, this compounds.
2. **Cost**: OPA evaluations consume compute. Caching reduces CPU pressure.
3. **Stability**: Many governance decisions are stable over time windows (consent status, policy
   configurations).
4. **Multi-tenancy**: Tenant-scoped caching prevents cross-tenant pollution while maximizing hit
   rates within tenants.

### Assumptions

1. Many governance decisions are stable within short time windows (seconds to minutes)
2. Gate results depend on: gate_id + tenant_id + scope + context
3. Policy results depend on: policy_id + tenant_id + scope + input_data
4. Context fields like `timestamp`, `request_id` are volatile and should not affect caching
5. Thread-safe access is required for concurrent request handling

### Constraints

| Type        | Constraint                                       | Impact                 |
| ----------- | ------------------------------------------------ | ---------------------- |
| Correctness | Stale cache must not violate compliance          | TTL bounds staleness   |
| Isolation   | Tenants must not see each other's cached results | tenant_id in key       |
| Performance | Cache operations must be sub-millisecond         | In-memory only         |
| Memory      | Cache memory bounded                             | max_size with eviction |

---

## Decision

### Summary

**We will** use an in-memory, thread-safe, TTL-based cache with decision-scope keys that include
tenant isolation and context hashing for cache invalidation.

### Rationale

**Key factors in the decision**:

1. **Scope-Based Keys**: Cache by decision scope (adverse_action, consent) rather than by request,
   enabling amortization across many requests.

2. **Context Hashing**: Hash stable context fields to create deterministic keys while excluding
   volatile fields (timestamps, request_ids).

3. **Differentiated TTLs**: Gates get shorter TTL (60s) because they often depend on time-sensitive
   conditions. Policies get longer TTL (300s) because logic changes less.

4. **In-Memory**: Fastest possible lookups. No network overhead. Acceptable for single-node
   deployments. Distributed cache is future work.

5. **Thread-Safe**: RLock allows concurrent access without corruption.

### Implementation Approach

```
Caching Architecture
--------------------
Component 1: CacheKey
  - Immutable key with kind + id + tenant + scope + context_hash
  - Factory methods: for_gate(), for_policy()
  - Deterministic hashing with volatile field exclusion

Component 2: DecisionCacheConfig
  - max_size: Capacity limit (default 10,000)
  - gate_ttl: Short TTL for dynamic gates (60s)
  - policy_ttl: Longer TTL for stable policies (300s)
  - enabled: Kill switch for cache

Component 3: DecisionCache
  - Thread-safe dict with RLock
  - O(1) get/set operations
  - Eviction on capacity (oldest first)
  - Metrics: hits, misses, evictions, hit_rate

Component 4: Invalidation
  - By key: Single entry removal
  - By prefix: Gate/policy-wide invalidation
  - By tenant: Tenant-scoped purge
  - cleanup_expired(): Background maintenance
```

**Cache Key Format**:

```
{kind}:{id}:{tenant_id}:{scope}:{context_hash}

Examples:
gate:consent.check:tenant_abc:adverse_action:a1b2c3d4e5f6g7h8
policy:nyc_fair_chance:tenant_xyz:hiring_decision:9876543210fedcba
```

### Alternatives Considered

#### Alternative 1: No Caching (Status Quo)

**Description**: Every request evaluates governance freshly.

| Criterion   | Score (1-5) | Notes               |
| ----------- | ----------- | ------------------- |
| Correctness | 5           | Always fresh        |
| Performance | 1           | O(n) overhead       |
| Complexity  | 5           | Nothing to maintain |
| Scalability | 1           | Linear cost growth  |

**Why Not Chosen**: Violates scalability enterprise-ility. Does not amortize.

#### Alternative 2: Redis/Distributed Cache

**Description**: Use Redis or similar distributed cache for shared state.

| Criterion   | Score (1-5) | Notes                      |
| ----------- | ----------- | -------------------------- |
| Correctness | 4           | Network adds failure modes |
| Performance | 3           | Network latency (1-5ms)    |
| Complexity  | 2           | Infrastructure dependency  |
| Scalability | 5           | Horizontal scaling         |

**Why Not Chosen**: Adds infrastructure complexity. Network latency defeats purpose for
sub-millisecond governance checks. May be future work for multi-node deployments.

#### Alternative 3: Request-Scoped Cache

**Description**: Cache only within a single request lifecycle.

| Criterion   | Score (1-5) | Notes                    |
| ----------- | ----------- | ------------------------ |
| Correctness | 5           | No staleness             |
| Performance | 2           | No cross-request benefit |
| Complexity  | 4           | Simple implementation    |
| Scalability | 2           | Limited amortization     |

**Why Not Chosen**: Does not amortize across requests. Minimal benefit for overhead.

### Decision Matrix

| Criterion          | Weight | No Cache | Redis    | Request-Scoped | **In-Memory TTL** |
| ------------------ | ------ | -------- | -------- | -------------- | ----------------- |
| Correctness        | 25%    | 5        | 4        | 5              | **4**             |
| Performance        | 30%    | 1        | 3        | 2              | **5**             |
| Complexity         | 20%    | 5        | 2        | 4              | **4**             |
| Scalability        | 25%    | 1        | 5        | 2              | **4**             |
| **Weighted Total** | 100%   | **2.75** | **3.45** | **3.05**       | **4.30**          |

---

## Consequences

### Positive Consequences

1. **O(1) Governance Overhead**: Cached decisions return instantly. Gate evaluation drops from
   10-50ms to <1us on cache hit.

2. **Decision-Scope Amortization**: Multiple requests sharing the same decision scope benefit from
   single evaluation.

3. **Reduced OPA Load**: Fewer policy evaluations mean lower CPU usage and better capacity planning.

4. **Configurable Freshness**: TTLs can be tuned per environment.

5. **Observable**: Cache metrics (hit_rate, size, evictions) enable performance tuning.

### Negative Consequences

1. **Staleness Window**: Cached results may be stale up to TTL
   - _Mitigation_: Short TTLs (60s for gates), explicit invalidation on policy change

2. **Memory Usage**: Cache consumes RAM (~5MB at 10k entries)
   - _Mitigation_: Bounded max_size with eviction

3. **Single-Node Limitation**: In-memory cache doesn't share across nodes
   - _Mitigation_: Future Redis integration for multi-node deployments

4. **Cache Invalidation Complexity**: Policy changes require explicit invalidation
   - _Mitigation_: TTL ensures eventual consistency

### Neutral Consequences

1. **Per-Node Cache**: Each node has independent cache (cold start after restart)

### Risks

| Risk                         | Likelihood | Impact | Mitigation                                           |
| ---------------------------- | ---------- | ------ | ---------------------------------------------------- |
| Stale cache compliance issue | L          | H      | Short TTLs, explicit invalidation on policy change   |
| Cross-tenant cache pollution | L          | H      | tenant_id in every cache key                         |
| Memory pressure under load   | M          | M      | max_size limit with eviction                         |
| Cache stampede on expiration | M          | L      | Could add jitter; entries created at different times |

### Dependencies Introduced

| Dependency | Type | Version | Stability | Notes                         |
| ---------- | ---- | ------- | --------- | ----------------------------- |
| (none)     | -    | -       | -         | Pure Python, no external deps |

### Migration Impact

**Backwards Compatibility**: Fully compatible. Caching is additive.

**Rollback Plan**: Set `CANON_CACHE_ENABLED=false` for fresh evaluation on every request.

---

## Verification

### Success Criteria

- [x] Gate results cached by scope with 60s TTL
- [x] Policy results cached by scope with 300s TTL
- [x] Tenant isolation via tenant_id in cache key
- [x] Volatile fields excluded from context hash
- [x] Thread-safe operations with RLock
- [x] Eviction on max_size
- [x] Metrics exposed (hits, misses, evictions, hit_rate)

### Metrics to Track

| Metric                    | Baseline | Target | Review Date |
| ------------------------- | -------- | ------ | ----------- |
| Cache hit rate            | N/A      | > 70%  | 2026-02-16  |
| Gate latency p99 (cached) | 10-50ms  | < 1ms  | 2026-02-16  |
| Memory usage              | 0        | < 50MB | 2026-02-16  |
| Cache evictions/hour      | N/A      | < 100  | 2026-02-16  |

### Review Schedule

- **Initial Review**: 2026-02-16 (1 month after implementation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Platform Team

---

## Related Artifacts

### Builds On

- `ADR-009-opa`: OPA integration provides the evaluations being cached
- `CONSTRAINTS-001`: Enterprise-ilities requirements (Section 5 Scalability)

### Impacts

- `TDS-029-caching-mechanism`: Technical specification implementing this decision
- `enforcement/service.py`: CanonService uses cache for gate evaluations
- `utils/opa/engine.py`: Uses cache for policy evaluations

---

## Discussion Record

### Key Questions

**Q1**: What if TTL is too long and compliance changes aren't reflected?

- **Answer**: Gates use 60s TTL. For immediate effect, call `cache.invalidate_by_prefix()` on policy
  update.
- **Raised By**: Compliance review
- **Date**: 2026-01-16

**Q2**: How do we prevent cache stampede when many entries expire simultaneously?

- **Answer**: Not yet implemented. Could add jitter. Current risk is low because entries are created
  at different times.
- **Raised By**: Performance review
- **Date**: 2026-01-16

### Approval Record

| Reviewer | Role    | Decision | Date       |
| -------- | ------- | -------- | ---------- |
| Ocean    | Creator | Approve  | 2026-01-16 |

---

## References

- Implementation: `libs/canon/src/canon/utils/cache.py`
- TDS: [TDS-029-caching-mechanism.md](./TDS-029-caching-mechanism.md)
- CONSTRAINTS-001: Enterprise-ilities framework (Section 5 Scalability)

---

## Vocabulary Mapping

### Package

- **Package**: `core`
- **Location**: `hub/foundation/packages/core/`

### Phrases

This is infrastructure. No vocabulary phrases directly implemented, but enables efficient governance
evaluation for all phrases.

### Control Surfaces

| Surface                    | Description            | Key Integration                                           |
| -------------------------- | ---------------------- | --------------------------------------------------------- |
| All                        | Gate Caching           | `CacheKey.for_gate()` caches gate results; 60s TTL        |
| All                        | Policy Caching         | `CacheKey.for_policy()` caches policy results; 300s TTL   |
| Break Glass Activation     | Break Glass Activation | Cache invalidation by tenant on emergency activation      |
| Privileged Role Escalation | Privileged Role        | Cache invalidation by prefix when role permissions change |
| High-Volume                | Performance            | Consent checks, PII scans benefit from cache hits         |
