# CanonSys Technical Architecture

**Version**: Schema v1.0 (Frozen) **Status**: Production **Audience**: Engineers, Technical
Architecture Review

---

## Executive Summary

CanonSys is a **System of Decisional Record** for employment actions. The architecture enforces
compliance at runtime through binary gates, generates immutable Decision Certificates as proof
artifacts, and versions the complete decision state for deterministic replay.

This document defines the technical primitives that make non-compliant actions architecturally
constrained. Without a valid certificate, execution permission cannot be granted.

**Responsibility Allocation**: CanonSys certifies process integrity. Legal owns policy intent.
Managers own judgment. CanonSys enforces that decisions occur only inside approved, provable
process boundaries.

---

## 1. Core Abstractions

### 1.1 Evidence Atoms

The smallest unit of proof. Each atom is:

- **Immutable**: Content-addressed by SHA-256 hash
- **Typed**: Structured schema per evidence category
- **Timestamped**: Designed for RFC 3161 third-party TSA integration. In deployments where a TSA is
  configured, certificate hashes are anchored using RFC 3161 tokens. Internal monotonic time
  provides ordering when TSA unavailable; batch anchoring creates **separate immutable evidence
  entries** referencing the original hashes (no modification of existing records)
- **Tenant-scoped**: Isolated by organization boundary

```
Evidence Atom = {
    id: UUID,
    type: EvidenceType,
    content_hash: SHA256,
    timestamp: Timestamp,  // RFC3161 when TSA enabled
    tenant_id: FK[Tenant],
    data: JSONB  // Type-specific payload
}
```

Evidence types include: `consent_grant`, `policy_acknowledgment`, `gate_evaluation`,
`human_decision`, `model_output`, `comparator_analysis`, `certification_event`.

### 1.2 Evidence Packet

Raw materials for decision certification. An Evidence Packet is:

- **Aggregated**: Collection of Evidence Atoms bound to a decision context
- **Provisional**: Mutable until certification event
- **Complete**: All required atoms present before compilation

```
Evidence Packet = {
    decision_id: UUID,
    atoms: list[Evidence],
    status: provisional | complete,
    completeness_check: PhraseResult
}
```

**Immutability Rule (Critical)**:

- **Append-only during provisional phase**: Atoms can be added, never removed
- **Frozen at certification**: Once CERTIFICATE_MINTED, packet is immutable
- **Audit trail for drops**: If an atom is invalidated (e.g., consent withdrawn), a `AtomWithdrawal`
  record is appended with rationale — the original atom remains but is marked withdrawn, not deleted

```
AtomWithdrawal = {
    original_atom_id: UUID,
    withdrawn_at: Timestamp,
    reason: WithdrawalReason,  // consent_revoked | legal_hold_conflict | duplicate
    withdrawn_by: ActorRef,
    successor_atom_id: UUID | null  // If replaced, not just dropped
}
```

> **Why**: Dropping atoms without trace enables evidence tampering. Prosecutors will ask "what was
> removed and why?" The audit trail answers that question.

**Analogy**: Evidence Packet is roasted cacao. Decision Certificate is chocolate.

### 1.3 Decision Certificate

The primary product artifact. A Decision Certificate is:

- **Minted once**: Single generation event, never regenerated
- **Immutable**: No edits, no invalidation
- **Supersedable**: May only be superseded by subsequent certified action referencing prior
  `decision_id`

```
Decision Certificate = {
    certificate_id: UUID,
    decision_id: UUID,
    schema_version: "1.0",

    // Decision Context
    action_type: ActionType,
    subject_id: FK[Person],
    actor_id: FK[User],

    // Computational State (frozen)
    model_identity: {
        name: str,                    // e.g., "gpt-4-turbo-2024-04-09"
        version_hash: SHA256,         // Provider-reported or our build hash
        prompt_chain_hash: SHA256,
        identity_source: IdentitySource  // self_hosted | provider_reported
    },
    input_fingerprints: list[SHA256],
    policy_version: str,
    policy_adapter_hash: SHA256,           // Exact build hash of enforcement logic
    tenant_policy_activation_hash: SHA256, // Proves what was activated at decision time
    jurisdiction: JurisdictionCode,

    // Gate Evaluations
    gates_passed: list[GateEvaluation],

    // Evidence Binding
    evidence_ids: list[FK[Evidence]],

    // Certification
    minted_at: Timestamp,  // RFC3161 for certification boundary
    certificate_hash: SHA256,
    supersedes: UUID | null
}
```

**Critical Property**: This document does not justify intent; it proves process.

**Model Identity Provenance**:

| Source              | What We Record                        | What We Can Prove                        |
| ------------------- | ------------------------------------- | ---------------------------------------- |
| `self_hosted`       | Our build hash + weights              | Exact model used (full control)          |
| `provider_reported` | API-reported name/version + call hash | API called, response hash, not internals |

> **Limitation**: For third-party LLMs (OpenAI, Anthropic, etc.), we record what the provider
> reports but cannot verify internal model state. The `prompt_chain_hash` proves what we sent; the
> response hash proves what we received. Model internals remain opaque. This is a known limitation
> of all API-based AI governance.

### 1.4 Decision Certificate Lifecycle (Canonical)

The single source of truth for certificate state transitions:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   PROVISIONAL          GATED            MINTED        SUPERSEDED│
│   ───────────────────────────────────────────────────────────── │
│                                                                 │
│   Evidence Packet  →   Gates Pass   →   CERTIFICATE_MINTED   →  │
│   (mutable)            (all binary)     (immutable)             │
│                                                                 │
│   - Atoms collected    - No partial     - Temporal cliff        │
│   - Incomplete OK      - No override    - Hash-sealed           │
│   - Editable           - All-or-block   - Never revoked         │
│                                                                 │
│                                         Only superseded by new  │
│                                         certificate referencing │
│                                         prior decision_id       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Lifecycle Stages**:

1. **Provisional** (Evidence Packet): Atoms are collected, packet is mutable, completeness not yet
   verified. Status: `provisional`.

2. **Gated**: All required gates evaluated. Binary pass/block. If any gate fails, action blocked—no
   execution path. If all pass, proceed to minting.

3. **Minted** (`CERTIFICATE_MINTED` event): The temporal cliff. Certificate hash computed, timestamp
   recorded, immutability begins. No edits, no invalidation.

