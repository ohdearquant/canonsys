---
doc_type: TDS
title: "Technical Design Specification: Compensating Controls Framework"
version: "2.0.0"
status: active
created: "2026-01-20"
updated: "2026-01-29"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: tds
phase: design
scope: L3

predecessors:
  - "ADR-030-compensating-controls"
successors: []
supersedes: null
superseded_by: null

tags:
  - security
  - compensating-controls
  - compliance
  - scoring
related:
  - "ADR-030-compensating-controls"
  - "ADR-016-break-glass"
  - "TDS-006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.95
  sources: 5
  docs: full
---

## 1. Overview

### 1.1 Purpose

The Compensating Controls Framework provides a **scored validation mechanism** for alternative
controls when primary controls (monitoring, DLP, audit logging, security tools) are disabled or
exempted. It quantifies control effectiveness, binds claims to evidence, and enforces minimum
thresholds based on risk tier.

**Core Principle**: "Compensating controls are measured, not asserted."

### 1.2 Scope

**In Scope**:

- CompensatingControl entity with effectiveness scoring
- CompensatingControlType enumeration
- ScoringBreakdown for factor-level transparency
- Scoring algorithm (0-100 scale, weighted factors)
- `verify_compensating_controls()` validation gate
- Integration with break-glass and exception workflows

**Out of Scope**:

- ML-based scoring suggestions (future work)
- Automated recertification (future work)

### 1.3 Platform Invariants

These invariants admit no exceptions:

1. **Scored, not binary**: Effectiveness is a 0-100 score, not yes/no
2. **Evidence-bound**: Every control claim links to sealed CEPs
3. **Threshold enforcement**: Minimum scores vary by risk tier
4. **Computed scoring**: Scores are calculated, not user-asserted
5. **Immutable history**: Historical scores preserved for audit

---

## 2. Architecture

### 2.1 Component Diagram

```mermaid
graph TB
    subgraph "Types"
        CT[CompensatingControlType]
        SB[ScoringBreakdown]
        CC[CompensatingControl]
        CCS[CompensatingControlSet]
        CCR[CompensatingControlsResult]
    end

    subgraph "Actions"
        Create[create_compensating_control]
        Score[score_compensating_control]
        Verify[verify_compensating_controls]
    end

    subgraph "Dependencies"
        CEP[Evidence Chain (CEP)]
        Gate[Gate Framework]
    end

    CC --> SB
    CC --> CT
    CCS --> CC
    CCR --> CCS

    Create --> CC
    Score --> CC
    Verify --> CCS
    Verify --> Gate

    CC --> CEP
```

### 2.2 Module Structure

| Module                                      | Purpose                      |
| ------------------------------------------- | ---------------------------- |
| `features/security/types/compensating.py`   | Type definitions             |
| `features/security/actions/compensating.py` | Actions (create, score)      |
| `features/security/gates/compensating.py`   | verify_compensating_controls |

---

## 3. Technical Specification

### 3.1 CompensatingControlType

```python
class CompensatingControlType(StrEnum):
    """Categories of compensating controls."""

    MONITORING_ALTERNATIVE = "monitoring_alternative"  # Alternative monitoring
    MANUAL_REVIEW = "manual_review"                    # Scheduled human review
    ALERTING = "alerting"                              # Alternative alerting
    ACCESS_RESTRICTION = "access_restriction"          # Reduced scope
    LOGGING_ALTERNATIVE = "logging_alternative"        # Alternative logging
    NETWORK_SEGMENTATION = "network_segmentation"      # Network isolation
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"        # UEBA
    ENCRYPTION = "encryption"                          # Data encryption
    TIME_BOUND = "time_bound"                          # Reduced duration
    APPROVAL_ESCALATION = "approval_escalation"        # Additional approvals
    OTHER = "other"                                    # Other type
```

### 3.2 ScoringBreakdown

```python
@dataclass(frozen=True)
class ScoringBreakdown:
    """Factor-by-factor scoring for transparency."""

    coverage_breadth: int       # 0-100: % of capability covered
    detection_capability: int   # 0-100: threat detection ability
    response_time: int          # 0-100: latency vs primary
    evidence_quality: int       # 0-100: audit trail completeness
    operational_maturity: int   # 0-100: production stability
    notes: str                  # Validator explanation
```

### 3.3 CompensatingControl

```python
@dataclass(frozen=True)
class CompensatingControl:
    """A single compensating control with effectiveness scoring."""

    # Required
    control_id: UUID
    exemption_id: UUID          # Links to exception/exemption
    control_type: CompensatingControlType
    description: str
    coverage_claim: str         # What primary capability this covers
    evidence_refs: tuple[UUID, ...]  # Sealed CEP IDs (immutable)
    scoring_breakdown: ScoringBreakdown
    validated_by: UUID          # Security team validator
    validated_at: datetime

    # Computed
    effectiveness_score: int    # 0-100, computed from breakdown

    # Optional
    tenant_id: UUID | None = None
    expires_at: datetime | None = None
    status: ControlStatus = ControlStatus.ACTIVE
```

### 3.4 Scoring Algorithm

```python
def compute_effectiveness_score(breakdown: ScoringBreakdown) -> int:
    """
    Weighted average of five factors.

    Weights:
    - coverage_breadth:     25%
    - detection_capability: 25%
    - response_time:        20%
    - evidence_quality:     15%
    - operational_maturity: 15%
    """
    return round(
        breakdown.coverage_breadth * 0.25 +
        breakdown.detection_capability * 0.25 +
        breakdown.response_time * 0.20 +
        breakdown.evidence_quality * 0.15 +
        breakdown.operational_maturity * 0.15
    )
```

