"""Charter domain: tenant governance documents and runtime execution.

Charters define compliance workflows as declarative specifications
that compile to validated DAGs. Each charter belongs to a tenant
and defines phases, gates, evidence requirements, and role bindings.

Runtime entities:
    CharterRun: Runtime instance of an executing charter workflow
    PhaseExecution: Per-phase state tracking within a CharterRun
"""

from .charter import Charter, CharterContent, CharterStatus
from .phase_execution import PhaseExecution, PhaseExecutionContent, PhaseStatus
from .run import CharterRun, CharterRunContent, CharterRunStatus

__all__ = (
    # Charter definition
    "Charter",
    "CharterContent",
    "CharterStatus",
    # Charter runtime
    "CharterRun",
    "CharterRunContent",
    "CharterRunStatus",
    # Phase execution
    "PhaseExecution",
    "PhaseExecutionContent",
    "PhaseStatus",
)
