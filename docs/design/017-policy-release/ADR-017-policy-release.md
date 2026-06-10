---
doc_type: ADR
title: "ADR-017: Policy Release Management"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["policy", "charter", "core"]
charters: []
---

# ADR-017: Policy Release Management

## Status

Accepted

## Context

CanonSys enforces compliance through policies evaluated by the embedded Regorus engine. These
policies define the legal and business rules that gate every action in the Decision Kill Chain.
Policy changes carry significant risk:

1. **Compliance impact**: A broken policy can block legitimate business operations
2. **Legal exposure**: A permissive policy can allow non-compliant actions
3. **Audit requirements**: Regulators require proof of which policy version was active when
4. **Multi-tenant isolation**: Different tenants may require different policy versions

### Decision Drivers

- Safe, versioned policy releases with immutability guarantees
- Staged rollout to minimize blast radius
- Rollback capability with full evidence trail
- Two-Key Model separating Legal from Engineering

## Decision

### D1: Semantic Versioning for Policy Packages

**Use semantic versioning (MAJOR.MINOR.PATCH) with date prefix for releases.**

| Version Component | Increment When                                 | Example              |
| ----------------- | ---------------------------------------------- | -------------------- |
| MAJOR (YYYY)      | Breaking changes, new regulatory year          | 2025 -> 2026         |
| MINOR (.MM)       | New policies added, non-breaking enhancements  | 2026.01 -> 2026.02   |
| PATCH (.N)        | Bug fixes, clarifications, no new requirements | 2026.01 -> 2026.01.1 |

**Implementation**: See vocabulary package `policy` - specifically:

- `create_policy_release` - Creates a new draft release with version
- `publish_policy_release` - Freezes content, transitions to published

### D2: Staged Rollout (Canary -> Tenant -> Global)

**Three-stage rollout with explicit progression gates.**

| Stage        | Scope                  | Duration   | Progression Gate                    |
| ------------ | ---------------------- | ---------- | ----------------------------------- |
| CANARY       | 5% of traffic (random) | 1-24 hours | Error rate <0.1%, latency p99 <10ms |
| TENANT_GROUP | Selected tenants       | 1-7 days   | Tenant admin sign-off, no incidents |
| GLOBAL       | All tenants            | Permanent  | Canary + Tenant gates passed        |

**Charter Integration**: Tenants explicitly bind to releases via Charter.

### D3: Two-Key Model for Policy Changes

**Neither Legal nor Engineering can unilaterally modify enforcement behavior.**

- **Key 1: PolicyDefinition** - Legal-authored, WHAT the policy requires
- **Key 2: PolicyAdapter** - Engineering-authored, HOW it's implemented

**Implementation**: See vocabulary package `policy`:

- `create_policy_definition` - Legal creates requirements with citations
- `create_policy_adapter` - Engineering implements with version lock
- `require_policy_version_current` - Validates adapter matches definition version

### D4: Charter Activation Lifecycle

**Charters transition through DRAFT -> RATIFIED -> ACTIVE with evidence.**

**Implementation**: See vocabulary packages `charter` and `core`:

- `activate_charter` - Transitions DRAFT -> ACTIVE, retires previous
- `ratify_charter` - Records signatories, computes ratification_hash

## Vocabulary Mapping

| Phrase                           | Package   | Purpose                                     |
| -------------------------------- | --------- | ------------------------------------------- |
| `create_policy_release`          | `policy`  | Create draft release with version           |
| `publish_policy_release`         | `policy`  | Freeze content, transition to published     |
| `create_policy_definition`       | `policy`  | Legal-authored policy specification (Key 1) |
| `create_policy_adapter`          | `policy`  | Engineering implementation (Key 2)          |
| `require_policy_active`          | `policy`  | Gate: policy must be active                 |
| `require_policy_version_current` | `policy`  | Gate: adapter version matches definition    |
| `activate_charter`               | `charter` | Activate charter, retire previous           |
| `ratify_charter`                 | `core`    | Record signatories with ratification_hash   |

## Alternatives Considered

### Alternative 1: Date-based Versioning (YYYY.MM)

Simple chronological versioning without semantic meaning.

**Rejected because**: No indication of change type - can't distinguish breaking changes from
patches.

### Alternative 2: Big Bang Deployment

Deploy to all tenants at once.

**Rejected because**: Maximum blast radius on bad releases. No gradual validation.

### Alternative 3: Mutable Releases

Allow editing published releases for quick fixes.

**Rejected because**: Breaks immutability guarantees required for audit compliance.

## Consequences

### Positive

- Clear change semantics via semantic versioning
- Limited blast radius via staged rollout
- Neither Legal nor Engineering can bypass controls (Two-Key Model)
- Full evidence trail via ratification_hash

### Negative

- Multiple active release versions to support simultaneously
- More coordination overhead between Legal and Engineering
- Version lock verification adds complexity

## References

- **Vocabulary Package**: `hub/foundation/packages/policy/`
- **Vocabulary Package**: `hub/foundation/packages/charter/`
- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Related ADRs**: ADR-009-opa, ADR-025-charter