4. **Superseded** (optional): A subsequent certified action may supersede this certificate by
   referencing its `decision_id`. The original remains in history; it is never deleted or revoked.

**Supersession Doctrine**: Certificates are never revoked, only superseded. The historical record is
append-only. A superseding certificate does not erase the prior—it extends the decision chain.

### 1.5 Gates

Binary predicates evaluated at runtime. Each gate:

- **Blocks or passes**: No intermediate states, no override path
- **Deterministic**: Same inputs produce same result
- **Logged**: Every evaluation becomes an Evidence Atom

```
Gate = {
    gate_id: str,
    predicate: (Context) -> bool,
    failure_reason: str,
    required_evidence: list[EvidenceType]
}

GateEvaluation = {
    gate_id: str,
    evaluated_at: Timestamp,  // RFC3161 for certification; internal time for interim
    passed: bool,
    context_hash: SHA256
}
```

**Architectural Invariant**: If a gate fails, the action cannot proceed to certified execution.
Break-glass provides an emergency path but produces a different certificate class (BREAK_GLASS) with
degraded defensibility. This is enforced at the service layer (`services/{workflow}/service.py`)
before any state mutation. No superadmin bypass exists; DB-level writes without gate passage produce
orphan records that cannot mint certificates.

**Comparator Constraint (Critical Invariant)**:

Comparator outputs are non-authorizing evidence. They cannot satisfy a gate, trigger an action, or
determine outcome. They may only contextualize a human-authored rationale.

**Multi-Layer Enforcement**:

| Layer       | Mechanism                                                                  |
| ----------- | -------------------------------------------------------------------------- |
| Type System | `ComparatorResult` is not a valid input type for `Gate.evaluate`           |
| Runtime     | Middleware rejects any `GateEvaluation` where `source_type` = `comparator` |
| Audit       | Compliance scan flags any certificate with comparator-only gates           |
| Test Suite  | `test_comparator_cannot_satisfy_gate()` asserts rejection                  |

```python
# Runtime invariant (services/gate/middleware.py)
def validate_gate_source(evaluation: GateEvaluation) -> None:
    if evaluation.source_type == SourceType.COMPARATOR:
        raise InvariantViolation(
            "Comparator outputs cannot satisfy gates. "
            "Human rationale required."
        )
```

> **Why this matters**: The core thesis is that HUMANS make employment decisions. Comparators
> provide context; they do not authorize. Any path where a comparator output directly satisfies a
> gate collapses the entire defensibility claim.

---

## 2. Two-Key Model

Separation of powers for the AI era. Consequential AI decisions are high-security events.

### 2.1 Policy Library Model

**Canonical Ownership**:

- **CanonSys**: Authors and maintains the Policy Library (statutory workflows, gate requirements)
- **Customer Legal**: Activates which library policies apply to which workflows/jurisdictions

This separation keeps the platform a technology layer rather than a professional-services engagement.

#### 2.1.1 Policy Library Release (CanonSys-Owned)

CanonSys ships versioned Policy Definitions as a product artifact:

```
PolicyLibraryRelease = {
    release_id: str,                    // e.g., "2026.01"
    release_hash: SHA256,               // Hash of all policy definitions

    policy_definitions: list[PolicyDefinition],

    counsel_reviewed_by: str,           // CanonSys external counsel
    released_at: Timestamp
}

PolicyDefinition = {
    policy_id: str,
    version: str,
    action_type: ActionType,
    jurisdictions: list[JurisdictionCode],

    required_gates: list[{
        gate_id: str,
        description: str,              // Legal language
        evidence_required: list[EvidenceType]
    }],

    waiting_periods: dict[EventType, Duration]
}
```

**Library Contents**: WARN Act, NYC LL144, CA WARN, GDPR Art 22, Colorado SB 205, etc.

#### 2.1.2 Tenant Policy Activation (Customer Legal-Owned)

Customer Legal approves which library policies apply to their organization:

```
TenantPolicyActivation = {
    tenant_id: FK[Tenant],
    policy_id: str,                     // References PolicyDefinition
    release_id: str,                    // Which library release

    scope: ActivationScope,             // Which workflows covered
    jurisdiction_map: dict[str, list[JurisdictionCode]],

    activated_by: str,                  // Customer Legal approver
    activated_at: Timestamp,
    activation_hash: SHA256             // Proves what was activated
}
```

**Customer Legal's Role**: Select which library policies apply, map them to jurisdictions and
workflows, and sign activation for audit trail. They configure applicability — CanonSys authors the
logic, defines gate predicates, and owns enforcement code.

### 2.2 Engineering Enforcement

**Owner**: Engineering **Artifact**: Policy Adapter

Engineering implements the executable constraint. Policy Adapters translate legal intent into binary
gates using **declarative configuration**.

#### 2.2.1 Declarative Policy Engine (OPA/Rego)

We use Open Policy Agent (OPA) with Rego for policy enforcement:

```rego
# Standard Statutory Adapter: WARN Act (60-day notice)
package canonsys.statutory.warn

default allow = false

allow {
    input.action_type == "termination"
    input.employee_count >= 100
    input.notice_days >= 60
    input.documentation.warn_notice_sent == true
}

deny[msg] {
    input.action_type == "termination"
    input.employee_count >= 100
    input.notice_days < 60
    msg := sprintf("WARN Act requires %d days notice, only %d provided",
                   [60, input.notice_days])
}
```

**Why Declarative**:

| Custom Python Code       | Declarative OPA/Rego         |
| ------------------------ | ---------------------------- |
| Per-customer services model | Platform model |
| Per-customer engineering | Standard templates activated |
| Deployment = code push   | Deployment = config push     |
| Audit = code review      | Audit = policy review        |

#### 2.2.2 Statutory Adapter Library

Customers configure parameters, not logic:

```yaml
# Customer configuration (NOT code)
statutory_adapters:
  - id: warn_act
    enabled: true
    parameters:
      employee_threshold: 100
      notice_period_days: 60

  - id: nyc_ll144
    enabled: true
    parameters:
      audit_frequency_months: 12
      summary_publication_required: true
```

**Library Contents**:

