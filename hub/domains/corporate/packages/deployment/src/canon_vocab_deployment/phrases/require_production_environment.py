"""Require operation to be in production environment.

Gate check for production-only actions, ensuring operations
are only performed in production environment.

Regulatory:
    - SOC 2 CC6.7 (Change management)
    - ISO 27001 A.12.1.4 (Separation of environments)
    - PCI DSS v4.0 Req. 6.5 (Separate test/production)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ProductionEnvironmentRequiredError
from ..types import EnvironmentType

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireProductionEnvironmentSpecs", "require_production_environment"]


class RequireProductionEnvironmentSpecs(BaseModel):
    """Specs for require production environment phrase."""

    # inputs
    resource_id: UUID
    # outputs
    environment: EnvironmentType | None = None


require_production_environment_operable = Operable.from_structure(RequireProductionEnvironmentSpecs)


@canon_phrase(
    require_production_environment_operable,
    inputs={"resource_id"},
    outputs={"resource_id", "environment"},
)
async def require_production_environment(
    options: RequireProductionEnvironmentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that resource is in production environment.

    Raises ProductionEnvironmentRequiredError if resource is not in
    production environment.

    Regulatory:
        - SOC 2 CC6.7 (Change management)
        - ISO 27001 A.12.1.4 (Separation of environments)
        - PCI DSS v4.0 Req. 6.5 (Separate test/production)

    Args:
        options: Options containing resource_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id and environment if in production.

    Raises:
        ProductionEnvironmentRequiredError: If not in production environment.
    """
    resource_id = options.resource_id

    row = await select_one(
        "resource_environments",
        {
            "tenant_id": ctx.tenant_id,
            "resource_id": resource_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise ProductionEnvironmentRequiredError(
            resource_id=resource_id,
            environment=EnvironmentType.DEVELOPMENT,
            context={"reason": "Resource environment unknown"},
        )

    env = EnvironmentType(row["environment_type"])

    if env != EnvironmentType.PRODUCTION:
        raise ProductionEnvironmentRequiredError(
            resource_id=resource_id,
            environment=env,
        )

    return {
        "resource_id": resource_id,
        "environment": env,
    }


# Export auto-generated types from the Phrase object
RequireProductionEnvironmentOptions = require_production_environment.options_type
RequireProductionEnvironmentResult = require_production_environment.result_type
