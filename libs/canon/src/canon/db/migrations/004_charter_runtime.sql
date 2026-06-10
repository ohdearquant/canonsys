-- Migration 004: Charter Runtime Support
-- Adds columns and indexes needed for the Charter Runtime Engine
-- Date: 2026-02-04

-- ============================================================================
-- Phase Executions: Add grant tracking and gate results
-- ============================================================================

-- Track grant tokens issued for this phase
ALTER TABLE phase_executions
ADD COLUMN IF NOT EXISTS grant_token_ids UUID[] DEFAULT '{}';

-- Store gate evaluation results (for debugging/audit)
ALTER TABLE phase_executions
ADD COLUMN IF NOT EXISTS gate_results JSONB DEFAULT '{}';

-- Track when phase was activated (moved to waiting_user)
ALTER TABLE phase_executions
ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ;

-- ============================================================================
-- Document Access Tokens: Link to Charter workflow
-- ============================================================================

-- Link grant to the workflow run that issued it
ALTER TABLE document_access_tokens
ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES charter_runs(id) ON DELETE CASCADE;

-- Track which phase issued this grant (for revocation on phase completion)
ALTER TABLE document_access_tokens
ADD COLUMN IF NOT EXISTS granted_by_phase TEXT;

-- Track revocation details
ALTER TABLE document_access_tokens
ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

ALTER TABLE document_access_tokens
ADD COLUMN IF NOT EXISTS revoked_by_id UUID REFERENCES users(id);

ALTER TABLE document_access_tokens
ADD COLUMN IF NOT EXISTS revoke_reason TEXT;

-- ============================================================================
-- Indexes for Inbox Queries
-- ============================================================================

-- Efficient inbox query: find phases waiting for user action
CREATE INDEX IF NOT EXISTS idx_phase_executions_inbox
ON phase_executions(status, assignee_role)
WHERE status = 'waiting_user';

-- Find phases by run (for cascade operations)
CREATE INDEX IF NOT EXISTS idx_phase_executions_run
ON phase_executions(run_id, status);

-- Find active grants by run/phase (for revocation)
CREATE INDEX IF NOT EXISTS idx_document_access_tokens_run_phase
ON document_access_tokens(run_id, granted_by_phase)
WHERE status = 'active';

-- Find grants by grantee (for user's active access)
CREATE INDEX IF NOT EXISTS idx_document_access_tokens_grantee
ON document_access_tokens(grantee_id, status)
WHERE status = 'active';

-- ============================================================================
-- Charter Runs: Add workflow tracking columns if missing
-- ============================================================================

-- Track current workflow being executed
ALTER TABLE charter_runs
ADD COLUMN IF NOT EXISTS current_workflow TEXT;

-- Track workflow completion
ALTER TABLE charter_runs
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

ALTER TABLE charter_runs
ADD COLUMN IF NOT EXISTS outcome TEXT; -- 'completed', 'failed', 'cancelled'

-- ============================================================================
-- Update existing phase_executions to have activated_at
-- ============================================================================

UPDATE phase_executions
SET activated_at = created_at
WHERE status IN ('waiting_user', 'in_progress', 'completed', 'failed')
  AND activated_at IS NULL;