| Adapter      | Jurisdiction | Key Parameters                      |
| ------------ | ------------ | ----------------------------------- |
| `warn_act`   | US Federal   | employee_threshold, notice_days     |
| `nyc_ll144`  | NYC          | audit_frequency, publication_reqs   |
| `ca_warn`    | California   | notice_days (90), covered_employers |
| `gdpr_art22` | EU           | review_required, consent_scope      |
| `co_sb205`   | Colorado     | disclosure_timing, appeal_rights    |

**No Custom Code Path**: Engineering maintains Rego templates. Customers toggle and configure.
Policy updates are configuration pushes, not deployments.

#### 2.2.3 Policy Adapter Interface

```python
class PolicyAdapter:
    """Declarative policy evaluation via OPA."""

    def __init__(self, policy: PolicyDefinition):
        self.policy = policy
        self.opa_client = OPAClient()

    async def evaluate(self, context: DecisionContext) -> PhraseResult:
        """Evaluate all configured adapters. Binary result."""
        input_doc = self._build_opa_input(context)
        result = await self.opa_client.evaluate(
            package=f"canonsys.tenant.{context.tenant_id}",
            input=input_doc
        )
        if not result.allow:
            return PhraseResult(passed=False, deny_reasons=result.deny)
        return PhraseResult(passed=True)
```

### 2.3 Separation Principle

Neither party can unilaterally change both:

- Legal cannot modify enforcement logic
- Engineering cannot modify policy requirements
- Changes require coordinated update with version increment

This mirrors nuclear launch protocols and high-security financial systems.

---

## 3. Three-Layer Stack

### 3.1 Constitution Layer

**Definition**: The rules all parties agree to.

The Constitution defines:

- Who can act (role-based permissions)
- With what data (input governance)
- Using what tools (model governance)
- Under what constraints (policy governance)

```
Constitution = {
    version: str,
    tenant_id: FK[Tenant],

    policies: list[PolicyDefinition],
    roles: list[RoleDefinition],
    model_allowlist: list[ModelIdentity],

    effective_from: Timestamp,
    ratified_by: list[Signatory]
}
```

**Property**: In an autonomous enterprise, trust is not assumed. It is compiled.

### 3.2 Execution Ledger Layer

**Definition**: The executable manifestation of the Constitution.

The Execution Ledger is:

- **Append-only**: No deletions, no modifications
- **Hash-chained**: Each entry references prior entry hash (**per-tenant chains** — each tenant has
  an independent hash chain for isolation and easier explanation under discovery)
- **Time-ordered**: Strict temporal sequence (RFC 3161 at certification boundaries)

```
LedgerEntry = {
    entry_id: UUID,
    prior_hash: SHA256,

    event_type: EventType,
    event_data: JSONB,

    timestamp: Timestamp,
    entry_hash: SHA256
}
```

Event types: `action_initiated`, `gate_evaluated`, `evidence_bound`, `human_decision_recorded`,
`certificate_minted`, `certificate_superseded`.

**Property**: The evidence chain is time. Immutable, append-only, non-semantic.

### 3.3 Evidence Atoms Layer

**Definition**: Non-repudiable proof that workflows executed as agreed.

This layer contains the typed evidence that populates Decision Certificates:

- Consent grants with scope and version
- Policy acknowledgments with timestamp
- Gate evaluations with context hash
- Human decisions with rationale
- Model outputs with input fingerprints

**Property**: The past is immutable; we certify what it means.

### 3.4 GDPR Compliance: Crypto-Shredding Protocol

**The Conflict**: GDPR Article 17 ("Right to Erasure") requires deletion on request. Immutable
ledgers appear incompatible.

**The Solution**: **Crypto-Shredding** — per-subject encryption where key deletion renders data
unreadable while preserving ledger integrity.

**Mechanism**:

1. **Key Management**: Maintain mutable `SubjectKeyStore` (PostgreSQL). Each `Person` entity has a
   unique AES-256 encryption key.
2. **Log Encryption**: Any PII destined for the immutable log (e.g., candidate name in metadata) is
   encrypted with the subject's key BEFORE hashing/logging.
3. **Erasure Protocol**: Upon Article 17 request, destroy the subject's key from `SubjectKeyStore`.
   On-ledger data remains (hash chain intact) but becomes mathematically unreadable.

```
Crypto-Shredding Flow:
    PII → Encrypt(subject_key) → Hash → Ledger Entry
                    ↓
    Article 17 Request → Delete(subject_key)
                    ↓
    Ledger intact, PII unreadable (cryptographic garbage)
```

**Legal Basis**: CNIL and EDPB guidance supports this approach. Data "put beyond use" satisfies
erasure requirements while preserving audit chain integrity.

**Result**: Immutability + GDPR compliance. The hash chain proves the decision process existed; the
underlying PII is cryptographically erased.

### 3.5 Retention and Legal Hold

**Architecture**:

| Layer             | Contents                            | Retention         |
| ----------------- | ----------------------------------- | ----------------- |
| Proof Layer       | Hashes, structural metadata, no PII | Indefinite        |
| PII Payload Layer | Encrypted blobs, per-tenant keys    | Policy-controlled |

**Retention Controls**:

```
RetentionPolicy = {
    tenant_id: FK[Tenant],
    evidence_type: EvidenceType,
    retention_days: int,              // e.g., 2555 (7 years)
    legal_hold_exempt: bool           // If false, legal hold overrides
}

LegalHold = {
    hold_id: UUID,
    tenant_id: FK[Tenant],
    scope: HoldScope,                 // Subject, matter, date range
    created_by: str,                  // Legal counsel
    created_at: Timestamp,
    released_at: Timestamp | null
}
```

**Deletion Flow** (respects legal holds):

```
Retention period expired
        ↓
Check: Any active LegalHold covering this evidence?
        ↓
If hold: BLOCK deletion (evidence preserved)
If no hold: Execute crypto-shred (key destroyed)
        ↓
Log: EVIDENCE_RETENTION_ACTION { action: "shredded" | "held" }
```

**Data Minimization**: PII is encrypted at the boundary before entering the proof layer. The proof
layer contains hashes and structural metadata only. This design ensures the immutable layer holds
minimal personal data while preserving full audit capability.

---

## 4. Gates vs Audits

### 4.1 Upstream Enforcement

Traditional compliance operates in **observation mode**: log violations after the fact, investigate,
remediate.

