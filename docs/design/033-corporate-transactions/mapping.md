# 033 Corporate Transactions - Vocabulary Mapping

**Status**: Implemented (vocabulary layer)

## Package Mapping

### Primary Package: `corporate`

**Location**: `hub/domains/corporate/packages/corporate/`

| Component          | Path            | Status      |
| ------------------ | --------------- | ----------- |
| Package definition | `package.py`    | Implemented |
| Service            | `service.py`    | Implemented |
| Exceptions         | `exceptions.py` | Implemented |

### Phrases (Anti-Gaming Derivations)

| Phrase                                  | Path                                               | Regulatory Basis   |
| --------------------------------------- | -------------------------------------------------- | ------------------ |
| `derive_clean_team_required`            | `phrases/derive_clean_team_required.py`            | HSR Act, Sherman   |
| `derive_conditional_findings_addressed` | `phrases/derive_conditional_findings_addressed.py` | SEC, Fiduciary     |
| `derive_carve_out_readiness`            | `phrases/derive_carve_out_readiness.py`            | FTC/DOJ Guidelines |
| `derive_condition_satisfaction_status`  | `phrases/derive_condition_satisfaction_status.py`  | M&A contract law   |

## Control Surface Coverage

| Surface                    | Description                | Phrases                                                               |
| -------------------------- | -------------------------- | --------------------------------------------------------------------- |
| Due Diligence              | Due Diligence              | `derive_clean_team_required`, `derive_conditional_findings_addressed` |
| Integration Planning       | Integration Planning       | DealPhaseGate (CLOSING_CONDITIONS)                                    |
| Carve-Out Compliance       | Carve-Out Compliance       | `derive_carve_out_readiness`                                          |
| Material Change Disclosure | Material Change Disclosure | MaterialChange entity (planned)                                       |
| Closing Conditions         | Closing Conditions         | `derive_condition_satisfaction_status`                                |

## Anti-Gaming Derivation Pattern

The key architectural pattern in this package is **derivation over verification**:

```python
# WRONG: Verification (user can game)
# User asserts: "clean team not required"
# System verifies: check if assertion is valid

# CORRECT: Derivation (anti-gaming)
# System examines: data categories present in deal
# System derives: clean team IS required because competitive_pricing found
result = await derive_clean_team_required(deal_id, ctx)
# result.required = True (derived, not asserted)
# result.reason = CleanTeamReason.COMPETITIVE_PRICING
# result.evidence_hash = "abc123..." (audit trail)
```

### Clean Team Triggers (Hardcoded per HSR/Sherman)

Data categories that always trigger clean team requirement:

- `competitive_pricing`
- `customer_lists`
- `supplier_terms`
- `strategic_roadmap`
- `product_margins`
- `market_strategy`
- `cost_structures`
- `capacity_plans`
- `bidding_history`

## Types

### Enums

| Type                          | Location         | Values                                            |
| ----------------------------- | ---------------- | ------------------------------------------------- |
| `DealPhase`                   | `types/enums.py` | PRE_LOI, LOI_SIGNED, DUE_DILIGENCE, ... CLOSED    |
| `DataSensitivityLevel`        | `types/enums.py` | PUBLIC, CONFIDENTIAL, COMPETITIVELY_SENSITIVE     |
| `CleanTeamReason`             | `types/enums.py` | COMPETITIVE_PRICING, CUSTOMER_LISTS, ...          |
| `FindingStatus`               | `types/enums.py` | OPEN, IN_PROGRESS, REMEDIATED, WAIVED, ...        |
| `CarveOutStatus`              | `types/enums.py` | NOT_STARTED, PLANNING, IN_PROGRESS, APPROVED, ... |
| `ConditionType`               | `types/enums.py` | REGULATORY_APPROVAL, FINANCING, NO_MAC, ...       |
| `ConditionSatisfactionStatus` | `types/enums.py` | PENDING, IN_PROGRESS, SATISFIED, WAIVED, FAILED   |

### Result Dataclasses

| Type                                 | Location           | Purpose                       |
| ------------------------------------ | ------------------ | ----------------------------- |
| `CleanTeamRequiredResult`            | `types/results.py` | Clean team derivation output  |
| `ConditionalFindingsAddressedResult` | `types/results.py` | DD findings derivation output |
| `CarveOutReadinessResult`            | `types/results.py` | Carve-out derivation output   |
| `ConditionSatisfactionResult`        | `types/results.py` | Conditions derivation output  |

## Dependencies

### This Design Depends On

- **ADR-008-policy-gates**: Gate framework for DealPhaseGate
- **ADR-022-consent**: Consent integration for data room access
- **ADR-006-evidence-chain-cep**: Evidence binding for derivations

### Designs That Depend On This

- Due Diligence, Integration Planning, Carve-Out Compliance, Material Change Disclosure, and Closing Conditions control surface implementations
- Future M&A workflow automation
- Data room access control

## Implementation Status

| Component                             | Status      | Notes                      |
| ------------------------------------- | ----------- | -------------------------- |
| corporate pkg                         | Implemented | 4 derivation phrases       |
| DealPhase enum                        | Implemented | 9 phases                   |
| CleanTeamReason enum                  | Implemented | 10 reasons + NOT_REQUIRED  |
| derive_clean_team_required            | Implemented | Anti-gaming derivation     |
| derive_conditional_findings_addressed | Implemented | DD completion check        |
| derive_carve_out_readiness            | Implemented | Divestiture readiness      |
| derive_condition_satisfaction_status  | Implemented | Conditions aggregation     |
| CorporateTransaction entity           | Planned     | Deal lifecycle tracking    |
| DealPhaseGate                         | Planned     | Phase-appropriate blocking |
| DataRoomAccess entity                 | Planned     | Consent-integrated access  |
| MaterialChange entity                 | Planned     | Disclosure tracking        |

## Database Tables (Planned)

```sql
corporate_transactions   -- M&A deal tracking
data_room_access         -- Access grants with clean team status
closing_conditions       -- Per-deal condition tracking
material_changes         -- Disclosure obligations
derivation_log           -- Audit log of all derivations (immutable)
```

## Evidence Integration

All derivations emit evidence:

- `derivation.clean_team_required` - Clean team derivation performed
- `derivation.findings_addressed` - Findings status derived
- `derivation.carve_out_readiness` - Carve-out readiness derived
- `derivation.conditions_status` - Conditions satisfaction derived

Each evidence record includes:

- `deal_id` - Transaction reference
- `result` - Frozen derivation result as JSON
- `evidence_hash` - SHA-256 of data examined
- `derived_at` - Timestamp

## Charter Integration

**Charter**: None currently (derivations are infrastructure-level)

**Control Surfaces**: Due Diligence, Integration Planning, Carve-Out Compliance, Material Change Disclosure, Closing Conditions