### 3.5 Score Interpretation

| Score Range | Classification | Meaning                        |
| ----------- | -------------- | ------------------------------ |
| 0-24        | MINIMAL        | Effectively no compensation    |
| 25-49       | INADEQUATE     | Cannot proceed with exemption  |
| 50-74       | PARTIAL        | Requires CISO + Legal approval |
| 75-89       | ADEQUATE       | Standard approval chain        |
| 90-100      | EQUIVALENT     | Minimal additional oversight   |

### 3.6 Risk Tier Thresholds

| Risk Tier | Minimum Score | Max Duration | Approval Required       |
| --------- | ------------- | ------------ | ----------------------- |
| CRITICAL  | 90            | 30 days      | CISO + Legal + CTO      |
| HIGH      | 75            | 90 days      | Security Lead + Manager |
| MEDIUM    | 50            | 180 days     | Manager                 |
| LOW       | 25            | 365 days     | Self-attestation        |

---

## 4. Actions

### 4.1 create_compensating_control

```python
async def create_compensating_control(
    exemption_id: UUID,
    control_type: CompensatingControlType,
    description: str,
    coverage_claim: str,
    evidence_refs: list[UUID],
    scoring_breakdown: ScoringBreakdown,
    ctx: RequestContext,
    *,
    expires_at: datetime | None = None,
    conn: Any | None = None,
) -> CompensatingControl:
    """
    Create a new compensating control with evidence binding.

    Validates:
    - evidence_refs point to sealed CEPs
    - scoring_breakdown values are 0-100
    - User has security team role

    Returns: CompensatingControl with computed effectiveness_score
    """
```

### 4.2 score_compensating_control

```python
async def score_compensating_control(
    control_id: UUID,
    coverage_breadth: int,
    detection_capability: int,
    response_time: int,
    evidence_quality: int,
    operational_maturity: int,
    notes: str,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> CompensatingControl:
    """
    Score or re-score a compensating control.

    Requires: security team role (separation of duties)
    Returns: Updated CompensatingControl
    """
```

### 4.3 verify_compensating_controls (Vocabulary Phrase)

```python
async def verify_compensating_controls(
    exemption_id: UUID,
    risk_tier: RiskTier,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> CompensatingControlsResult:
    """
    GATE: Validate compensating controls for an exemption.

    1. Fetch all controls for exemption_id
    2. Verify evidence_refs are sealed CEPs
    3. Compute aggregate score (max + redundancy bonus)
    4. Check against risk_tier threshold

    Returns:
        CompensatingControlsResult with passed/failed, aggregate_score, details
    """
```

---

## 5. Aggregate Scoring

When multiple compensating controls exist for one exemption:

```python
def compute_aggregate_score(controls: list[CompensatingControl]) -> int:
    """
    Aggregate = max(individual scores) + redundancy bonus

    Redundancy bonus: min(10, (count - 1) * 3)
    - 2 controls: +3
    - 3 controls: +6
    - 4 controls: +9
    - 5+ controls: +10 (capped)

    Rationale: Multiple controls provide defense in depth.
    """
    if not controls:
        return 0

    max_score = max(c.effectiveness_score for c in controls)
    redundancy_bonus = min(10, (len(controls) - 1) * 3)
    return min(100, max_score + redundancy_bonus)
```

---

## 6. Control Surface Coverage

The framework applies to these control surfaces:

**Supplemental Domain**:

- Remove from Monitoring surface
- Disable DLP surface
- Disable Audit Logging surface

**Security Domain**:

- Vulnerability Exemption surface
- Patch Deferral surface
- Security Tool Bypass surface
- Security Exception Grant surface

**Infra Domain**:

- Firewall Rule Bypass surface
- Kubernetes Admission Bypass surface
- Network Segmentation Override surface
- Backup Retention Override surface

**Identity Domain**:

- JIT Role Assignment surface
- Service Account Exception surface

---

## 7. Testing Strategy

### 7.1 Test Coverage

| Component                   | Target |
| --------------------------- | ------ |
| Scoring algorithm           | 100%   |
| Threshold enforcement       | 100%   |
| Evidence binding validation | 100%   |
| Aggregate scoring           | 100%   |
| Security role enforcement   | 100%   |

---

## 8. Vocabulary Mapping

### Package

- **Package**: `controls`
- **Location**: `hub/foundation/packages/controls/`

### Phrases

| Phrase                       | Type   | Pattern | Description                            |
| ---------------------------- | ------ | ------- | -------------------------------------- |
| `derive_control_equivalence` | derive | derive  | Compute equivalence score for controls |
| `check_exploitability`       | check  | verify  | Verify exploitability of control gap   |
| `verify_tool_controls`       | verify | verify  | Verify security tool controls in place |

### Control Surfaces

| Surface                  | Description              | Key Integration                             |
| ------------------------ | ------------------------ | ------------------------------------------- |
| Vulnerability Exemption  | Vulnerability Exemption  | Scored compensating controls for exemptions |
| Security Tool Bypass     | Security Tool Bypass     | verify_tool_controls for bypass approval    |
| Security Exception Grant | Security Exception Grant | Full compensating controls assessment       |
| Remove from Monitoring   | Remove from Monitoring   | Coverage-based compensating controls        |
| Disable DLP              | Disable DLP              | derive_control_equivalence for alternatives |
| Disable Audit Logging    | Disable Audit Logging    | Highest-risk tier, 90+ score required       |

---

## 9. References

- Implementation: `hub/foundation/packages/controls/` (planned)
- ADR: ADR-030-compensating-controls
- Related: ADR-016-break-glass, TDS-006-evidence-chain-cep
- Standard: PCI DSS Compensating Controls guidance
