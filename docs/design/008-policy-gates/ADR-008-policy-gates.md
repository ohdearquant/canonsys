---
doc_type: ADR
title: "ADR-008: Policy Gates Design"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["authorization", "policy"]
charters: ["privileged_escalation", "wire_transfer", "service_account_privilege"]
---

# ADR-008: Policy Gates Design

## Status

Accepted

## Context

CanonSys implements compliance-as-substrate through the Decision Kill Chain. Gates are the
compliance checkpoints - every action must pass through explicit verification before execution.

### Decision Drivers

- Binary pass/fail decisions (no ambiguity)
- Evidence-grade records for every evaluation
- Support dynamic gate registration and parameterization
- Integrate with jurisdiction-aware policy enforcement

## Decision

### D1: Binary Pass/Fail Semantics

Gates return boolean `passed` - no intermediate states, no confidence scores.

**Implementation**: See vocabulary package `authorization` - all phrases return `satisfied: bool` or
`verified: bool`:

- `require_dual_approval` - Returns `satisfied: bool` with approval chain metadata
- `verify_approval_chain_complete` - Returns `verified: bool` with chain status

### D2: Three-Tier Enforcement Levels

Inspired by HashiCorp Sentinel: HARD_MANDATORY, SOFT_MANDATORY, ADVISORY.

| Level          | On Failure | Override           | Use Case                          |
| -------------- | ---------- | ------------------ | --------------------------------- |
| HARD_MANDATORY | Blocked    | No                 | Consent gates, legal requirements |
| SOFT_MANDATORY | Blocked    | With justification | Business rules, escalation paths  |
| ADVISORY       | Warning    | N/A                | Best practices, recommendations   |

**Implementation**: See vocabulary package `policy`:

- `require_policy_pass` - Evaluates policy with enforcement level

### D3: Access Justification for Soft Overrides

When soft gates block, justification is required for override.

**Implementation**: See vocabulary package `authorization`:

- `require_access_justification` - Gates access with mandatory justification

**Charter Integration**: Control surfaces using this pattern:

- the Privileged Escalation surface - Privileged escalation (requires justification for INCIDENT codes)
- the Wire Transfer surface - Wire transfer (requires justification for CRITICAL urgency)
- the Service Account Privilege surface - Service account privilege (requires justification for privilege scope)

## Vocabulary Mapping

| Phrase                           | Package         | Purpose                                      |
| -------------------------------- | --------------- | -------------------------------------------- |
| `require_dual_approval`          | `authorization` | Require N approvals for high-risk operations |
| `require_access_justification`   | `authorization` | Gate access with mandatory justification     |
| `verify_approval_chain_complete` | `authorization` | Verify all required approvals obtained       |
| `require_policy_pass`            | `policy`        | Evaluate named policy with enforcement       |
| `evaluate_policy`                | `policy`        | Execute policy evaluation returning result   |

## Control Surface Integration

| Surface                    | Charter                              | Key Phrases Used                                                                          |
| -------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------- |
| Privileged Escalation      | `privileged_escalation.canon`        | `require_dual_approval`, `require_policy_pass`                                            |
| Wire Transfer              | `wire_transfer.canon`                | `require_dual_approval`, `verify_approval_chain_complete`, `require_access_justification` |
| Service Account Privilege  | `service_account_privilege.canon`    | `require_policy_pass`, `require_dual_approval`                                            |

## Alternatives Considered

### Alternative 1: Confidence Scores

Gates return probability (0.0-1.0) instead of boolean.

**Rejected**: Threshold debates, legal ambiguity - "Was consent obtained?" has a binary answer.

### Alternative 2: All-or-Nothing Enforcement

Every gate blocks on failure with no override path.

**Rejected**: No flexibility for low-risk warnings or escalation workflows.

### Alternative 3: Manual Gate Registration

Explicit `registry.add(gate)` calls required.

**Rejected**: Easy to forget, boilerplate; auto-registration via `__init_subclass__` preferred.

## Consequences

### Positive

- Crystal clear audit trail ("Gate X passed: True")
- No debates about confidence thresholds
- Hard requirements cannot be bypassed (legal compliance)
- Soft requirements support escalation workflows

### Negative

- Edge cases must be handled by gate logic itself
- Soft override requires justification tracking
- Must classify each gate into appropriate enforcement level

## References

- **Vocabulary Package**: `hub/foundation/packages/authorization/`
- **Vocabulary Package**: `hub/foundation/packages/policy/`
- **Charters**: `hub/charters/surfaces/`
- **Related ADRs**: ADR-007 (certificates consume gate results), ADR-009 (OPA integration)
