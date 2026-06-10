# Writing Vocabulary Phrases

This guide explains how to create vocabulary phrases - the atomic operations that power charters.

## What is a Phrase?

A phrase is a **declarative compliance operation** that:

- Has typed inputs and outputs
- Maps to a regulatory requirement
- Executes database queries or business logic
- Returns structured results

Phrases are the vocabulary that charters compose into workflows.

## Phrase Anatomy

```python
from canon.enforcement.executor import canon_phrase
from canon.enforcement.errors import RequirementNotMetError
from kron.specs import Operable
from pydantic import BaseModel

class RequireSeparationOfDutiesSpecs(BaseModel):
    """Specs for require separation of duties phrase."""

    # inputs
    workflow_id: UUID
    conflicting_steps: tuple[str, ...] | list[str]

    # outputs (with defaults for instantiation)
    satisfied: bool = False
    step_actors: dict[str, UUID] | None = None
    conflicts_found: tuple[tuple[str, str, UUID], ...] | None = None
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireSeparationOfDutiesSpecs),
    inputs={"workflow_id", "conflicting_steps"},
    outputs={"satisfied", "workflow_id", "step_actors", "conflicts_found", "checked_at", "reason"},
)
async def require_separation_of_duties(
    options: RequireSeparationOfDutiesSpecs,
    ctx: RequestContext,
) -> dict:
    """Require separation of duties for workflow steps.

    Regulatory basis: SOX Section 404, SOC 2 CC5.1
    """
    # Implementation...
    return {
        "satisfied": True,
        "workflow_id": workflow_id,
        "step_actors": step_actors,
        "conflicts_found": (),
        "checked_at": now,
        "reason": "SoD verified",
    }
```

## Phrase Patterns

### 1. Require Pattern (Vocabulary Phrase)

**Purpose**: Block progression if condition not met.

**Convention**: Name starts with `require_`, raises `RequirementNotMetError` on failure.

```python
@canon_phrase(
    Operable.from_structure(RequireManagerApprovedSpecs),
    inputs={"request_id"},
    outputs={"satisfied", "approval_id", "approved_at", "reason"},
)
async def require_manager_approved(
    options: RequireManagerApprovedSpecs,
    ctx: RequestContext,
) -> dict:
    """Gate on manager approval.

    Regulatory basis: SOC 2 CC6.1
    """
    row = await select_one(
        "approvals",
        where={"request_id": options.request_id, "status": "approved"},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="manager_approval",
            reason="Manager approval not found",
        )

    return {
        "satisfied": True,
        "approval_id": row["id"],
        "approved_at": row["approved_at"],
        "reason": None,
    }
```

### 2. Verify Pattern (Check)

**Purpose**: Check a condition, return result without raising.

**Convention**: Name starts with `verify_`, returns `verified: bool`.

```python
@canon_phrase(
    Operable.from_structure(VerifyConsentTokenSpecs),
    inputs={"subject_id", "scope"},
    outputs={"verified", "token_id", "granted_at", "expires_at", "reason"},
)
async def verify_consent_token(
    options: VerifyConsentTokenSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify active consent exists.

    Regulatory basis: FCRA Section 1681b(b)(3), GDPR Art 6-7
    """
    row = await select_one(
        "consent_tokens",
        where={
            "subject_id": options.subject_id,
            "scope": options.scope.value,
            "status": "active",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "token_id": None,
            "granted_at": None,
            "expires_at": None,
            "reason": f"No active consent for scope '{options.scope.value}'",
        }

    # Check expiration
    if row.get("expires_at") and row["expires_at"] < now_utc():
        return {
            "verified": False,
            "token_id": row["id"],
            "granted_at": row.get("granted_at"),
            "expires_at": row["expires_at"],
            "reason": "Consent token has expired",
        }

    return {
        "verified": True,
        "token_id": row["id"],
        "granted_at": row.get("granted_at"),
        "expires_at": row.get("expires_at"),
        "reason": None,
    }
```

### 3. Derive Pattern (Compute)

**Purpose**: Calculate a value from data.

**Convention**: Name starts with `derive_`, returns computed value.

```python
@canon_phrase(
    Operable.from_structure(DeriveRiskTierSpecs),
    inputs={"factors"},
    outputs={"risk_tier", "score", "factors_evaluated", "computed_at"},
)
async def derive_risk_tier(
    options: DeriveRiskTierSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive risk tier from factors.

    Regulatory basis: SOX 404, COSO Framework
    """
    score = compute_risk_score(options.factors)

    if score >= 0.8:
        tier = "CRITICAL"
    elif score >= 0.6:
        tier = "HIGH"
    elif score >= 0.4:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return {
        "risk_tier": tier,
        "score": score,
        "factors_evaluated": len(options.factors),
        "computed_at": now_utc(),
    }
```

