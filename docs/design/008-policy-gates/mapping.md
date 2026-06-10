# 008 Policy Gates - Code Mapping

## Overview

Gates are **binary predicates** that block or pass actions. The gate system provides the compliance
checkpoint mechanism for the Decision Kill Chain.

## Vocabulary Packages

### Authorization Package

```
hub/foundation/packages/authorization/
```

| Phrase                           | File                                        | Purpose                 |
| -------------------------------- | ------------------------------------------- | ----------------------- |
| `require_dual_approval`          | `phrases/require_dual_approval.py`          | Require N approvals     |
| `require_access_justification`   | `phrases/require_access_justification.py`   | Gate with justification |
| `verify_approval_chain_complete` | `phrases/verify_approval_chain_complete.py` | Verify chain complete   |
| `require_segregation_analysis`   | `phrases/require_segregation_analysis.py`   | SOD checks              |
| `require_distinct_identities`    | `phrases/require_distinct_identities.py`    | Identity separation     |
| `check_er_clearance`             | `phrases/check_er_clearance.py`             | ER clearance check      |
| `verify_role_approval`           | `phrases/verify_role_approval.py`           | Role-based approval     |
| `require_role_authorized`        | `phrases/require_role_authorized.py`        | Role authorization gate |
| `require_separation_of_duties`   | `phrases/require_separation_of_duties.py`   | SOD enforcement         |
| `verify_delegation_valid`        | `phrases/verify_delegation_valid.py`        | Delegation validation   |
| `require_time_bounded_access`    | `phrases/require_time_bounded_access.py`    | JIT access              |
| `require_release_clearance`      | `phrases/require_release_clearance.py`      | Release approval        |
| `get_approval_chain`             | `phrases/get_approval_chain.py`             | Query approval chain    |

### Policy Package

```
hub/foundation/packages/policy/
```

| Phrase                           | File                                        | Purpose                     |
| -------------------------------- | ------------------------------------------- | --------------------------- |
| `require_policy_pass`            | `phrases/require_policy_pass.py`            | Evaluate and gate on policy |
| `require_policy_active`          | `phrases/require_policy_active.py`          | Check policy state          |
| `require_policy_version_current` | `phrases/require_policy_version_current.py` | Version check               |
| `evaluate_policy`                | `phrases/evaluate_policy.py`                | Execute policy evaluation   |
| `evaluate_conditional_policy`    | `phrases/evaluate_conditional_policy.py`    | Conditional evaluation      |
| `get_applicable_policies`        | `phrases/get_applicable_policies.py`        | Policy discovery            |
| `verify_policy_not_overridden`   | `phrases/verify_policy_not_overridden.py`   | Override check              |
| `derive_risk_tier`               | `phrases/derive_risk_tier.py`               | Risk classification         |

## Supporting Types

### Authorization Types

- `ApprovalChainStatus` - Chain state enum
- `RoleType` - Role definitions
- `ApprovalResult` - Approval outcome

### Enforcement Types (from kron)

- `EnforcementLevel` - HARD_MANDATORY, SOFT_MANDATORY, ADVISORY
- `PhraseResult` - Immutable phrase evaluation result (from `kron.specs.phrase`)
- `PolicyResult` - Policy evaluation result
- `AggregatedResult` - Combined multi-policy result

## Control Surface Usage

| Surface                   | Charter File                                  | Key Phrases                                               |
| ------------------------- | --------------------------------------------- | --------------------------------------------------------- |
| Privileged Escalation     | `identity/privileged_escalation.canon`        | `require_policy_pass`, `require_dual_approval`            |
| Wire Transfer             | `finance/wire_transfer.canon`                 | `require_dual_approval`, `verify_approval_chain_complete` |
| Service Account Privilege | `identity/service_account_privilege.canon`    | `require_policy_pass`, `require_dual_approval`            |

## Architectural Patterns

1. **Binary Decision Model**: Gates return boolean `passed`
2. **Three-Tier Enforcement**: HARD/SOFT/ADVISORY levels
3. **Short-Circuit Execution**: Stop at first failure
4. **Evidence-Grade Results**: Immutable PhraseResult records

## Regulatory Basis

- SOX Section 404 (Segregation of duties)
- PCI DSS v4.0 Req. 8.6 (Multi-factor)
- SOC 2 CC6.1 (Logical access controls)
- ISO 27001 A.9.2 (User access management)

## Dependencies

- ADR-007 (certificates consume gate results)
- ADR-009 (OPA integration)
- ADR-012 (single enforcement point)

## References

- ADR: `docs-shared/canonsys/01_design/008-policy-gates/ADR-008-policy-gates.md`
- TDS: `docs-shared/canonsys/01_design/008-policy-gates/TDS-008-policy-gates.md`