CanonSys operates in **enforcement mode**: unauthorized actions cannot obtain execution permission.
Violations result in uncertified, defensibility-degraded states that are visible in all downstream
systems.

| Aspect    | Audit Model       | Gate Model             |
| --------- | ----------------- | ---------------------- |
| When      | After action      | Before action          |
| Response  | Investigate       | Block                  |
| Evidence  | Reconstructed     | Generated as byproduct |
| Override  | Policy exceptions | No execution path      |
| Liability | Remediation cost  | Prevention             |

### 4.2 Gate Properties

**Binary**: Pass or block. No partial compliance, no risk scores. Break-glass is not an override —
it's a separate, louder path that produces a different certificate class.

```python
# CORRECT
if not await gate.evaluate(context):
    raise GateBlocked(gate.gate_id, gate.failure_reason)

# WRONG - probabilistic
if compliance_score < 0.8:  # NO PERCENTAGES
    ...
```

**Deterministic**: Same context produces same result. Gates do not depend on:

- Time of day (except explicit waiting periods)
- System load
- Previous unrelated decisions
- Probabilistic model outputs for permission

**No Override Path**: The system does not ask humans to comply. It prevents non-compliant states
from existing.

### 4.3 Gate Examples

```python
# Eligibility Gate - PIP initiation
class PIPEligibilityGate:
    """Manager cannot initiate PIP unless prerequisites exist."""

    async def evaluate(self, context: PIPContext) -> bool:
        return (
            await self.has_documented_feedback(context) and
            await self.waiting_period_elapsed(context) and
            await self.jurisdiction_allows(context) and
            await self.no_protected_status_conflict(context)
        )

# Consent Gate - AI processing
class AIProcessingGate:
    """AI cannot process without root lawful basis."""

    async def evaluate(self, context: ProcessingContext) -> bool:
        consent = await self.get_consent(context.subject_id)
        return (
            consent is not None and
            consent.scope.includes(context.processing_purpose) and
            not consent.revoked
        )
```

### 4.4 Anti-Rubber Stamp Heuristics

**The Problem**: Regulators flag "rubber stamping" — approving in 0.5 seconds proves the AI made the
decision, not the human. GDPR Article 22 and EEOC guidance require "meaningful" human review.

**The Solution**: Enforce minimum review duration and attention tracking.

**Mechanism**:

1. **Minimum Review Time**: `MinimumReadTime = WordCount / 200 (WPM)`. The "Approve" button is
   disabled until timer elapses.
2. **Scroll Telemetry**: User must scroll to bottom of evidence container (100% viewport exposure
   verified).
3. **Disagreement Tracking**: Log when human overrides comparator suggestion. If agreement rate is
   100%, flag for review.
4. **Attestation**: Decision Certificate includes `review_duration_ms` and `scroll_depth_percent`.

```python
class MeaningfulReviewGate:
    """Human review must be substantive, not token."""

    MIN_REVIEW_SECONDS = 5  # Absolute minimum

    async def evaluate(self, context: ReviewContext) -> bool:
        read_time = len(context.evidence_text.split()) / 200 * 60  # seconds
        min_required = max(self.MIN_REVIEW_SECONDS, read_time)

        return (
            context.review_duration_seconds >= min_required and
            context.scroll_depth_percent >= 100
        )
```

**Dashboard Metric**: Comparator Disagreement Rate. If a manager agrees 100% of the time, they are
flagged for training or audit.

**Result**: "Meaningful human oversight" is provable, not claimed.

---

## 5. Decision State Versioning

### 5.1 The Problem

AI systems are probabilistic. Model updates, prompt changes, and training data shifts can alter
outputs. Post-hoc explanation is insufficient when the decision context has evolved.

### 5.2 The Solution

Version the complete decision state, not just the outcome.

```
Decision State = {
    // Model Identity
    model_name: str,
    model_version_hash: SHA256,  // Provider/build artifact identity, not "GPT-4"

    // Prompt Chain
    prompt_template_hash: SHA256,
    prompt_parameters: dict,

    // Input Data
    input_fingerprints: list[{
        input_id: str,
        content_hash: SHA256,
        schema_version: str
    }],

    // Policy Context
    policy_version: str,
    jurisdiction: JurisdictionCode,

    // Gate State
    gate_evaluations: list[GateEvaluation],

    // Human Interventions
    human_decisions: list[{
        actor_id: FK[User],
        decision: str,
        rationale: str,
        timestamp: Timestamp
    }]
}
```

### 5.3 Properties

**Deterministic Replay**: Given the same Decision State, the same certificate would be generated.
The execution context is frozen at certification time.

**No Retroactive Fixes**: You cannot fix a decision. You can only issue a new one that supersedes
the prior certificate.

**Schema Versioning**: Changes to Decision State structure require `SCHEMA_VERSION` increment and
backwards compatibility guarantees.

```python
SCHEMA_VERSION = "1.0"

# Version changes require:
# 1. Backwards-compatible migration path
# 2. Legal sign-off on new requirements
# 3. Engineering validation of gate implementations
```

---

## 6. Deterministic Permissioning for Probabilistic Systems

### 6.1 The Thesis

AI systems are probabilistic. That is fine for prediction. But once AI enters execution
paths--advancing candidates, triggering workflows, approving actions--probability becomes risk.

### 6.2 Historical Pattern

Important systems converge toward determinism. Not because the world is deterministic, but because
**permission has to be**.

| Era      | System               | Determinism Layer                  |
| -------- | -------------------- | ---------------------------------- |
| Finance  | Trading              | Position limits, circuit breakers  |
| Aviation | Flight control       | Redundant systems, checklists      |
| Nuclear  | Launch authorization | Two-key model, physical interlocks |
| AI       | Decision execution   | CanonSys                          |

### 6.3 The AI Wrapper

CanonSys wraps probabilistic AI in deterministic permissioning:

