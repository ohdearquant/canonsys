"""Session: conversation orchestration with messages, branches, and services.

Core types:
    Session: Central orchestrator owning branches, messages, services.
    Branch: Message progression with access control (capabilities, resources).
    Message: Inter-entity communication container.
    Exchange: Async message router between entity mailboxes.

Validators (raise on failure):
    resource_must_exist_in_session
    resource_must_be_accessible_by_branch
    capabilities_must_be_subset_of_branch
    resolve_branch_exists_in_session
"""

from .exchange import Exchange
from .message import Message
from .session import (
    Branch,
    Session,
    SessionConfig,
    capabilities_must_be_subset_of_branch,
    resolve_branch_exists_in_session,
    resource_must_be_accessible_by_branch,
    resource_must_exist_in_session,
)

__all__ = (
    "Branch",
    "Exchange",
    "Message",
    "Session",
    "SessionConfig",
    "capabilities_must_be_subset_of_branch",
    "resolve_branch_exists_in_session",
    "resource_must_be_accessible_by_branch",
    "resource_must_exist_in_session",
)
