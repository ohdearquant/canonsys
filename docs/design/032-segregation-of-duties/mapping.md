# 032 Segregation of Duties - Vocabulary Mapping

**Status**: Implemented (vocabulary layer)

## Package Mapping

### Primary Package: `authorization`

**Location**: `hub/foundation/packages/authorization/`

| Component          | Path            | Status      |
| ------------------ | --------------- | ----------- |
| Package definition | `package.py`    | Implemented |
| Service            | `service.py`    | Implemented |
| Exceptions         | `exceptions.py` | Implemented |

### Phrases

| Phrase                           | Path                                        | Regulatory Basis |
| -------------------------------- | ------------------------------------------- | ---------------- |
| `require_segregation_analysis`   | `phrases/require_segregation_analysis.py`   | SOX 302/404      |
| `require_distinct_identities`    | `phrases/require_distinct_identities.py`    | SOC 2 CC6.1      |
| `require_dual_approval`          | `phrases/require_dual_approval.py`          | SOX 302/404      |
| `require_separation_of_duties`   | `phrases/require_separation_of_duties.py`   | SOX 302/404      |
| `verify_approval_chain_complete` | `phrases/verify_approval_chain_complete.py` | SOC 2 CC6.1      |
| `check_er_clearance`             | `phrases/check_er_clearance.py`             | Employment law   |
| `require_role_authorized`        | `phrases/require_role_authorized.py`        | SOC 2 CC6.1      |
| `verify_delegation_valid`        | `phrases/verify_delegation_valid.py`        | SOC 2 CC6.1      |
| `require_time_bounded_access`    | `phrases/require_time_bounded_access.py`    | SOC 2 CC6.1      |

## Control Surface Coverage

| Surface                   | Description               | Phrases                                                   |
| ------------------------- | ------------------------- | --------------------------------------------------------- |
| Candidate Advancement     | Candidate advancement     | `require_segregation_analysis`, `check_er_clearance`      |
| Comment/Document Approval | Comment/document approval | `require_distinct_identities`                             |
| Adverse Action Sign-Off   | Adverse action sign-off   | `require_dual_approval`, `verify_approval_chain_complete` |

## Financial Control Surfaces (SOX)

| PRD | Surface                            | SoD Requirement                          |
| --- | ---------------------------------- | ---------------------------------------- |
| 84  | PROMOTE_TO_PRIVILEGED_FINANCE_ROLE | `verify_no_sod_conflict`                 |
| 09  | LARGE_WIRE_TRANSFER_EXECUTION      | wire_initiator vs wire_approver          |
| 56  | LARGE_PAYMENT_APPROVAL             | payment_requestor vs payment_approver    |
| 57  | REFUND_APPROVAL_ABOVE_THRESHOLD    | refund_requestor vs refund_approver      |
| 60  | FINANCIAL_GUARANTEE_ISSUANCE       | guarantee_requestor vs risk_assessor     |
| 61  | BUDGET_LOCK_UNLOCK                 | budget_modifier vs budget_approver       |
| 62  | CAP_TABLE_CHANGE                   | cap_table_preparer vs cap_table_approver |
| 63  | EQUITY_ISSUANCE                    | equity_preparer vs equity_approver       |
| 64  | EQUITY_CANCELLATION                | equity_preparer vs legal_reviewer        |
| 70  | SIGN_COMPLIANCE_ATTESTATION        | controls_tester vs attestation_signer    |
| 91  | DISABLE_AUDIT_LOGGING_FOR_SYSTEM   | logging_operator vs logging_approver     |

## Architectural Patterns

### Vocabulary Feature Pattern

```python
async def require_segregation_analysis(
    initiator_id: UUID,
    approver_id: UUID,
    required_level: SeparationLevel,
    ctx: RequestContext,
) -> SeparationResult:
    """Compute separation level between two parties."""
```

### Conflict Matrix Pattern

```python
@dataclass(frozen=True)
class SoDConflictRule:
    rule_id: UUID
    role_a: str
    role_b: str
    conflict_type: ConflictType
    sox_control_id: str
```

### Evidence Integration

All SoD checks emit evidence:

- `sod.check_performed` - When SoD check executed
- `sod.conflict_detected` - When conflict found
- `sod.exemption_used` - When exemption applied
- `sod.grant_blocked` - When role grant denied

## Dependencies

### This Design Depends On

- **ADR-008-policy-gates**: Gate framework
- **ADR-015-jit-role**: JIT role integration
- **ADR-016-break-glass**: Emergency override
- **TDS-006-evidence-chain-cep**: CEP binding for exemptions

### Designs That Depend On This

- All finance control surfaces requiring maker-checker
- JIT role grant flow
- PRD-84 privileged finance role promotion

## Implementation Status

| Component         | Status      | Notes                       |
| ----------------- | ----------- | --------------------------- |
| authorization pkg | Implemented | 9 phrases                   |
| SoDConflictMatrix | Planned     | Versioned conflict rules    |
| SoDExemption      | Planned     | Time-bounded exemptions     |
| Role aggregation  | Planned     | Cross-system (Workday, SAP) |
| JIT integration   | Planned     | ADR-015 hook                |

## Database Tables (Planned)

```sql
sod_conflict_matrices   -- Matrix versions
sod_conflict_rules      -- Individual conflict rules
sod_exemptions          -- Documented exceptions
sod_check_log           -- Audit log (immutable)
```

## Charter Integration

**Charter**: None (infrastructure-level authorization)

**Control Surfaces**: Candidate Advancement, Comment/Document Approval, Adverse Action Sign-Off, plus all SOX finance surfaces