```
┌─────────────────────────────────────────────────┐
│                 DETERMINISTIC LAYER             │
│  ┌─────────────────────────────────────────┐   │
│  │           PROBABILISTIC AI              │   │
│  │                                         │   │
│  │   Model proposes → Output generated     │   │
│  │                                         │   │
│  └─────────────────────────────────────────┘   │
│                      │                          │
│                      ▼                          │
│  ┌─────────────────────────────────────────┐   │
│  │           GATE EVALUATION               │   │
│  │                                         │   │
│  │   Policy constrains → Binary pass/block │   │
│  │                                         │   │
│  └─────────────────────────────────────────┘   │
│                      │                          │
│                      ▼                          │
│  ┌─────────────────────────────────────────┐   │
│  │           EVIDENCE BINDING              │   │
│  │                                         │   │
│  │   Evidence binds → Decision emits       │   │
│  │                                         │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Flow**:

1. AI proposes (probabilistic)
2. Policy constrains (deterministic)
3. Evidence binds (immutable)
4. Decision emits (certified)

The AI accelerates decisions. The gates ensure only permissible decisions execute.

---

## 7. Enforcement vs Observation Mode

### 7.1 Observation Mode (Traditional)

```
Action → Log → Audit → Investigate → Remediate
         ↓
    [Violation may have occurred]
         ↓
    [Evidence reconstructed]
         ↓
    [Liability incurred]
```

Problems: Evidence is reconstructed after violations occur. Audit becomes adversarial. Compliance
becomes a cost center.

### 7.2 Enforcement Mode (CanonSys)

```
Intent → Gate Evaluation → [Block] or [Proceed]
                              ↓
                    [No execution path]
                    [No violation possible]

         [Proceed] → Evidence Generated → Certificate Minted
                              ↓
                    [Audit-ready by default]
                    [Evidence as byproduct]
```

Properties: Evidence is generated as enforcement side-effect. Non-compliant states cannot exist.
Audit becomes verification. Compliance becomes infrastructure.

### 7.3 Architectural Consequence

Logs are produced as enforcement byproduct. Gates are the control mechanism.

```python
# Enforcement mode
async def initiate_pip(context: PIPContext) -> Decision:
    # Gate evaluation (enforcement)
    gate_result = await eligibility_gate.evaluate(context)

    if not gate_result.passed:
        # Action blocked - no execution path
        raise GateBlocked(gate_result)

    # Evidence generated as byproduct
    evidence = await bind_evidence(context, gate_result)

    # Decision emitted with proof
    return await mint_certificate(context, evidence)
```

---

## 8. HRIS Integration: JIT Role Enforcement

### 8.1 The Enforcement Pattern

CanonSys sits adjacent to HRIS but authoritative over it.

**HRIS provides**: Business Processes, Security Groups, Condition Rules, Integration Framework, and
time-bound role assignments (the integration point).

**CanonSys adds**: Cryptographic certificates, external policy attestations, short-lived execution
capabilities, and immutable evidence guarantees — what HRIS cannot provide.

### 8.2 Workday Integration Pattern: Async-to-Sync Permit Gate

**The Problem**: Standard Workday Business Processes cannot pause mid-transaction for synchronous
external API calls without heavy custom work (Workday Studio).

**The Solution**: Use native Workday Custom Validation Rules with a pre-validation step.

**Mechanism**:

1. **Custom Object**: Create `CanonSys_Permit` custom object on Worker profile
2. **Integration Trigger**: Add "Verify Compliance" step early in Hire/Terminate BP
3. **Write-Back**: CanonSys validates and writes signed token: `CanonSys_Permit.status = "VALID"`
4. **Gate**: Final approval step has Condition Rule:
   `Entry Condition: CanonSys_Permit.status == "VALID"`

**EIB Compatibility**: Enterprise Interface Builder bulk loads DO trigger Business Process
validation rules (unless explicitly bypassed via integration system user privileges). This ensures
bulk actions don't slip through.

**User Experience**: If validation fails, the "Submit" or "Approve" button is disabled, or a hard
error displays: "Error: Pre-requisite CanonSys Certificate missing."

### 8.3 Permit Token Pattern (One-to-One Binding)

**The Problem**: JIT roles are bound to user + scope + time window. A user with a 5-minute role
could execute multiple actions.

**The Solution**: Bind at the transaction boundary.

Each certificate mint issues a **Permit Token** — a single-use capability:

```json
{
  "iss": "canonsys",
  "jti": "unique-nonce",
  "action": "TERMINATE_WORKER",
  "subject_worker_id": "WD-Worker-12345",
  "actor_user_id": "WD-User-67890",
  "certificate_id": "ht-cert-abc",
  "exp": "2026-01-10T15:04:00Z"
}
```

**Enforcement flow**:

```
Certificate mints + Permit Token issued (subject-bound, single-use)
        ↓
HRIS Business Process requires Permit to complete
        ↓
HRIS calls CanonSys redemption endpoint
        ↓
CanonSys: atomic check-and-consume (ISSUED → CONSUMED)
        ↓
First redemption succeeds; second attempt fails
```

**Redemption logic (idempotent for retries)**:

```python
def redeem_permit(token, worker_id, actor_id, bp_instance_id):
    claims = verify_signature(token)
    assert claims["subject_worker_id"] == worker_id
    assert claims["action"] == "TERMINATE_WORKER"
    assert now() < claims["exp"]

    jti = claims["jti"]
    existing = db.get_permit_state(jti)

    if existing is None:
        # First attempt: atomic consume
        db.insert(jti, state="CONSUMED", bp_instance_id=bp_instance_id, receipt_id=new_uuid())
        ledger.append("PERMIT_REDEEMED", {...})
        return ALLOW(receipt_id=existing.receipt_id)

    if existing.state == "CONSUMED":
        # Retry handling: same BP instance = idempotent success
        if existing.bp_instance_id == bp_instance_id:
            return ALLOW(receipt_id=existing.receipt_id)  # Same receipt, safe retry
        else:
            return DENY("PERMIT_ALREADY_USED_BY_DIFFERENT_BP")  # Different BP = fraud attempt

    return DENY("INVALID_PERMIT_STATE")
```

**Why Idempotent**: HRIS integrations retry on timeouts. If Workday retries after a successful
consume but before seeing the response, naive logic would block the retry and create a stuck state.
Idempotent redemption returns the same receipt for the same `bp_instance_id`, preventing false
negatives.

**Result**: One certificate = one permit = one completed action. Same-BP retries succeed;
different-BP reuse fails.

### 8.4 Execution Confirmation (Two-Event Model)

**The Problem**: Certificate issuance proves authorization. But does the action actually complete in
Workday? Failures can occur after permit redemption (HRIS errors, network issues, user
cancellation).

**The Solution**: Separate immutable events for authorization vs. execution:

```
CERTIFICATE_MINTED (temporal cliff)
        ↓
    CanonSys authorized the action
        ↓
