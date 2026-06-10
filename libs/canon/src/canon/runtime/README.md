# Charter Runtime Engine Specification

**Status**: To Be Built
**Priority**: Critical Path
**Author**: Claude (from Ocean's direction)
**Date**: 2026-02-04

## Overview

The Charter Runtime Engine is the orchestration layer that executes compiled Charter workflows. It manages phase lifecycle, evaluates dependencies, cascades completions, and enforces compliance gates.

## Current State (What Exists)

1. **Entities** (`canon/src/canon/core/charter/`):
   - `Charter` - The governance document definition
   - `CharterRun` - Workflow instance linking Charter to subject/related entity
   - `PhaseExecution` - Per-phase state (assignee, status, gates, grants, evidence)

2. **DSL Compiler** (`canon/src/canon/dsl/`):
   - Lexer, Parser, Resolver, Compiler
   - Produces `CompiledCharter` with phase DAG, feature names, schema types

3. **Manual Shim** (current hack):
   - Approval endpoints manually UPDATE phase_executions
   - No automatic cascade, no grant management

## What Needs to Be Built

### 1. Phase State Machine (`phase_state.py`)

```python
class PhaseStatus(Enum):
    """Phase lifecycle states."""
    PENDING = "pending"           # Created, waiting for requires
    WAITING_USER = "waiting_user" # Requires satisfied, in assignee inbox
    IN_PROGRESS = "in_progress"   # Assignee has started work
    COMPLETED = "completed"       # Successfully finished
    FAILED = "failed"             # Failed/rejected
    SKIPPED = "skipped"           # Skipped (e.g., skip_svp=True)

# Valid transitions
PHASE_TRANSITIONS = {
    PhaseStatus.PENDING: {PhaseStatus.WAITING_USER, PhaseStatus.SKIPPED},
    PhaseStatus.WAITING_USER: {PhaseStatus.IN_PROGRESS, PhaseStatus.SKIPPED},
    PhaseStatus.IN_PROGRESS: {PhaseStatus.COMPLETED, PhaseStatus.FAILED},
    PhaseStatus.COMPLETED: set(),  # Terminal
    PhaseStatus.FAILED: set(),     # Terminal
    PhaseStatus.SKIPPED: set(),    # Terminal
}
```

### 2. Require Evaluator (`require_eval.py`)

Evaluates `require` expressions from compiled charter:

```python
@dataclass
class RequireResult:
    satisfied: bool
    unsatisfied_requires: list[str]  # Which requires are blocking

async def evaluate_requires(
    run_id: UUID,
    phase_name: str,
    compiled_charter: CompiledCharter,
    conn,
) -> RequireResult:
    """
    Evaluate all require conditions for a phase.

    Require types:
    - `require other_phase.passed` → check phase_executions WHERE phase_name=other_phase AND status=completed
    - `require gate_name` → check gate evaluation (future)
    """
    phase_node = compiled_charter.get_phase(phase_name)

    for require in phase_node.requires:
        if require.type == "phase_completion":
            # Check if referenced phase is completed
            row = await select_one(
                "phase_executions",
                where={"run_id": run_id, "phase_name": require.phase_ref, "status": "completed"},
                conn=conn,
            )
            if not row:
                return RequireResult(satisfied=False, unsatisfied_requires=[require.expr])

    return RequireResult(satisfied=True, unsatisfied_requires=[])
```

### 3. Phase Cascade Engine (`cascade.py`)

The core orchestration - when a phase completes, cascade to downstream phases:

```python
async def on_phase_completed(
    run_id: UUID,
    phase_name: str,
    action_by_id: UUID,
    action_notes: str | None,
    conn,
) -> list[str]:
    """
    Handle phase completion and cascade to downstream phases.

    Returns list of phase names that were activated.
    """
    # 1. Mark current phase as completed
    await execute(
        """
        UPDATE phase_executions
        SET status = 'completed', action_at = NOW(), action_by_id = $1, action_notes = $2
        WHERE run_id = $3 AND phase_name = $4
        """,
        action_by_id, action_notes, run_id, phase_name,
        conn=conn,
    )

    # 2. Record evidence
    await record_phase_evidence(run_id, phase_name, "completed", action_by_id, conn)

    # 3. Revoke any grants for this phase
    await revoke_phase_grants(run_id, phase_name, conn)

    # 4. Find downstream phases and evaluate their requires
    charter_run = await get_charter_run(run_id, conn)
    compiled = get_compiled_charter(charter_run.charter_id)

    activated = []
    downstream_phases = compiled.get_downstream_phases(phase_name)

    for downstream in downstream_phases:
        result = await evaluate_requires(run_id, downstream, compiled, conn)
        if result.satisfied:
            # Activate the phase
            await activate_phase(run_id, downstream, compiled, conn)
            activated.append(downstream)

    # 5. Check if workflow is complete (all terminal phases done)
    if await is_workflow_complete(run_id, compiled, conn):
        await complete_charter_run(run_id, conn)

    return activated


async def activate_phase(
    run_id: UUID,
    phase_name: str,
    compiled: CompiledCharter,
    conn,
) -> None:
    """
    Activate a phase - set to waiting_user and create grants.
    """
    phase_node = compiled.get_phase(phase_name)

    # 1. Update phase status
    await execute(
        """
        UPDATE phase_executions
        SET status = 'waiting_user', updated_at = NOW()
        WHERE run_id = $1 AND phase_name = $2
        """,
        run_id, phase_name,
        conn=conn,
    )

    # 2. Create grants if defined
    for grant in phase_node.grants:
        await create_phase_grant(run_id, phase_name, grant, conn)
```

### 4. Grant Lifecycle Manager (`grants.py`)

Manages JIT document access tied to phase lifecycle:

```python
async def create_phase_grant(
    run_id: UUID,
    phase_name: str,
    grant: GrantNode,
    conn,
) -> UUID:
    """
    Create a document access grant for a phase.

    Grant is active while phase is pending/waiting_user.
    Automatically revoked on phase completion.
    """
    charter_run = await get_charter_run(run_id, conn)
    phase_exec = await get_phase_execution(run_id, phase_name, conn)

    # Determine expiry
    if grant.ttl_minutes:
        expires_at = datetime.now(UTC) + timedelta(minutes=grant.ttl_minutes)
    else:
        expires_at = None  # Phase-scoped (revoked on completion)

    token_id = uuid4()
    await insert(
        "document_access_tokens",
        data={
            "id": token_id,
            "tenant_id": charter_run.tenant_id,
            "grantee_id": phase_exec.assignee_id,
            "subject_id": charter_run.subject_id,
            "document_type": grant.document_type,  # "resume", etc.
            "status": "active",
            "granted_by_phase": phase_name,
            "run_id": run_id,
            "expires_at": expires_at,
            "created_at": datetime.now(UTC),
        },
        conn=conn,
    )

    # Link grant to phase execution
    await execute(
        """
        UPDATE phase_executions
        SET grant_token_ids = array_append(grant_token_ids, $1)
        WHERE run_id = $2 AND phase_name = $3
        """,
        token_id, run_id, phase_name,
        conn=conn,
    )

    return token_id


async def revoke_phase_grants(run_id: UUID, phase_name: str, conn) -> None:
    """
    Revoke all grants associated with a phase (on phase completion).
    """
    await execute(
        """
        UPDATE document_access_tokens
        SET status = 'revoked', revoked_at = NOW()
        WHERE run_id = $1 AND granted_by_phase = $2 AND status = 'active'
        """,
        run_id, phase_name,
        conn=conn,
    )
```

### 5. Inbox Query (`inbox.py`)

Efficient inbox derivation for users:

```python
@dataclass
class InboxItem:
    run_id: UUID
    phase_name: str
    charter_name: str
    subject_name: str
    related_entity_type: str
    related_entity_id: UUID
    waiting_since: datetime
    is_overdue: bool
    grants: list[str]  # Document types accessible

async def get_user_inbox(
    user_id: UUID,
    tenant_id: UUID,
    conn,
) -> list[InboxItem]:
    """
    Get all pending phases assigned to a user.

    A phase is in user's inbox when:
    - status = 'waiting_user'
    - assignee_id = user_id OR assignee_role in user.roles
    """
    rows = await fetch(
        """
        SELECT
            pe.run_id,
            pe.phase_name,
            pe.assignee_role,
            pe.created_at as waiting_since,
            pe.grant_token_ids,
            cr.charter_id,
            cr.subject_id,
            cr.related_entity_type,
            cr.related_entity_id,
            c.name as charter_name,
            p.first_name || ' ' || p.last_name as subject_name
        FROM phase_executions pe
        JOIN charter_runs cr ON pe.run_id = cr.id
        JOIN charters c ON cr.charter_id = c.id
        JOIN persons p ON cr.subject_id = p.id
        JOIN users u ON u.id = $1
        WHERE pe.status = 'waiting_user'
          AND cr.tenant_id = $2
          AND (
              pe.assignee_id = $1
              OR pe.assignee_role = ANY(u.roles)
          )
        ORDER BY pe.created_at ASC
        """,
        user_id, tenant_id,
        conn=conn,
    )

    return [InboxItem(**row) for row in rows]
```

### 6. Workflow Starter (`workflow.py`)

Initialize a new workflow run:

```python
async def start_workflow(
    charter_id: UUID,
    subject_id: UUID,
    related_entity_type: str,
    related_entity_id: UUID,
    workflow_name: str,
    initiated_by_id: UUID,
    tenant_id: UUID,
    conn,
) -> UUID:
    """
    Start a new charter workflow.

    Creates CharterRun and all PhaseExecutions in PENDING state,
    then activates phases with no requires (entry points).
    """
    compiled = get_compiled_charter(charter_id)
    workflow = compiled.workflows[workflow_name]

    # 1. Create CharterRun
    run_id = uuid4()
    await insert(
        "charter_runs",
        data={
            "id": run_id,
            "tenant_id": tenant_id,
            "charter_id": charter_id,
            "subject_id": subject_id,
            "related_entity_type": related_entity_type,
            "related_entity_id": related_entity_id,
            "current_workflow": workflow_name,
            "status": "active",
            "started_at": datetime.now(UTC),
            "started_by_id": initiated_by_id,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
        conn=conn,
    )

    # 2. Create PhaseExecutions for all phases (initially PENDING)
    for phase_name, phase_node in workflow.phases.items():
        await insert(
            "phase_executions",
            data={
                "id": uuid4(),
                "tenant_id": tenant_id,
                "run_id": run_id,
                "phase_name": phase_name,
                "assignee_role": phase_node.assignee_role,
                "status": "pending",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
            conn=conn,
        )

    # 3. Activate entry phases (phases with no requires)
    entry_phases = compiled.get_entry_phases(workflow_name)
    for phase_name in entry_phases:
        await activate_phase(run_id, phase_name, compiled, conn)

    return run_id
```

### 7. Integration Points

#### 7.1 Replace Manual Sync in Approval Endpoints

**Before** (current hack in `offers.py`):
```python
# Manual SQL updates
await execute("UPDATE phase_executions SET status = 'completed' ...")
await execute("UPDATE phase_executions SET status = 'waiting_user' ...")
```

**After** (using runtime):
```python
from canon.runtime import on_phase_completed

# Single call handles everything
activated = await on_phase_completed(
    run_id=charter_run_id,
    phase_name="finance_approval",
    action_by_id=current_user.id,
    action_notes=request.comments,
    conn=conn,
)
```

#### 7.2 Dashboard Inbox Integration

**Before** (manual query per role):
```python
# Separate queries for each dashboard type
```

**After** (unified inbox):
```python
from canon.runtime import get_user_inbox

inbox = await get_user_inbox(current_user.id, tenant_id, conn)
# Returns all pending items across all workflow types
```

### 8. File Structure

```
canon/src/canon/runtime/
├── __init__.py           # Public API exports
├── phase_state.py        # PhaseStatus enum, transitions
├── require_eval.py       # Require expression evaluator
├── cascade.py            # Phase completion cascade engine
├── grants.py             # Grant lifecycle management
├── inbox.py              # User inbox derivation
├── workflow.py           # Workflow start/complete
├── evidence.py           # Automatic evidence recording
└── registry.py           # Compiled charter cache/registry
```

### 9. Database Schema Updates Needed

```sql
-- Add columns to phase_executions if not present
ALTER TABLE phase_executions ADD COLUMN IF NOT EXISTS grant_token_ids UUID[] DEFAULT '{}';
ALTER TABLE phase_executions ADD COLUMN IF NOT EXISTS gate_results JSONB DEFAULT '{}';

-- Add columns to document_access_tokens for grant tracking
ALTER TABLE document_access_tokens ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES charter_runs(id);
ALTER TABLE document_access_tokens ADD COLUMN IF NOT EXISTS granted_by_phase TEXT;

-- Index for inbox queries
CREATE INDEX IF NOT EXISTS idx_phase_executions_inbox
ON phase_executions(status, assignee_role)
WHERE status = 'waiting_user';
```

### 10. Testing Strategy

1. **Unit Tests**: Each module independently
   - `test_require_eval.py` - Require expression evaluation
   - `test_cascade.py` - Phase cascade logic
   - `test_grants.py` - Grant lifecycle

2. **Integration Tests**: Full workflow execution
   - Start workflow → complete phases → verify cascade
   - Grant creation → phase completion → verify revocation
   - Inbox population → action → verify removal

3. **E2E Tests**: Browser-based approval flow
   - Multi-user approval chain
   - Concurrent approvals
   - Grant-gated document access

## Implementation Order

1. **Phase 1**: Core State Machine
   - `phase_state.py`
   - `require_eval.py`
   - `cascade.py` (basic version)

2. **Phase 2**: Grants & Evidence
   - `grants.py`
   - `evidence.py`
   - Database schema updates

3. **Phase 3**: Integration
   - `inbox.py`
   - `workflow.py`
   - Replace manual shims in approval endpoints

4. **Phase 4**: Testing & Polish
   - Comprehensive tests
   - Error handling
   - Logging/observability

## Success Criteria

1. **Automatic Cascade**: Completing a phase automatically activates downstream phases
2. **Inbox Works**: User sees pending phases in their inbox based on role
3. **Grants Lifecycle**: Document access granted on phase activation, revoked on completion
4. **No Manual SQL**: Approval endpoints use runtime API, not raw SQL
5. **Evidence Trail**: All phase transitions automatically recorded as evidence
