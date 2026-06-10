---
doc_type: TDS
title: "Technical Design Specification: Corporate Transaction Compliance"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: tds
phase: design
scope: L3

predecessors:
  - "ADR-033-corporate-transactions"
successors: []
supersedes: null
superseded_by: null

tags:
  - corporate-transactions
  - m-and-a
  - anti-gaming
  - due-diligence
related:
  - "ADR-033-corporate-transactions"
  - "ADR-022-consent"
  - "ADR-008-policy-gates"
  - "TDS-006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# Technical Design Specification: Corporate Transaction Compliance

## 1. Overview

### 1.1 Purpose

Corporate transaction compliance provides **M&A workflow management** with anti-gaming derivations
for CanonSys. The system tracks transactions through their lifecycle, enforces phase-appropriate
activities, and derives compliance status from evidence rather than user assertions.

### 1.2 Scope

**In Scope**:

- CorporateTransaction entity and phase lifecycle
- DealPhaseGate for phase-appropriate enforcement
- Anti-gaming derivation actions (clean team, findings, carve-out, conditions)
- DataRoomAccess entity with consent integration (ADR-022)
- Material change disclosure workflow
- Closing conditions satisfaction framework

**Out of Scope**:

- External HSR filing system integration details
- Multi-jurisdiction regulatory approval coordination
- Valuation and financial modeling
- Contract management system integration

### 1.3 Platform Invariants

1. **Anti-Gaming**: Status is derived from evidence, not user assertions
2. **Phase-Gated**: Operations blocked until phase-appropriate
3. **Evidence-Bound**: Every decision links to audit-grade evidence
4. **Consent-Integrated**: Data sharing uses ADR-022 consent model
5. **Derivation over Verification**: System determines compliance, not users

### 1.4 Design Goals

| Priority | Goal                   | Rationale                     |
| -------- | ---------------------- | ----------------------------- |
| P0       | Gun-jumping prevention | HSR Act compliance            |
| P0       | Anti-gaming derivation | Prevent user bypass           |
| P1       | Evidence binding       | Audit-grade compliance trail  |
| P1       | Phase gate enforcement | Appropriate activity blocking |
| P2       | Consent integration    | Unified data access model     |

---

## 2. Architecture

### 2.1 Component Hierarchy

```
CorporateTransaction (Entity)
    +-- transaction_id: UUID
    +-- deal_name: str
    +-- deal_type: DealType
    +-- phase: DealPhase
    +-- buyer_id, seller_id, target_id: FK[Organization]

DealPhaseGate (Vocabulary Phrase)
    +-- required_phase: DealPhase
    +-- check(ctx) -> PhraseResult

DataRoomAccess (Entity)
    +-- transaction_id: FK[CorporateTransaction]
    +-- accessor_id: FK[User]
    +-- access_scope: DataRoomScope
    +-- clean_team_required: bool (derived)
    +-- consent_token_id: FK[ConsentToken]

CleanTeamRequiredResult (Derivation Output)
    +-- required: bool
    +-- reason: CleanTeamReason
    +-- data_categories: tuple[str, ...]
    +-- evidence_hash: str
```

### 2.2 Dependencies

**Internal Dependencies**:

| Component    | Purpose             | Location                      |
| ------------ | ------------------- | ----------------------------- |
| Gate         | Gate abstraction    | `canon.enforcement`      |
| Evidence     | Audit trail         | `canon.evidence`         |
| ConsentToken | Data access consent | `canon.features.consent` |
| CEP          | Evidence binding    | `canon.evidence`         |

**External Dependencies**:

| Library  | Purpose           | Version  |
| -------- | ----------------- | -------- |
| asyncpg  | PostgreSQL driver | >=0.28.0 |
| pydantic | Validation        | >=2.0.0  |

---

## 3. Vocabulary Mapping

### Package: `corporate`

**Location**: `hub/domains/corporate/packages/corporate/`

| Phrase                                  | File                                               | Purpose                   |
| --------------------------------------- | -------------------------------------------------- | ------------------------- |
| `derive_clean_team_required`            | `phrases/derive_clean_team_required.py`            | Derive clean team need    |
| `derive_conditional_findings_addressed` | `phrases/derive_conditional_findings_addressed.py` | Derive DD completion      |
| `derive_carve_out_readiness`            | `phrases/derive_carve_out_readiness.py`            | Derive divestiture status |
| `derive_condition_satisfaction_status`  | `phrases/derive_condition_satisfaction_status.py`  | Derive conditions         |

### Control Surface Coverage