PERMIT_REDEEMED
        ↓
    HRIS attempted execution
        ↓
HRIS_EXECUTION_CONFIRMED (or HRIS_EXECUTION_FAILED)
        ↓
    Workday confirmed completion
```

**Evidence Structure**:

```
HRIS_EXECUTION_CONFIRMED = {
    confirmation_id: UUID,
    certificate_id: UUID,              // Links to authorization
    hris_transaction_id: str,          // Workday BP instance ID
    action_type: ActionType,
    subject_id: FK[Person],
    confirmed_at: Timestamp,
    confirmation_source: "workday_callback" | "shadow_audit" | "manual_reconciliation"
}
```

**Detection Methods**:

| Method           | Mechanism                                          | Latency   |
| ---------------- | -------------------------------------------------- | --------- |
| Workday Callback | Integration step calls CanonSys after BP complete | Real-time |
| Shadow Audit     | Reconciliation engine detects completion in logs   | ≤1 hour   |
| Manual Reconcile | Compliance reviews pending permits                 | Manual    |

**Export Representation**: Certificate exports show both events:

```
Certificate Status: CERTIFIED
  - Authorized: 2026-01-10T14:00:00Z (CERTIFICATE_MINTED)
  - Executed: 2026-01-10T14:02:30Z (HRIS_EXECUTION_CONFIRMED)
```

**Important**: Both events are immutable. If execution fails after authorization, a separate
`HRIS_EXECUTION_FAILED` event is logged. The certificate proves authorization was granted; execution
confirmation proves the action completed.

### 8.5 JIT Execution Roles (Secondary Hardening)

JIT roles provide defense-in-depth but are not the primary binding:

1. **Remove standing execution power** — No human has unconditional action authority
2. **Replace with JIT role** — `Termination_Executor_JIT` assigned only when certificate exists
3. **Role revoked after permit redemption** — Revoked by scheduled removal via API (not native TTL
   expiry)

```
Certificate + Permit issued
        ↓
JIT role granted via API (add to security group)
        ↓
User executes action with Permit
        ↓
Permit consumed (one-to-one enforced)
        ↓
Role revoked via API (scheduled removal)
```

**Defense layers**:

- **Layer 1 (primary)**: Permit is consumed, so it's dead
- **Layer 2 (hardening)**: JIT role revoked by scheduled API call after successful redemption

**Implementation note**: Workday supports programmatic add/remove of user-based security group
membership through User-Based Security Group Event (Web Service). JIT is implemented by grant +
scheduled revoke, not native TTL.

This works across: UI, API, Admins, Service accounts.

### 8.6 Break-Glass Protocol

Emergency overrides exist but are maximally visible:

**Break-Glass Flow**:

1. Admin invokes `BreakGlassExecute`
2. Must provide: Reason code, Attestation text (typed, not clicked), Case ID
3. System:
   - Executes action via HRIS
   - Issues **Break-Glass Certificate** (different class: `BREAK_GLASS`)
   - Auto-notifies Legal / ER
   - Forces post-hoc review workflow

```
Break-Glass Certificate = {
    certificate_type: "BREAK_GLASS",
    attestation: str,  // Typed justification
    review_required_by: "Legal",
    defensibility_state: "DEGRADED",
    notified: ["Legal", "ER", "Audit"],
    exportable: false  // Cannot include in counsel packages without Legal sign-off
}
```

**Break-glass ≠ bypass**. Break-glass = different, louder path that changes the evidence state.

**Blast Radius Rule**: BREAK_GLASS certificates are **non-exportable** to external counsel packages
without explicit Legal sign-off. This makes break-glass a visibly painful choice — the decision
exists in the system but cannot be weaponized in defense without additional attestation.

### 8.7 Downstream Enforcement

Any downstream consumer of decision data must verify certification:

```python
def export_case_file(worker_id: UUID, action: str) -> CaseFile:
    cert = get_certificate(worker_id, action)

    if cert is None:
        return CaseFile(
            status="UNCERTIFIED",
            defensibility="DEGRADED",
            usable_in_defense=False
        )

    if cert.certificate_type == "BREAK_GLASS":
        return CaseFile(
            status="BREAK_GLASS",
            defensibility="PROVISIONAL",
            review_required=True
        )

    return CaseFile(
        status="CERTIFIED",
        defensibility="FULL",
        certificate=cert
    )
