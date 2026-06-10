---
doc_type: mapping
title: "ADR-022 Consent - Code Mapping"
version: "2.0.0"
updated: "2026-01-29"
adr: ADR-022-consent
tds: TDS-022-consent
---

# 022-consent - Code Mapping

## Vocabulary Package Reference

**Primary Package**: `hub/foundation/packages/consent/`

### Vocabulary Phrases

| Phrase                   | Pattern | Location           | Regulatory Basis            |
| ------------------------ | ------- | ------------------ | --------------------------- |
| `verify_token`           | verify  | `consent/actions/` | GDPR Art. 7(1), FCRA 604(b) |
| `grant_token`            | action  | `consent/actions/` | GDPR Art. 7(1)              |
| `revoke_token`           | action  | `consent/actions/` | GDPR Art. 7(3)              |
| `require_active_consent` | require | `consent/actions/` | GDPR Art. 6                 |
| `require_valid_consent`  | require | `consent/actions/` | FCRA 604(b)(2)(A)           |
| `cascade_revoke_token`   | action  | `consent/actions/` | GDPR Art. 7(3)              |
| `verify_scope_covers`    | verify  | `consent/actions/` | GDPR Art. 5(1)(b)           |

### Control Surface Bindings

| Surface                  | Phrase Integration                              |
| ------------------------ | ----------------------------------------------- |
| PII Export Authorization | `consent_status` fact derived from ConsentToken |
| Cross-Border Transfer    | ConsentGate verifies data_sharing consent       |
| Training Data Inclusion  | ConsentScope.AI_SCORING validates AI training   |

---

## Primary Code Paths

- `hub/foundation/packages/consent/` - Complete consent feature vertical slice
- `hub/foundation/packages/consent/types/token.py` - ConsentToken entity
- `hub/foundation/packages/consent/types/scope.py` - ConsentScope enum with primary/dependency model
- `hub/foundation/packages/consent/types/status.py` - ConsentStatus enum
- `hub/foundation/packages/consent/service.py` - ConsentService and ConsentGate
- `hub/foundation/packages/consent/actions/` - All consent actions

## Key Classes/Functions

### Token Entity (features/consent/types/token.py)

- **ConsentTokenContent** - Content model with `tenant_id` and `subject_id` fields (consent vocabulary):
  - `scope: ConsentScope` - What this permits (BACKGROUND_CHECK, AI_SCORING, etc.)
  - `version: str | None` - Consent form/policy version
  - `granted_at: datetime` - When consent was granted (defaults to now)
  - `granted_by_id: FK[User] | None` - Who recorded consent
  - `status: ConsentStatus` - Current state (ACTIVE, REVOKED, EXPIRED, SUPERSEDED)
  - `expires_at: datetime | None` - When consent expires
  - `revoked_at: datetime | None` - When consent was revoked
  - `revoked_by_id: FK[User] | None` - Who revoked consent
  - `revocation_reason: str | None` - Why consent was revoked

- **ConsentToken** - Entity registered to `consent_tokens` table

### Scope Model (features/consent/types/scope.py)

- **ConsentScope** - Enum with primary/dependency model:
  - `CONSIDERATION_AUTHORIZATION` - Primary consent (gates all others)
  - `AI_SCORING`, `INTERVIEW_RECORDING`, `BACKGROUND_CHECK`, `DATA_PROCESSING`, `COMMUNICATIONS`,
    `THIRD_PARTY_SHARING` - Dependent scopes
  - `primary()` classmethod - Returns primary scope(s)
  - `dependencies()` classmethod - Returns dependency map

### Status Model (features/consent/types/status.py)

- **ConsentStatus** - Enum with states:
  - `ACTIVE` - Consent is valid
  - `REVOKED` - Consent was withdrawn
  - `EXPIRED` - Consent has expired (checked at query time)
  - `SUPERSEDED` - Consent was replaced by new version

### Service (features/consent/service.py)

- **ConsentService** - CanonService with gate-protected actions:
  - `grant(payload, ctx)` - Grant consent for a scope
  - `verify(payload, ctx)` - Verify consent exists (hot path, skip_evidence=True)
  - `revoke(payload, ctx)` - Revoke consent, cascades if primary scope
  - `list(payload, ctx)` - List consent tokens for subject

- **ConsentGate** - Parameterized gate with dynamic `gate_id`:
  - Constructor: `ConsentGate(scope: str)`
  - gate_id: `f"consent.{scope}"`
  - Uses `verify_consent_token` action internally
  - Returns evidence_refs when consent is found

### Actions (features/consent/actions/)

- **grant_consent_token** - Create new consent token
- **verify_consent_token** - Check consent exists and is valid (hot path)
- **revoke_consent_token** - Revoke consent with reason
- **cascade_revoke_consent_token** - Cascade revoke to dependent scopes
- **find_consent_token** - Find specific consent token
- **list_consent_tokens** - List tokens for subject with filtering
- **require_valid_consent** - Requirement action for valid consent
- **require_active_consent** - Requirement action for active consent

### Truth Machine Phrases (features/consent/actions/constraints.py)

- `consent_must_be_valid` - Assert consent is valid
- `consent_must_not_be_expired` - Assert consent is not expired
- `consent_must_not_be_withdrawn` - Assert consent is not revoked
- `consent_scope_must_cover` - Assert scope covers required permission

## Architectural Patterns

- **Vertical Slice**: Complete consent domain in `features/consent/` with types, actions, service,
  exceptions, and API.

- **Token as Capability**: ConsentToken IS the permission, not just evidence of permission. Gates
  query tokens directly.

- **Separate from Evidence**: ConsentToken is queryable state. Evidence records the audit trail.
  Token is current state; Evidence is historical record.

- **Primary/Dependency Model**: `CONSIDERATION_AUTHORIZATION` is primary consent that gates all
  others. Revoking primary cascades to all dependent scopes.

- **Parameterized Gate**: ConsentGate instantiated with scope, generating dynamic gate_id. Single
  implementation, multiple scopes.

- **Expiration at Query Time**: `is_valid()` checks both status AND expires_at. Tokens can
  time-expire without explicit revocation. No background jobs needed.

- **CanonService Integration**: ConsentService uses `@gates` and `@action` decorators for automatic
  gate evaluation and evidence emission.

## Dependencies

- **Depends on**:
  - `canon.entities.entity.Entity` - Base entity
  - Consent vocabulary (`hub/foundation/packages/consent/`) - Content with tenant/subject
  - `kron.types.db_types.FK` - Type-safe foreign keys
  - `canon.enforcement.vocabulary` - Vocabulary-based enforcement (verify_*/require_* phrases)
  - `canon.enforcement.service.CanonService` - Service base
  - `kron` - Framework primitives

- **Depended by**:
  - Background check workflows - Require BACKGROUND_CHECK consent
  - AI scoring operations - Require AI_SCORING consent
  - Interview recording - Require INTERVIEW_RECORDING consent
  - GDPR compliance - Requires valid consent tokens

## Key Decisions

1. **Vertical slice architecture**: Complete domain in one feature folder, not scattered across
   types/enforcement/services.

2. **ConsentScope as enum**: Strongly typed scopes with primary/dependency relationships defined in
   code.

3. **Cascade revocation**: Revoking primary consent automatically revokes all dependent scopes via
   `cascade_revoke_consent_token`.

4. **SUPERSEDED status**: Added for consent version upgrades when terms change and require
   re-consent.

5. **Hot path optimization**: `verify` action has `skip_evidence=True` for performance on critical
   paths.

6. **Truth machine phrases**: Constraint functions for invariant assertions in workflows.
