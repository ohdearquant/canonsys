"""Message: typed container for inter-entity communication."""

from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from kron.core import Element

__all__ = ("Message",)


class Message(Element):
    """Inter-entity communication container.

    Messages are content carriers with optional routing (sender/recipient).
    recipient=None indicates broadcast to all registered entities.

    Attributes:
        content: Payload (any serializable type).
        sender: Sender entity UUID.
        recipient: Target UUID (None=broadcast).
        channel: Topic/namespace for filtering.
    """

    content: Any
    sender: UUID | None = None
    recipient: UUID | None = None
    channel: str | None = Field(None, description="Optional namespace for message grouping")

    @property
    def is_broadcast(self) -> bool:
        """True if no specific recipient (broadcast to all)."""
        return self.recipient is None

    @property
    def is_direct(self) -> bool:
        """True if has specific recipient (point-to-point)."""
        return self.recipient is not None

    @field_validator("sender", "recipient", mode="before")
    @classmethod
    def _validate_uuid(cls, v):
        """Coerce UUID|str|Element-like to UUID."""
        if v is None:
            return None
        if isinstance(v, UUID):
            return v
        if isinstance(v, str):
            return UUID(v)
        if hasattr(v, "id") and isinstance(v.id, UUID):
            return v.id
        raise ValueError(f"Expected UUID, str, or Element-like, got {type(v)}")

    def __repr__(self) -> str:
        sender_str = str(self.sender)[:8] if self.sender else "unknown"
        target = str(self.recipient)[:8] if self.recipient else "broadcast"
        channel_str = f", channel={self.channel}" if self.channel else ""
        return f"Message({sender_str} -> {target}{channel_str})"
