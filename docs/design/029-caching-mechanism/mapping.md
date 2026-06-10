# 029-caching-mechanism - Vocabulary Mapping

## Package Mapping

| Aspect   | Value                                         |
| -------- | --------------------------------------------- |
| Package  | `core`                                        |
| Location | `hub/foundation/packages/core/` |
| Status   | Infrastructure (performance optimization)     |

## Phrases

This is infrastructure. No vocabulary phrases are directly implemented, but the caching mechanism
enables efficient governance evaluation for all vocabulary phrases.

## Control Surfaces

| Surface                    | Description            | Key Integration                                           |
| -------------------------- | ---------------------- | --------------------------------------------------------- |
| All                        | Gate Caching           | `CacheKey.for_gate()` caches gate results; 60s TTL        |
| All                        | Policy Caching         | `CacheKey.for_policy()` caches policy results; 300s TTL   |
| Break Glass Activation     | Break Glass Activation | Cache invalidation by tenant on emergency activation      |
| Privileged Role Escalation | Privileged Role        | Cache invalidation by prefix when role permissions change |
| High-Volume                | Performance            | Consent checks, PII scans benefit from sub-ms cache hits  |

## Code Paths

### Primary Implementation

- `libs/canon/src/canon/utils/cache.py`

### Key Components

| Component                  | Purpose                                  |
| -------------------------- | ---------------------------------------- |
| `CacheKey`                 | Immutable cache key with context hashing |
| `CacheEntry`               | Entry with value, TTL, hits counter      |
| `DecisionCacheConfig`      | Configuration (max_size, TTLs, enabled)  |
| `DecisionCache`            | Thread-safe TTL cache with metrics       |
| `get_decision_cache`       | Singleton accessor                       |
| `configure_decision_cache` | Configuration entry point                |

### Key Methods

| Method                                 | Purpose                 |
| -------------------------------------- | ----------------------- |
| `CacheKey.for_gate()`                  | Create gate cache key   |
| `CacheKey.for_policy()`                | Create policy cache key |
| `DecisionCache.get()`                  | Retrieve cached value   |
| `DecisionCache.set()`                  | Cache value with TTL    |
| `DecisionCache.invalidate()`           | Remove specific entry   |
| `DecisionCache.invalidate_by_prefix()` | Remove matching entries |
| `DecisionCache.invalidate_by_tenant()` | Remove tenant's entries |
| `DecisionCache.metrics`                | Get cache statistics    |

## Default Configuration

| Parameter   | Default | Rationale                                           |
| ----------- | ------- | --------------------------------------------------- |
| max_size    | 10,000  | ~5MB RAM, sufficient for most workloads             |
| gate_ttl    | 60s     | Gates are time-sensitive (consent, waiting periods) |
| policy_ttl  | 300s    | Policies change less frequently                     |
| default_ttl | 300s    | Safe default for unknown types                      |
| enabled     | true    | Caching on by default                               |

## Dependencies

### Upstream

| Component         | Purpose                     |
| ----------------- | --------------------------- |
| `hashlib`         | SHA-256 for context hash    |
| `threading.RLock` | Thread-safe operations      |
| `json`            | Deterministic serialization |

### Downstream

| Component         | Purpose                          |
| ----------------- | -------------------------------- |
| CanonService      | Gate evaluation caching          |
| PolicyEngine      | Policy evaluation caching        |
| EnforcementRunner | Uses cache for governance checks |

## Verification

- **Last verified**: 2026-01-29
- **Design doc version**: 2.0.0
