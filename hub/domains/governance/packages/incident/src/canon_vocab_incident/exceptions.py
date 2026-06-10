"""Incident feature exceptions.

Re-exports common errors used by incident features.
Incident features primarily use RequirementNotMetError for gate failures.
"""

from canon.enforcement.errors import RequirementNotMetError

__all__ = ["RequirementNotMetError"]
