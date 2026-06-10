"""Risk level types.

NIST/ISO frameworks define risk classification levels.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["RiskLevel"]

RiskLevel = Literal["low", "medium", "high", "critical"]
"""Risk level classification per NIST/ISO frameworks.

- low: Minimal impact, standard controls sufficient
- medium: Moderate impact, enhanced controls required
- high: Significant impact, strict controls required
- critical: Severe impact, maximum controls required
"""
