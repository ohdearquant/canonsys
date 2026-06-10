"""Authorization role definitions.

Standard roles for compliance surfaces and approval chains.
"""

from __future__ import annotations

__all__ = ["STANDARD_ROLES"]


# Standard role types for compliance surfaces
STANDARD_ROLES = frozenset(
    {
        "CISO",  # Chief Information Security Officer
        "CFO",  # Chief Financial Officer
        "GC",  # General Counsel
        "DPO",  # Data Protection Officer
        "CTO",  # Chief Technology Officer
        "CEO",  # Chief Executive Officer
        "BOARD",  # Board of Directors
        "AUDIT_COMMITTEE",  # Audit Committee
        "EXEC_SPONSOR",  # Executive Sponsor
        "HR",  # Human Resources Officer
        "COMPLIANCE",  # Chief Compliance Officer
    }
)