```

**Result**: HRIS remains system-of-record. CanonSys becomes system-of-decisional-truth.

### 8.8 Coverage Matrix

**Covered (when configured)**:

| Path                                 | Enforcement Point      | Status  |
| ------------------------------------ | ---------------------- | ------- |
| Terminate Employee BP (UI)           | Permit validation step | Covered |
| Terminate Employee BP (API)          | Same BP triggered      | Covered |
| Mass actions initiating Terminate BP | Same BP triggered      | Covered |

**Requires separate gating**:

| Path                           | Risk                      | Mitigation                            |
| ------------------------------ | ------------------------- | ------------------------------------- |
| End Contingent Worker Contract | Different BP              | Add same permit validation to that BP |
| Rescind/Correct termination    | Reversal without new cert | Treat as separate high-risk action    |

**High-risk privileged channels**:

| Path                       | Risk                               | Mitigation                                         |
| -------------------------- | ---------------------------------- | -------------------------------------------------- |
| EIB "Automatic processing" | May bypass approvals/notifications | Restrict or prove permit validation still enforced |
| Direct DB access           | Produces orphan records            | Cannot mint certificates (architectural)           |

**Implementation note**: EIBs can run business processes with "automatic processing" that bypasses
approvals and notifications. Tenant demo must verify permit validation step is still enforced under
EIB, or this channel must be restricted for covered actions.

### 8.9 Enforcement Coverage Assertion

Each tenant deployment produces an **Enforcement Coverage Assertion** — a signed artifact that
enumerates which channels are provably gated:

```
Enforcement Coverage Assertion = {
    tenant_id: FK[Tenant],
    assertion_version: str,
    generated_at: Timestamp,

    covered_channels: [
        { channel: "Terminate Employee BP (UI)", enforcement: "PERMIT_REQUIRED" },
        { channel: "Terminate Employee BP (API)", enforcement: "PERMIT_REQUIRED" },
        { channel: "Mass Termination via BP", enforcement: "PERMIT_REQUIRED" }
    ],

    excluded_channels: [
        { channel: "EIB Automatic Processing", reason: "TENANT_REFUSED_RESTRICTION" }
    ],

    defensibility_impact: {
        actions_via_excluded_channels: "AUTO_DOWNGRADE",
        certificate_class_for_excluded: "UNCOVERED"
    },

    signed_by: "CanonSys",
    tenant_acknowledged: bool
}
```

**Auto-Downgrade Rule**: If a tenant refuses to restrict an ungated channel (e.g., EIB automatic
processing), all actions through that channel automatically receive `UNCOVERED` certificate class
with `DEGRADED` defensibility. The system does not pretend coverage exists where it does not.

This makes enforcement gaps **explicit and traceable** rather than silent.

### 8.10 Verification Checklist (Tenant Demo)

Before claiming enforcement in production:

1. **UI termination**: Cannot complete without valid Permit Token
2. **API termination**: Cannot complete without valid Permit Token
3. **Mass termination**: Cannot complete without valid Permit Token
4. **EIB automatic processing**: Verify permit validation enforced OR restrict channel
5. **Invalid token**: Returns DENY, BP cannot reach "Complete"
6. **Reused token**: Returns DENY("PERMIT_ALREADY_USED")
7. **Wrong subject**: Returns DENY (subject mismatch)
8. **JIT revocation**: Role removed after permit redemption (verify timing)

### 8.11 Reconciliation Engine (Shadow Auditor)

**The Problem**: Validation rules can be bypassed (during outages, by Super Admins, or via ungated
channels). CanonSys cannot count what it doesn't see.

**The Solution**: Periodic reconciliation against HRIS audit logs to detect orphan transactions.

**Mechanism**:

1. **Ingest**: Hourly cron job fetches `Hire` and `Terminate` events from Workday `Get_Audit_Logs`
   API
2. **Match**: Attempt to match each HRIS event to a CanonSys Permit using `worker_id` +
   `action_type`
3. **Alert**: Workday transaction without corresponding Permit → P0 "Compliance Breach" alert to GRC
   dashboard

**Definition**: An **Orphan Transaction** is an HRIS state change lacking a corresponding upstream
Decision in CanonSys.

```
Shadow Auditor Flow:
    Workday Audit Log (hourly) → Ingest → Match against Permit Ledger
                                            ↓
                                   [Match] → OK (certified)
                                   [No Match] → ORPHAN → Alert
```

**Result**: The Red State Dashboard shows mathematically real orphan counts, not guesses. "14% of
hires are UNCERTIFIED" is provable.

### 8.12 System Outage Protocol (Emergency Continuity)

**The Problem**: If CanonSys infrastructure is unavailable (503), the enterprise cannot lose the
ability to execute critical HR actions (e.g., terminate for cause).

**The Solution**: "Break-Glass" daily token for catastrophic outages.

**Mechanism**:

1. **Secret**: `EMERGENCY_BYPASS_TOKEN` generated daily, stored in a secure credential vault
   accessible only to VP HR/Legal
2. **Bypass**: During outage, Admin manually enters token into `CanonSys_Permit` field
3. **Workday Logic**: `IF (Permit_Valid) OR (Permit_Token == BYPASS_TOKEN) THEN Allow`
4. **Reconciliation**: Shadow Auditor flags all bypass transactions for retroactive review upon
   service restoration

```
Emergency Continuity Protocol:
    CanonSys Unavailable → Admin retrieves daily bypass token
                            ↓
                   Enter token in Workday permit field
                            ↓
                   Action proceeds (flagged as OUTAGE_BYPASS)
                            ↓
                   Service restored → Shadow Auditor detects gap
                            ↓
                   Mandatory retroactive certification
```

**Critical**: Bypass tokens rotate daily. Each use is flagged as `FORCE_MAJEURE_BYPASS` requiring
mandatory review. This is not a silent override—it's a loud, tracked, defensibility-degraded path.

---

## 9. Schema v1.0

### 9.1 Version Freeze

This document constitutes **Decision Certification Schema v1.0**.

The schema is frozen. Changes require:

1. `SCHEMA_VERSION` constant increment
2. Backwards-compatible migration path
3. Legal sign-off on modified requirements
4. Engineering validation of implementation

### 9.2 Breaking Changes

The following require major version increment (v2.0):

- Adding required evidence types
- Modifying gate semantics
- Changing certificate structure
- Altering hash computation

### 9.3 Non-Breaking Changes

The following are permitted within v1.x:

- Adding optional evidence types
- Adding new gate types (additive)
- Extending JSONB metadata fields
- New jurisdictional policy variants

### 9.4 Backwards Compatibility

All v1.x certificates must be:

- Verifiable against v1.0 schema
- Replayable with v1.0 Decision State
- Valid indefinitely (no expiration)

```python
SCHEMA_VERSION = "1.0"

def verify_certificate(cert: DecisionCertificate) -> bool:
    """Verify certificate against its schema version."""
    schema = load_schema(cert.schema_version)
    return schema.validate(cert) and verify_hash(cert)
```

### 9.5 High-Availability Timestamping (RFC 3161 Failover)

**Problem**: External TSAs (DigiCert, Sectigo) have downtime. Business operations cannot block
because a TSA is offline.

**Solution**: Optimistic Merkle Batching with multi-provider failover.

**Mechanism**:

| Phase       | Operation                                                         |
| ----------- | ----------------------------------------------------------------- |
| 1. Primary  | Attempt synchronous RFC 3161 timestamp to primary TSA             |
| 2. Failover | If primary unavailable, try secondary TSA                         |
| 3. Fallback | If all TSAs down, use internal monotonic clock + queue for anchor |
| 4. Batching | Pending timestamps aggregated into Merkle Tree (10-min intervals) |
| 5. Recovery | On TSA restoration, anchor Merkle Root to external TSA            |

**Evidence Structure**:

```
Timestamp Record = {
    decision_id: UUID,
    local_time: Timestamp,           // Internal monotonic
    tsa_time: Timestamp | null,      // RFC 3161 when available
    merkle_proof: MerkleProof | null, // For batch-anchored records
    anchor_status: "realtime" | "batch_pending" | "batch_anchored"
}

