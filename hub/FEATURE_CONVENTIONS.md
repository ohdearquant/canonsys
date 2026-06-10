# Feature Vocabulary Conventions

**Version**: 2.0 | **Status**: Canonical | **Last Updated**: 2026-01-20

Reference documentation for canon-core vocabulary features. This document defines the **complete and
exhaustive** list of allowed function prefixes. Any prefix not listed here is non-standard and must
be refactored.

---

## The Core Principle: Code as Regulation

CanonSys vocabulary follows a simple rule: **the function name IS the regulation**.

```python
# FCRA § 1681b(b)(3): "obtain consent before procuring consumer report"
await require_consent_for_scope(subject_id, ConsentScope.BACKGROUND_CHECK, ctx)

# FCRA § 1681m: "provide pre-adverse action notice"
await certify_fcra_notice(subject_id, notice_sent_at, dispute_window_end, cep_ids, ctx)
```

A compliance officer reading the code should see the regulation, not implementation details. An
auditor reviewing the vocabulary should understand what controls exist without reading function
bodies.

---

## Vocabulary Taxonomy

Functions are organized into **semantic layers** based on their behavior:

| Layer             | Purpose                             | Raises?   | Mutates? |
| ----------------- | ----------------------------------- | --------- | -------- |
| **Query**         | Observe state, return results       | Never     | Never    |
| **Gate**          | Assert preconditions, enforce rules | Yes       | Never    |
| **Action**        | Mutate state, create entities       | Sometimes | Yes      |
| **Certification** | Create immutable proof artifacts    | Sometimes | Yes      |
| **Lifecycle**     | Manage temporal state transitions   | Sometimes | Yes      |
| **Evidence**      | Chain and supersede audit trails    | Sometimes | Yes      |

---

## Layer 1: Query Patterns

**Behavior**: Read-only observation. Returns structured results. Never raises for expected outcomes.
Never mutates state.

**Use when**: You need to ask a question about state without changing it or enforcing rules.

### `verify_*` — Binary Validity Check

**Semantics**: Query for existence or validity. Returns boolean outcome in result.

```python
async def verify_consent_for_scope(
    subject_id: UUID,
    scope: ConsentScope,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> ConsentVerificationResult:
    """Verify consent exists for subject and scope.

    Returns:
        ConsentVerificationResult with has_consent=True/False
    """
```

**Result pattern**:

```python
@dataclass(frozen=True, slots=True)
class ConsentVerificationResult:
    has_consent: bool          # Binary outcome
    subject_id: UUID
    scope: ConsentScope
    reason: str | None = None  # Why false (if applicable)
```

**Regulatory mapping**: "Verify that X exists" → `verify_*`

---

### `check_*` — Status/Metric Evaluation

**Semantics**: Evaluate external state or conditions. Returns status enum or metrics.

```python
async def check_waiting_period_elapsed(
    notice_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> WaitingPeriodResult:
    """Check if FCRA 5-day waiting period has elapsed.

    Per FCRA 15 U.S.C. § 1681b(b)(3), employer must wait
    a reasonable time (typically 5 business days) for dispute.

    Returns:
        WaitingPeriodResult with elapsed=True/False, remaining_hours
    """
```

**Use for**: Timing checks, threshold evaluations, external API status queries.

---

### `derive_*` — Compute from Inputs

**Semantics**: Calculate derived value from inputs. Pure computation, no state queries.

```python
async def derive_risk_score(
    factors: list[RiskFactor],
    ctx: RequestContext,
) -> RiskScoreResult:
    """Derive composite risk score from input factors.

    Returns:
        RiskScoreResult with score (0.0-1.0), contributing_factors
    """
```

**Key distinction**: `check_*` queries external state; `derive_*` computes from provided inputs.

**Use for**: Score calculations, metric derivations, equivalence assessments.

---

### `get_*` — Retrieve Single Entity

**Semantics**: Fetch a single entity by identifier.

```python
async def get_consent_token(
    token_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> ConsentToken | None:
    """Retrieve consent token by ID.

    Returns:
        ConsentToken if found, None otherwise
    """
```

---

### `list_*` — Retrieve Collection

**Semantics**: Fetch multiple entities, optionally filtered.

```python
async def list_consent_tokens(
    subject_id: UUID,
    ctx: RequestContext,
    *,
    scope: ConsentScope | None = None,
    conn: Any | None = None,
) -> list[ConsentToken]:
    """List consent tokens for subject.

    Returns:
        List of ConsentToken (may be empty)
    """
```

---

### `find_*` — Search with Criteria

**Semantics**: Search for entities matching criteria.