| Surface                       | Phrases Used                                                          | Status      |
| ----------------------------- | --------------------------------------------------------------------- | ----------- |
| Clean Team Required           | `derive_clean_team_required`, `derive_conditional_findings_addressed` | Implemented |
| Closing Conditions Gate       | DealPhaseGate (CLOSING_CONDITIONS)                                    | Planned     |
| Carve-Out Readiness           | `derive_carve_out_readiness`                                          | Implemented |
| Material Change Disclosure    | MaterialChange entity                                                 | Planned     |
| Condition Satisfaction Status | `derive_condition_satisfaction_status`                                | Implemented |

---

## 4. Data Models

### 4.1 Deal Phase Lifecycle

```python
class DealPhase(StrEnum):
    """Phase of M&A deal lifecycle."""

    PRE_LOI = "pre_loi"                      # Pre-letter of intent
    LOI_SIGNED = "loi_signed"                # LOI executed
    DUE_DILIGENCE = "due_diligence"          # Active DD
    DEFINITIVE_AGREEMENT = "definitive_agreement"
    HSR_FILING = "hsr_filing"                # HSR filing submitted
    REGULATORY_REVIEW = "regulatory_review"  # Awaiting approval
    CLOSING_CONDITIONS = "closing_conditions" # Satisfying conditions
    CLOSED = "closed"                        # Transaction complete
    TERMINATED = "terminated"                # Deal terminated
```

### 4.2 Clean Team Derivation Types

```python
class CleanTeamReason(StrEnum):
    """Reason clean team is required (derived)."""

    COMPETITIVE_PRICING = "competitive_pricing"
    CUSTOMER_LISTS = "customer_lists"
    STRATEGIC_ROADMAP = "strategic_roadmap"
    SUPPLIER_TERMS = "supplier_terms"
    EMPLOYEE_COMPENSATION = "employee_compensation"
    PRODUCT_MARGINS = "product_margins"
    MARKET_STRATEGY = "market_strategy"
    COST_STRUCTURES = "cost_structures"
    CAPACITY_PLANS = "capacity_plans"
    BIDDING_HISTORY = "bidding_history"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True, slots=True)
class CleanTeamRequiredResult:
    """Result of clean team derivation."""

    deal_id: UUID
    required: bool                          # Derived, not asserted
    reason: CleanTeamReason                 # Primary trigger
    data_categories: tuple[str, ...]        # All categories found
    sensitivity_triggers: tuple[str, ...]   # Categories that triggered
    evidence_hash: str | None               # Audit trail
    derived_at: datetime | None
```

### 4.3 Condition Satisfaction Types

```python
class ConditionType(StrEnum):
    """Type of closing condition."""

    REGULATORY_APPROVAL = "regulatory_approval"   # HSR, CFIUS
    SHAREHOLDER_APPROVAL = "shareholder_approval"
    FINANCING = "financing"
    NO_MAC = "no_mac"                             # No Material Adverse Change
    DUE_DILIGENCE = "due_diligence"
    THIRD_PARTY_CONSENT = "third_party_consent"
    EMPLOYEE_RETENTION = "employee_retention"
    CARVE_OUT = "carve_out"
    LEGAL_OPINION = "legal_opinion"
    TAX_RULING = "tax_ruling"


class ConditionSatisfactionStatus(StrEnum):
    """Status of condition satisfaction."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SATISFIED = "satisfied"
    WAIVED = "waived"
    FAILED = "failed"
    EXPIRED = "expired"
```

### 4.4 Database Schema (Planned)

