---
doc_type: TDS
title: "Technical Design Specification: Policy Gates"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["authorization", "policy"]
charters: ["privileged_escalation", "wire_transfer", "service_account_privilege"]
---

# Technical Design Specification: Policy Gates

## 1. Overview

### 1.1 Purpose

Gates are **binary predicates** that block or pass actions. The gate system provides the compliance
checkpoint mechanism for the Decision Kill Chain.

### 1.2 Vocabulary Packages

Gate operations are implemented across two vocabulary packages:

```
hub/foundation/packages/authorization/
├── phrases/
│   ├── require_dual_approval.py         # Multi-approval gate
│   ├── require_access_justification.py  # Justification gate
│   ├── verify_approval_chain_complete.py # Chain verification
│   ├── require_segregation_analysis.py  # SOD checks
│   └── check_er_clearance.py            # ER clearance
└── types/

hub/foundation/packages/policy/
├── phrases/
│   ├── require_policy_pass.py           # Policy evaluation gate
│   ├── evaluate_policy.py               # Policy execution
│   └── require_policy_active.py         # Policy state check
└── types/
```

### 1.3 Design Principles

1. **Binary**: `passed` is boolean - no intermediate states
2. **Evidence-Grade**: Every evaluation produces immutable result
3. **Deterministic**: Same context = same result

## 2. Key Phrases

### 2.1 require_dual_approval

Requires N approvals (default 2) for high-risk operations. Raises `RequirementNotMetError` if
insufficient approvals.

**Inputs**: `request_id`, `min_approvers`

**Outputs**: `satisfied`, `approvals_required`, `approvals_received`, `approver_ids`

**Regulatory**: SOX 404, PCI DSS v4.0, SOC 2 CC6.1

See: `authorization/phrases/require_dual_approval.py`

### 2.2 verify_approval_chain_complete

Verifies all required approvals in a chain are complete. Returns verification result (does not
raise).

**Inputs**: `request_id`

**Outputs**: `verified`, `status`, `approvals_required`, `approvals_received`, `completed_at`

**Regulatory**: SOX 404, SOC 2 CC6.1, ISO 27001 A.9.2

See: `authorization/phrases/verify_approval_chain_complete.py`

### 2.3 require_access_justification

Gates access with mandatory justification. Used for soft overrides in the three-tier enforcement
model.

**Inputs**: `request_id`, `justification_type`

**Outputs**: `satisfied`, `justification_id`, `reason`

See: `authorization/phrases/require_access_justification.py`

### 2.4 require_policy_pass

Evaluates a named policy and blocks if it fails.

**Inputs**: `policy_id`

**Outputs**: `satisfied`, `policy_result`

See: `policy/phrases/require_policy_pass.py`

## 3. Three-Tier Enforcement Model

```python
class EnforcementLevel(str, Enum):
    HARD_MANDATORY = "hard_mandatory"  # Blocks, no override
    SOFT_MANDATORY = "soft_mandatory"  # Blocks, allows justified override
    ADVISORY = "advisory"              # Warning only
```

| Level          | On Failure | Override           | Use Case                          |
| -------------- | ---------- | ------------------ | --------------------------------- |
| HARD_MANDATORY | Blocked    | No                 | Consent gates, legal requirements |
| SOFT_MANDATORY | Blocked    | With justification | Business rules, escalation        |
| ADVISORY       | Warning    | N/A                | Best practices                    |

## 4. Control Surface Integration

The authorization phrases appear throughout charter workflows:

| Surface                   | Usage                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------- |
| Privileged Escalation     | `require_policy_pass("privileged_escalation")` in policy phase                        |
| Wire Transfer             | `require_dual_approval()` for significant amounts, `verify_approval_chain_complete()` |
| Service Account Privilege | `require_policy_pass("service_account_privilege")`                                    |

Example from the Wire Transfer surface:

```
phase approval_collection:
    require callback_verification.passed
    require verify_approval_chain_complete()
    when amount_band == "SIGNIFICANT":
        require verify_cfo_approval()
    when urgency == "CRITICAL":
        require require_access_justification()
```

## 5. PhraseResult Structure

Phrase results are immutable frozen dataclasses (from `kron.specs.phrase`):

```python
@dataclass(frozen=True, slots=True)
class PhraseResult:
    gate: str              # Gate identifier
    passed: bool           # Binary result
    message: str | None    # Human-readable explanation
    checked_at: datetime   # Timestamp
```

## 6. Short-Circuit Execution

Gates execute sequentially and short-circuit on first failure. All results up to failure point are
recorded in `RequestContext.gate_results`.

## 7. Anti-Patterns

- **Do NOT** return confidence scores from gates
- **Do NOT** allow bypass without break-glass
- **Do NOT** skip recording gate results in RequestContext
- **Do NOT** mutate PhraseResult after creation

## 8. References

- **ADR**: ADR-008-policy-gates
- **Package**: `hub/foundation/packages/authorization/`
- **Package**: `hub/foundation/packages/policy/`
- **Charters**: `hub/charters/surfaces/`
