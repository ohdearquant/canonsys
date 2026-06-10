"""Infrastructure feature exceptions.

Re-exports common errors used by infrastructure features.
Infrastructure features primarily use RequirementNotMetError for gate failures.
"""

from canon.enforcement.errors import RequirementNotMetError

__all__ = ["RequirementNotMetError"]