// Batch anchoring creates NEW evidence, never modifies existing records
TimestampAnchor = {
    anchor_id: UUID,
    anchor_type: "timestamp_anchor",
    merkle_root: SHA256,
    anchored_decision_ids: list[UUID],  // References to original records
    tsa_token: RFC3161Token,
    anchored_at: Timestamp
}
```

**Immutability Principle**: Batch anchoring never modifies original records. It creates a **new
immutable evidence entry** (`timestamp_anchor`) that references the original decision_ids and proves
their existence via Merkle proof + TSA token.

**Legal Defensibility**:

- Real-time RFC 3161: Strongest temporal proof (third-party attestation)
- Batch-anchored: Legally equivalent if chain proves existence post-event
- Pending: Internal ordering preserved; anchored within 24 hours

**Alert Thresholds**: Records pending >24 hours without anchor trigger compliance alert.

**Safe Phrasing**: "RFC 3161 timestamps enabled by default with multi-provider failover. Batch
anchoring preserves temporal proof when TSA unavailable."

---

## 10. System Guarantees

### 10.1 What CanonSys Guarantees

1. **Gate Enforcement**: Non-compliant actions have no execution path
2. **Evidence Integrity**: Certificates are content-addressed and tamper-evident
3. **Temporal Proof**: Timestamps prove existence at certification (RFC 3161 when enabled)
4. **Decision State Capture**: Complete computational context preserved
5. **Deterministic Replay**: Same inputs produce same certification

### 10.2 Boundaries

CanonSys certifies process, not intent. Humans verify decision quality, outcome correctness, legal
compliance, and AI fairness. Comparator analysis is advisory. Certification is engineering artifact,
not legal opinion.

### 10.3 Thesis

CanonSys claims the process is defensible. The law regulates decisions; we govern the decision
layer.

---

## Appendix A: Terminology

| Term                 | Definition                                      |
| -------------------- | ----------------------------------------------- |
| Evidence Atom        | Smallest unit of proof, content-addressed       |
| Evidence Packet      | Collection of atoms for a decision context      |
| Decision Certificate | Minted, immutable proof artifact                |
| Gate                 | Binary predicate, no override path              |
| Constitution         | Agreed rules for system behavior                |
| Execution Ledger     | Append-only record of system events             |
| Decision State       | Complete computational context at certification |
| Minting              | One-time certificate generation event           |
| Supersession         | New certificate referencing prior decision      |

## Appendix B: Evidence Types

| Type                    | Purpose                       | Schema                              |
| ----------------------- | ----------------------------- | ----------------------------------- |
| `consent_grant`         | Subject authorization         | scope, version, granted_at          |
| `policy_acknowledgment` | Actor policy acceptance       | policy_id, version, timestamp       |
| `gate_evaluation`       | Gate pass/block record        | gate_id, passed, context_hash       |
| `human_decision`        | Human judgment with rationale | actor, decision, rationale          |
| `model_output`          | AI-generated content          | model_hash, input_hash, output_hash |
| `comparator_analysis`   | Advisory peer comparison      | advisory_only: true                 |
| `certification_event`   | Certificate minting record    | certificate_hash, timestamp         |

## Appendix C: Gate Catalog

| Gate                 | Trigger              | Failure Behavior                |
| -------------------- | -------------------- | ------------------------------- |
| `consent_required`   | AI processing        | Block until consent granted     |
| `eligibility_check`  | PIP initiation       | Block until prerequisites met   |
| `waiting_period`     | Action timing        | Block until period elapsed      |
| `jurisdiction_check` | Cross-border actions | Block if jurisdiction disallows |
| `role_authorization` | Privileged actions   | Block if actor lacks permission |

## Appendix D: Operational Integrity

Hash chaining in a database is not, by itself, persuasive against "an admin could alter records."
This appendix defines the operational controls that protect ledger integrity.

### D.1 Certificate Signing Keys

```
Key Management = {
    storage: "AWS KMS / GCP Cloud HSM",
    key_type: "RSA-4096 or ECDSA P-256",
    rotation_policy: "Annual, or on personnel change",
    access_control: "IAM policy: sign-only, no export"
}
```

- Certificate hashes are signed with tenant-specific keys stored in KMS/HSM
- Signing keys cannot be exported; signing operations are audit-logged
- Key rotation creates new version; old signatures remain valid with version reference

### D.2 Database Access Control

```
Append-Only Role (ledger_writer):
    - INSERT: allowed
    - UPDATE: denied
    - DELETE: denied

Admin Role (ledger_admin):
    - Separate from ledger_writer
    - Change control required for any access
    - All queries logged to separate audit system
```

- Ledger tables have database-level triggers preventing UPDATE/DELETE
- Admin access requires approval ticket + time-limited credential
- All admin queries logged with query text and result hash

### D.3 Backup and Restoration Controls

- Backups are encrypted with separate KMS key
- Restoration requires dual-approval (Engineering + Security)
- Any restoration creates `LEDGER_RESTORATION_EVENT` in audit log
- Post-restoration integrity check compares hash chain to pre-backup state

### D.4 External Anchoring (Defense in Depth)

For high-risk customers, optional external anchoring:

| Mechanism         | Implementation                                  |
| ----------------- | ----------------------------------------------- |
| TSA Anchoring     | RFC 3161 tokens for certificate hashes          |
| WORM Storage      | S3 Object Lock for exported certificate bundles |
| Blockchain Anchor | Periodic Merkle root to public chain (optional) |

External anchoring is additive—it does not replace internal integrity controls.

### D.5 Opposing Counsel Attack Map

| Attack                 | Defense                                          |
| ---------------------- | ------------------------------------------------ |
| "Post-hoc fabrication" | Temporal cliff + hash chain + TSA anchoring      |
| "Admin tampering"      | KMS keys + IAM + audit logging + WORM option     |
| "Backup replay"        | Restoration audit trail + dual approval          |
| "Policy accuracy"      | Vendor library + customer activation + warranty  |
| "Automated decision"   | Comparator non-authorizing + required human gate |

---

**Document Version**: 1.0 **Schema Version**: 1.0 **Last Updated**: 2026-01-11 **Classification**:
Technical Architecture
