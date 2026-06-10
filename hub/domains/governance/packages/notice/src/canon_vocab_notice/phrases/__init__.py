"""Notice domain phrases.

Phrase-based gates for notice delivery verification.
These complement the service-based notice operations with
declarative enforcement gates.

Regulatory context:
    - FCRA Section 1681m (Adverse action notice requirements)
    - WARN Act (60-day advance notice for mass layoffs)
    - State employment notice requirements
"""

from .require_notice_delivered import (
    RequireNoticeDeliveredSpecs,
    require_notice_delivered,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "RequireNoticeDeliveredSpecs",
    # Phrase functions
    "require_notice_delivered",
]
