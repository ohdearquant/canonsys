"""Re-export ConsentToken from canon-core.

Entities with @register_entity must only be defined once.
"""

# Re-export from canonical location
from canon.entities.consent import ConsentToken, ConsentTokenContent

__all__ = (
    "ConsentToken",
    "ConsentTokenContent",
)