```python
async def find_consent_token(
    subject_id: UUID,
    scope: ConsentScope,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> ConsentToken | None:
    """Find active consent token matching criteria.

    Returns:
        ConsentToken if found, None otherwise
    """
```

**Distinction from `get_*`**: `get_*` uses primary key; `find_*` uses search criteria.

---

### `assess_*` — Qualitative Evaluation

**Semantics**: Evaluate and score qualitatively.

```python
async def assess_bias_risk(
    model_id: UUID,
    ctx: RequestContext,
) -> BiasAssessmentResult:
    """Assess algorithmic bias risk for model.

    Returns:
        BiasAssessmentResult with risk_level enum, findings
    """
```

---

### `classify_*` — Categorization

**Semantics**: Assign category or classification.

```python
async def classify_data_sensitivity(
    data_type: str,
    ctx: RequestContext,
) -> DataClassificationResult:
    """Classify data sensitivity level.

    Returns:
        DataClassificationResult with classification enum
    """
```

---

## Layer 2: Gate Patterns

**Behavior**: Assert preconditions. Raises exception on failure. Returns confirmation on success.
Never mutates state.

**Use when**: You need to enforce a rule that MUST pass before proceeding.

### `require_*` — Assert Precondition

**Semantics**: Assert a condition is met. Raises if not satisfied.

```python
async def require_consent_for_scope(
    subject_id: UUID,
    scope: ConsentScope,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> RequireConsentResult:
    """Require valid consent exists for scope.

    FCRA § 1681b(b)(2): Consent required before procuring consumer report.

    Returns:
        RequireConsentResult with satisfied=True (only on success)

    Raises:
        ConsentRequiredError: If no valid consent exists
    """
```

**Result pattern**: Always returns `satisfied=True` — the result confirms the gate passed.

**Regulatory mapping**:

- "Must obtain consent" → `require_consent_*`
- "Must not disclose without authorization" → `require_authorization_*`
- "Must wait 5 days" → `require_waiting_period_elapsed`

**Why not `deny_*`?**: The `deny_*` pattern was removed because:

