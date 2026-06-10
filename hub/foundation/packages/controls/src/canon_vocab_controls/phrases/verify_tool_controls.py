"""Verify required controls for a tool.

Checks that a tool has all required controls documented and active
based on its category and any bypass configurations.

Regulatory Context:
    - SOX Section 404 (Application controls)
    - SOC 2 CC6.1 (Logical access controls)
    - NYC LL144 (AEDT tool requirements)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyToolControlsSpecs", "verify_required_controls_for_tool"]


class VerifyToolControlsSpecs(BaseModel):
    """Specs for verify tool controls phrase."""

    # inputs
    tool_id: UUID
    tool_category: str
    bypass_type: str
    controls_doc_id: UUID
    # outputs
    satisfied: bool
    required_controls: tuple[str, ...]
    present_controls: tuple[str, ...]
    missing_controls: tuple[str, ...]


@canon_phrase(
    Operable.from_structure(VerifyToolControlsSpecs),
    inputs={"tool_id", "tool_category", "bypass_type", "controls_doc_id"},
    outputs={
        "satisfied",
        "tool_id",
        "tool_category",
        "required_controls",
        "present_controls",
        "missing_controls",
    },
)
async def verify_required_controls_for_tool(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify required controls for a tool are present.

    Checks that a tool has all required controls documented and active
    based on its category and any bypass configurations. This is critical
    for AEDT compliance where specific controls are mandated.

    Args:
        options: Verification options (tool_id, tool_category, bypass_type, controls_doc_id)
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfied, tool_id, tool_category, required_controls, present_controls, missing_controls

    Regulatory:
        - SOX Section 404: Application controls must be documented
        - SOC 2 CC6.1: Logical access controls for applications
        - NYC LL144: AEDT tools require bias audits and notices
    """
    tool_id = options.get("tool_id")
    tool_category = options.get("tool_category")
    bypass_type = options.get("bypass_type")
    controls_doc_id = options.get("controls_doc_id")

    # Query required controls for this tool category and bypass type
    required_query = """
        SELECT control_name
        FROM tool_control_requirements
        WHERE tool_category = $1
          AND (bypass_type = $2 OR bypass_type = 'all')
        ORDER BY control_name
    """
    required_rows = await fetch(
        required_query,
        tool_category,
        bypass_type,
        conn=ctx.conn,
    )

    if not required_rows:
        # No requirements defined - satisfied by default
        return {
            "satisfied": True,
            "tool_id": tool_id,
            "tool_category": tool_category,
            "required_controls": (),
            "present_controls": (),
            "missing_controls": (),
        }

    required_controls = {row["control_name"] for row in required_rows}

    # Query controls present for this tool
    present_query = """
        SELECT DISTINCT c.control_name
        FROM controls c
        JOIN tool_controls tc ON tc.control_id = c.control_id
        WHERE tc.tool_id = $1
          AND tc.controls_doc_id = $2
          AND tc.tenant_id = $3
          AND c.status = 'active'
    """
    present_rows = await fetch(
        present_query,
        tool_id,
        controls_doc_id,
        ctx.tenant_id,
        conn=ctx.conn,
    )

    present_controls = {row["control_name"] for row in present_rows}

    # Calculate missing
    missing_controls = required_controls - present_controls

    return {
        "satisfied": len(missing_controls) == 0,
        "tool_id": tool_id,
        "tool_category": tool_category,
        "required_controls": tuple(sorted(required_controls)),
        "present_controls": tuple(sorted(present_controls)),
        "missing_controls": tuple(sorted(missing_controls)),
    }