### 4. Action Pattern (Record/Execute)

**Purpose**: Perform an operation, record evidence.

**Convention**: Action verbs - `save_`, `record_`, `emit_`, `schedule_`.

```python
@canon_phrase(
    Operable.from_structure(EmitCertificateSpecs),
    inputs={"decision_id", "certificate_type"},
    outputs={"certificate_id", "emitted_at", "content_hash"},
)
async def emit_certificate(
    options: EmitCertificateSpecs,
    ctx: RequestContext,
) -> dict:
    """Emit immutable decision certificate.

    Regulatory basis: FRE 901, ISO 27037
    """
    certificate = await create_certificate(
        decision_id=options.decision_id,
        certificate_type=options.certificate_type,
        ctx=ctx,
    )

    return {
        "certificate_id": certificate.id,
        "emitted_at": certificate.created_at,
        "content_hash": certificate.content_hash,
    }
```

## Adding Phrases to a Package

### 1. Create the Phrase File

```
packages/
└── authorization/
    └── phrases/
        └── require_separation_of_duties.py   # New phrase
```

### 2. Export from `__init__.py`

```python
# packages/authorization/phrases/__init__.py
from .require_separation_of_duties import (
    RequireSeparationOfDutiesSpecs,
    require_separation_of_duties,
)

__all__ = [
    "RequireSeparationOfDutiesSpecs",
    "require_separation_of_duties",
    # ... other phrases
]
```

### 3. Register in Package Definition

```python
# packages/authorization/package.py
from canon.hub.package import VocabularyPackage

AUTHORIZATION_PACKAGE = VocabularyPackage(
    name="authorization",
    domain_module="canon_vocab_authorization",
    feature_names=frozenset({
        "require_manager_approved",
        "require_dual_approval",
        "require_separation_of_duties",    # Add here
        "verify_approval_chain_complete",
        # ...
    }),
    regulatory_basis="SOC 2 CC6.1-6.3, SOX 404",
)
```

## Regulatory Documentation

Always document the regulatory basis:

```python
"""Require separation of duties for workflow steps.

Verifies that different actors performed different workflow steps.
This is essential for compliance with segregation of duties requirements.

Regulatory basis:
    - SOX Section 404 (Segregation of duties in financial controls)
    - SOC 2 CC5.1 (Control activities - segregation of duties)
    - COSO Framework (Control environment and control activities)
    - PCI DSS 6.4.2 (Separation of duties between dev and prod)

Common use cases:
    - Preparer != Approver (financial transactions)
    - Requester != Authorizer (access grants)
    - Developer != Deployer (change management)
    - Maker != Checker (dual control)
"""
```

## Testing Phrases

```python
import pytest
from unittest.mock import AsyncMock

async def test_require_separation_of_duties_passes():
    """SoD passes when different actors performed conflicting steps."""
    ctx = create_mock_context()
    ctx.conn.fetch = AsyncMock(return_value=[
        {"step_name": "prepare", "actor_id": UUID("11111111-1111-1111-1111-111111111111")},
        {"step_name": "approve", "actor_id": UUID("22222222-2222-2222-2222-222222222222")},
    ])

    result = await require_separation_of_duties(
        RequireSeparationOfDutiesSpecs(
            workflow_id=UUID("00000000-0000-0000-0000-000000000000"),
            conflicting_steps=["prepare", "approve"],
        ),
        ctx,
    )

    assert result["satisfied"] is True
    assert result["conflicts_found"] == ()


async def test_require_separation_of_duties_fails():
    """SoD fails when same actor performed conflicting steps."""
    ctx = create_mock_context()
    same_actor = UUID("11111111-1111-1111-1111-111111111111")
    ctx.conn.fetch = AsyncMock(return_value=[
        {"step_name": "prepare", "actor_id": same_actor},
        {"step_name": "approve", "actor_id": same_actor},
    ])

    with pytest.raises(RequirementNotMetError) as exc:
        await require_separation_of_duties(
            RequireSeparationOfDutiesSpecs(
                workflow_id=UUID("00000000-0000-0000-0000-000000000000"),
                conflicting_steps=["prepare", "approve"],
            ),
            ctx,
        )

    assert "Segregation of Duties violation" in str(exc.value)
```

## Next Steps

- [Control Surface Charters](./04-control-surfaces.md) - See phrases in action
- [Package Namespace Enforcement](./05-namespace-enforcement.md) - How packages work