1. It overlaps semantically with query patterns (`verify_*`, `check_*`)
2. Double-negatives are confusing (`deny_expired` returning `denied=False`)
3. Regulatory language uses positive framing ("require consent") not negative ("deny without
   consent")
4. Gates should raise, not return booleans — that's what `require_*` does

---

### `validate_*` — Assert Structure/Format

**Semantics**: Assert input conforms to schema or format. Raises if invalid.

```python
async def validate_cep_structure(
    cep: CertifiedEvidencePacket,
    ctx: RequestContext,
) -> ValidateCEPResult:
    """Validate CEP has required structure.

    Returns:
        ValidateCEPResult with valid=True

    Raises:
        CEPValidationError: If structure invalid
    """
```

**Use for**: Input validation, schema conformance, format checks.

---

### `enforce_*` — Apply Rule Strictly

**Semantics**: Enforce a policy rule. Raises if rule cannot be applied.

```python
async def enforce_retention_policy(
    entity_id: UUID,
    policy: RetentionPolicy,
    ctx: RequestContext,
) -> EnforceRetentionResult:
    """Enforce retention policy on entity.

    Returns:
        EnforceRetentionResult with enforced=True

    Raises:
        RetentionPolicyViolation: If entity violates policy
    """
```

---

### `*_must_be_*` / `*_must_not_be_*` — Truth Machine Phrases

**Semantics**: Assert invariant. Raises domain exception on violation. These are the "truth machine"
— if the function returns, the invariant is proven true.

```python
def consent_must_be_valid(token: ConsentToken) -> None:
    """Assert consent token is in ACTIVE status.

    Truth Machine Semantics:
        If this function returns, the invariant holds.
        No further checking needed by caller.

    Raises:
        ConsentNotValidError: If token status is not ACTIVE
    """
    if token.status != ConsentStatus.ACTIVE:
        raise ConsentNotValidError(token.subject_id, token.scope)
```

**Naming pattern**: `{noun}_must_be_{adjective}` or `{noun}_must_not_be_{adjective}`

**Examples**:

- `consent_must_be_valid`
- `consent_must_not_be_expired`
- `subject_must_be_adult`
- `data_must_not_be_pii`

---

## Layer 3: Action Patterns

**Behavior**: Mutate state. Create, modify, or delete entities.

### `create_*` — Create New Entity

```python
async def create_consent_token(
    subject_id: UUID,
    scope: ConsentScope,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> ConsentToken:
    """Create new consent token.

    Returns:
        Created ConsentToken
    """
```

---

### `save_*` — Persist Entity

```python
async def save_evidence(
    evidence: Evidence,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> Evidence:
    """Persist evidence with content hash.

    Returns:
        Saved Evidence with id and hash
    """
```

---

### `grant_*` — Create Permission

```python
async def grant_consent(
    subject_id: UUID,
    scope: ConsentScope,
    ctx: RequestContext,
    *,
    expires_at: datetime | None = None,
    conn: Any | None = None,
) -> ConsentToken:
    """Grant consent for processing scope.

    Returns:
        Created ConsentToken in ACTIVE status
    """
```

---

### `revoke_*` — Remove Permission

```python
async def revoke_consent(
    token_id: UUID,
    ctx: RequestContext,
    *,
    reason: str | None = None,
    conn: Any | None = None,
) -> RevokedConsentToken:
    """Revoke consent token.

    Returns:
        Token with status=REVOKED
    """
```

---

### `record_*` — Log Action/Event

**Semantics**: Create audit record. Never fails (fire-and-forget evidence).

```python
async def record_workflow_step(
    workflow_run_id: UUID,
    step_name: str,
    ctx: RequestContext,
    *,
    input_hash: str | None = None,
    output_hash: str | None = None,
    conn: Any | None = None,
) -> WorkflowStepRecord:
    """Record workflow step execution for audit trail.

    Returns:
        WorkflowStepRecord with timestamp and hashes
    """
```

---

### `trigger_*` — Initiate Process

```python
async def trigger_break_glass_override(
    resource_id: UUID,
    justification: str,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> BreakGlassOverride:
    """Trigger emergency break-glass override.

    Creates audit trail and temporary elevated access.

    Returns:
        BreakGlassOverride with expiration
    """
```

---

## Layer 4: Certification Patterns

**Behavior**: Create immutable, signed proof artifacts. Audit-grade evidence.

### `certify_*` — Create Signed Certificate

```python
async def certify_fcra_notice(
    subject_id: UUID,
    notice_sent_at: datetime,
    dispute_window_end: datetime,
    cep_ids: list[UUID],
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> FCRANoticeCertificate:
    """Certify FCRA pre-adverse action compliance.

    Creates immutable certificate proving notice was sent
    and dispute window observed per FCRA § 1681m.

    Returns:
        FCRANoticeCertificate (signed, hashed, immutable)
    """
```

**Certificate requirements**:

- Unique ID (uuid4)
- Content hash (`compute_hash(hash_data)`)
- Timestamp (`certified_at`)
- Actor (`certified_by`)
- Supporting evidence references (`cep_ids`)

---

### `emit_*` — Produce Document

```python
async def emit_certificate(
    certificate_type: CertificateType,
    data: CertificateData,
    ctx: RequestContext,
) -> Certificate:
    """Emit compliance certificate document.

    Returns:
        Certificate ready for signing
    """
```

---

### `seal_*` — Finalize and Lock

```python
async def seal_cep(
    cep_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> SealedCEP:
    """Seal Certified Evidence Packet.

    Once sealed, CEP cannot be modified. Creates
    cryptographic commitment.

    Returns:
        SealedCEP with seal_hash
    """
```

---

### `sign_*` — Cryptographic Signature

```python
async def sign_certificate(
    certificate_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> SignedCertificate:
    """Sign certificate with RSA-4096.

    Returns:
        SignedCertificate with signature bytes
    """
```

---

## Layer 5: Lifecycle Patterns

**Behavior**: Manage temporal state transitions.

### `pause_*` / `resume_*` — Temporal Suspension

```python
async def pause_waiting_period(
    notice_id: UUID,
    reason: str,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> PausedWaitingPeriod:
    """Pause waiting period (e.g., for dispute).

    Returns:
        PausedWaitingPeriod with paused_at
    """

async def resume_waiting_period(
    notice_id: UUID,
    ctx: RequestContext,
    *,
    extension_hours: int = 0,
    conn: Any | None = None,
) -> ResumedWaitingPeriod:
    """Resume paused waiting period.

    Returns:
        ResumedWaitingPeriod with resumed_at, new_end
    """
```

---

### `schedule_*` — Future Execution

```python
async def schedule_retention_review(
    entity_id: UUID,
    review_date: datetime,
    ctx: RequestContext,
) -> ScheduledReview:
    """Schedule future retention review.

    Returns:
        ScheduledReview with scheduled_for
    """
```

---

## Layer 6: Evidence Patterns

**Behavior**: Link and manage immutable evidence chains.

### `chain_*` — Link Evidence

```python
async def chain_evidence(
    parent_id: UUID,
    child_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> EvidenceChain:
    """Chain evidence to parent.

    Creates cryptographic link in evidence chain.

    Returns:
        EvidenceChain with parent_hash, child_hash
    """
```

---

### `supersede_*` — Immutable Replacement

```python
async def supersede_evidence(
    old_id: UUID,
    new_content: EvidenceContent,
    reason: str,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> SupersededEvidence:
    """Supersede evidence with correction.

    Old evidence is marked superseded (not deleted).
    New evidence links to old.

    Returns:
        SupersededEvidence with old_id, new_id, reason
    """
```

---

## Function Signature Standard

### Template

```python
async def {prefix}_{noun}(
    # Required positional parameters (most specific to least)
    primary_id: UUID,
    secondary_param: SomeType,
    ctx: RequestContext,
    *,
    # Optional keyword-only parameters
    optional_param: OtherType | None = None,
    conn: Any | None = None,
) -> ResultType:
    """One-line summary.

    Detailed description with regulatory context.

    Args:
        primary_id: Description
        secondary_param: Description
        ctx: Request context (tenant, actor)
        optional_param: Description (default: None)
        conn: Optional existing connection

    Returns:
        ResultType description

    Raises:
        ExceptionType: When this happens

    Regulatory:
        - FCRA § X: Requirement description
        - GDPR Art. Y: Requirement description
    """
```

### Parameter Order

1. **Primary resource ID** — The main entity being operated on
2. **Secondary parameters** — Additional required inputs
3. **`ctx: RequestContext`** — Always required, always last positional
4. **`*`** — Keyword-only marker
5. **Optional parameters** — With defaults, alphabetical
6. **`conn: Any | None = None`** — Always last (connection passthrough)

### Return Type Requirements

All features return **frozen dataclasses** (or entity types):

```python
@dataclass(frozen=True, slots=True)
class FeatureResult:
    """Result of feature operation."""

    # Boolean outcome (for gates/queries)
    satisfied: bool  # or has_*, is_*, valid

    # Echo back key inputs (for correlation)
    subject_id: UUID
    scope: SomeScope

    # Output data
    result_field: SomeType

    # Optional metadata
    reason: str | None = None
    timestamp: datetime | None = None
```

**Why frozen dataclasses**:

- Immutable (safe for caching, logging)
- `slots=True` for memory efficiency
- Type-safe (no dict access errors)
- Self-documenting structure

---

## Quick Reference

### Complete Prefix List

| Prefix        | Layer     | Returns                  | Raises                   | Use When                 |
| ------------- | --------- | ------------------------ | ------------------------ | ------------------------ |
| `verify_*`    | Query     | `Result(has_*=bool)`     | Never                    | Binary validity check    |
| `check_*`     | Query     | `Result(status=enum)`    | Never                    | Status/metric evaluation |
| `derive_*`    | Query     | `Result(value=T)`        | Never                    | Compute from inputs      |
| `get_*`       | Query     | `Entity \| None`         | Never                    | Retrieve by ID           |
| `list_*`      | Query     | `list[Entity]`           | Never                    | Retrieve collection      |
| `find_*`      | Query     | `Entity \| None`         | Never                    | Search by criteria       |
| `assess_*`    | Query     | `Result(score=float)`    | Never                    | Qualitative evaluation   |
| `classify_*`  | Query     | `Result(category=enum)`  | Never                    | Categorization           |
| `require_*`   | Gate      | `Result(satisfied=True)` | `RequirementNotMetError` | Assert precondition      |
| `validate_*`  | Gate      | `Result(valid=True)`     | `ValidationError`        | Assert structure/format  |
| `enforce_*`   | Gate      | `Result(enforced=True)`  | `EnforcementError`       | Apply rule strictly      |
| `*_must_*`    | Gate      | `None`                   | Domain exception         | Truth machine invariant  |
| `create_*`    | Action    | `Entity`                 | `CreateError`            | New entity               |
| `save_*`      | Action    | `Entity`                 | `PersistError`           | Persist entity           |
| `grant_*`     | Action    | `Grant`                  | `GrantError`             | Create permission        |
| `revoke_*`    | Action    | `Revocation`             | `RevokeError`            | Remove permission        |
| `record_*`    | Action    | `Record`                 | Never                    | Audit trail              |
| `trigger_*`   | Action    | `Trigger`                | `TriggerError`           | Initiate process         |
| `certify_*`   | Cert      | `Certificate`            | `CertifyError`           | Create certificate       |
| `emit_*`      | Cert      | `Document`               | `EmitError`              | Produce document         |
| `seal_*`      | Cert      | `SealedEntity`           | `SealError`              | Finalize/lock            |
| `sign_*`      | Cert      | `Signature`              | `SignError`              | Cryptographic signature  |
| `pause_*`     | Lifecycle | `PausedEntity`           | `LifecycleError`         | Suspend                  |
| `resume_*`    | Lifecycle | `ActiveEntity`           | `LifecycleError`         | Resume                   |
| `schedule_*`  | Lifecycle | `ScheduledAction`        | `ScheduleError`          | Plan future              |
| `chain_*`     | Evidence  | `ChainedEvidence`        | `ChainError`             | Link evidence            |
| `supersede_*` | Evidence  | `SupersededEntity`       | `SupersedeError`         | Replace immutably        |

### Deprecated/Removed Prefixes

| Old Prefix   | Replacement | Reason                                         |
| ------------ | ----------- | ---------------------------------------------- |
| `deny_*`     | `require_*` | Double-negative confusion; gates should raise  |
| `count_*`    | `derive_*`  | Counting is derivation from inputs             |
| `log_*`      | `record_*`  | Consistent with evidence vocabulary            |
| `invoke_*`   | `trigger_*` | Consistent with control flow vocabulary        |
| `activate_*` | `certify_*` | Activation is certification of lifecycle state |
| `mint_*`     | `emit_*`    | Consistent with certification vocabulary       |
| `map_*`      | `derive_*`  | Mapping is derivation                          |
| `ratify_*`   | `certify_*` | Ratification is certification                  |

---

## Anti-Patterns

### 1. Returning dicts instead of dataclasses

```python
# BAD
async def verify_consent(...) -> dict:
    return {"has_consent": True, "token_id": str(token_id)}

# GOOD
async def verify_consent(...) -> ConsentVerificationResult:
    return ConsentVerificationResult(has_consent=True, token_id=token_id)
```

### 2. Raising exceptions for expected query outcomes

```python
# BAD - verify_* should not raise for "no consent"
async def verify_consent(...):
    if not row:
        raise NoConsentError()  # Wrong! Caller has to catch

# GOOD - return result with boolean
async def verify_consent(...) -> ConsentVerificationResult:
    if not row:
        return ConsentVerificationResult(has_consent=False, reason="...")
```

### 3. Mixing query and gate semantics

```python
# BAD - unclear what it does
async def check_and_require_consent(...):
    ...

# GOOD - separate concerns
async def verify_consent(...) -> VerifyResult: ...
async def require_consent(...) -> RequireResult: ...
```

### 4. Using wrong prefix for behavior

```python
# BAD - check implies query, but this raises
async def check_access_allowed(...):
    if not allowed:
        raise AccessDenied()

# GOOD - require implies gate
async def require_access_allowed(...):
    if not allowed:
        raise AccessDenied()
    return RequireResult(satisfied=True)
```

### 5. Not documenting regulatory basis

```python
# BAD - why does this exist?
async def check_waiting_period(...): ...

# GOOD - regulatory context is clear
async def check_waiting_period(...):
    """Check FCRA 5-day waiting period has elapsed.

    Regulatory:
        FCRA 15 U.S.C. § 1681b(b)(3): Employer must wait
        reasonable time (typically 5 business days) for dispute.
    """
```

---

## Deontic Mapping

Legal requirements use modal verbs. Map them to prefixes:

| Legal Language                   | Prefix      | Example                            |
| -------------------------------- | ----------- | ---------------------------------- |
| "**Must** obtain consent"        | `require_*` | `require_consent_for_scope`        |
| "**Shall** provide notice"       | `certify_*` | `certify_notice_sent`              |
| "**May** process if consented"   | `verify_*`  | `verify_consent_for_scope`         |
| "**Shall not** disclose without" | `require_*` | `require_disclosure_authorization` |
| "**Must** wait 5 days"           | `require_*` | `require_waiting_period_elapsed`   |
| "**Shall** maintain records"     | `record_*`  | `record_processing_activity`       |

---

## Compliance with This Convention

**100% compliance required.** Every function in `features/` must use a prefix from the Complete
Prefix List above.

To check compliance:

```bash
# Find non-standard prefixes
grep -r "^async def " features/ | grep -v -E "(verify_|check_|derive_|get_|list_|find_|assess_|classify_|require_|validate_|enforce_|_must_|create_|save_|grant_|revoke_|record_|trigger_|certify_|emit_|seal_|sign_|pause_|resume_|schedule_|chain_|supersede_)"
```

Non-compliant functions should be renamed in the next refactoring cycle.