```sql
-- Corporate transactions
CREATE TABLE corporate_transactions (
    transaction_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    deal_name VARCHAR(255) NOT NULL,
    deal_type VARCHAR(50) NOT NULL,
    phase VARCHAR(50) NOT NULL DEFAULT 'pre_loi',
    phase_entered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    buyer_id UUID REFERENCES organizations(organization_id),
    seller_id UUID REFERENCES organizations(organization_id),
    target_id UUID NOT NULL REFERENCES organizations(organization_id),
    requires_hsr_filing BOOLEAN NOT NULL DEFAULT FALSE,
    requires_carve_out BOOLEAN NOT NULL DEFAULT FALSE,
    is_cross_competitor BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Data room access
CREATE TABLE data_room_access (
    access_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    transaction_id UUID NOT NULL REFERENCES corporate_transactions(transaction_id),
    accessor_id UUID NOT NULL REFERENCES users(user_id),
    access_scope VARCHAR(50) NOT NULL,
    clean_team_required BOOLEAN NOT NULL,  -- Derived
    consent_token_id UUID REFERENCES consent_tokens(token_id),
    granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE
);

-- Derivation audit log (immutable)
CREATE TABLE derivation_log (
    log_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    derivation_type VARCHAR(100) NOT NULL,
    result JSONB NOT NULL,
    evidence_hash VARCHAR(64) NOT NULL,
    derived_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

---

## 5. Key Operations

### 5.1 derive_clean_team_required

```python
async def derive_clean_team_required(
    deal_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> CleanTeamRequiredResult:
    """Derive whether clean team is required based on data categories.

    Anti-gaming: Examines data categories PRESENT in deal and determines
    whether clean team is required. Users cannot assert "not required".

    Clean team triggered by:
    - competitive_pricing
    - customer_lists
    - supplier_terms
    - strategic_roadmap
    - employee_compensation (if cross-competitor)
    - product_margins
    - market_strategy
    - cost_structures
    - capacity_plans
    - bidding_history
    """
    # 1. Fetch data categories present in deal
    # 2. Check against sensitivity triggers
    # 3. Compute evidence hash
    # 4. Log derivation
    # 5. Return frozen result
```

### 5.2 derive_condition_satisfaction_status

```python
async def derive_condition_satisfaction_status(
    deal_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> ConditionSatisfactionResult:
    """Derive overall satisfaction status of closing conditions.

    Aggregates all condition types and returns:
    - all_satisfied: bool (all conditions satisfied or waived)
    - blocking_conditions: tuple[UUID, ...] (IDs of blocking conditions)
    - conditions_by_type: dict[ConditionType, ConditionSatisfactionStatus]
    """
```

### 5.3 DealPhaseGate Check

```python
class DealPhaseGate:
    """Parameterized gate for transaction phase enforcement."""

    def __init__(self, required_phase: str):
        self.required_phase = DealPhase(required_phase)

    @property
    def gate_id(self) -> str:
        return f"deal.phase.{self.required_phase.value}"

    async def check(self, ctx: RequestContext) -> PhraseResult:
        """Check if transaction is in required phase."""
        # 1. Get transaction from context
        # 2. Compare current phase to required phase
        # 3. Return pass/fail with remediation
```

---

## 6. Integration Points

### 6.1 Consent Integration (ADR-022)

Data room access requires consent verification:

```python
@gates(hard=["consent.data_processing", "deal.phase.due_diligence"])
async def grant_data_room_access(self, req, ctx):
    # 1. Verify consent token exists
    consent = await verify_consent_token(
        VerifyOptions(scope=ConsentScope.DATA_PROCESSING), ctx
    )
    if not consent.has_consent:
        raise ConsentRequired(ConsentScope.DATA_PROCESSING)

    # 2. Derive clean team requirement
    clean_team = await derive_clean_team_required(req.deal_id, ctx)

    # 3. Grant access with derived status
    return await create_data_room_access(
        transaction_id=req.deal_id,
        accessor_id=req.user_id,
        clean_team_required=clean_team.required,
        consent_token_id=consent.token_id,
        ctx=ctx,
    )
```

### 6.2 Evidence Binding (ADR-006)

All derivations produce evidence hash:

```python
def compute_evidence_hash(data_categories: list[str], deal_id: UUID) -> str:
    """Compute SHA-256 hash of evidence used in derivation."""
    payload = {
        "deal_id": str(deal_id),
        "data_categories": sorted(data_categories),
        "derived_at": datetime.utcnow().isoformat(),
    }
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()
```

---

## 7. Testing Requirements

| Test Category                     | Coverage Target |
| --------------------------------- | --------------- |
| Clean team derivation logic       | 100%            |
| Findings addressed derivation     | 100%            |
| Carve-out readiness derivation    | 100%            |
| Condition satisfaction derivation | 100%            |
| Phase gate enforcement            | 100%            |
| Consent integration               | 100%            |
| Evidence hash computation         | 100%            |
| Phase transition validation       | 100%            |

---

## 8. Open Questions

| # | Question                         | Impact            | Status   |
| - | -------------------------------- | ----------------- | -------- |
| 1 | HSR filing status integration    | External API      | Open     |
| 2 | Multi-jurisdiction approvals     | Parallel tracking | Open     |
| 3 | Clean team membership assignment | Role management   | Open     |
| 4 | Material change auto-detection   | Financial feeds   | Resolved |

---

## 9. References

- ADR: `docs-shared/canonsys/01_design/033-corporate-transactions/ADR-033-corporate-transactions.md`
- Corporate package: `hub/domains/corporate/packages/corporate/`
- Related: ADR-022-consent (consent integration)
- Related: ADR-008-policy-gates (gate protocol)
- Related: ADR-006-evidence-chain-cep (evidence binding)
- Hart-Scott-Rodino Act: Antitrust filing/waiting requirements
- Sherman Act Section 1: Information sharing restrictions
