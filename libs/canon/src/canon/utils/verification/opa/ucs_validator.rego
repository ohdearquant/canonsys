# UCS-v1 Validator (OPA/Rego)
# Author: Jason La Barbera
# Captured: 2026-01-13
# Mode: Fail-Closed, Type-Safe, Time-Aware
#
# Assumes:
# - JSON Schema validation happens before OPA
# - input = the candidate certificate JSON (UCS)
# - data.roles = allowed roles per workflow
# - data.ceps = CEP metadata keyed by cep_id (from SQL)
# - data.signing_keys = key windows keyed by key_id (from SQL)

package ucs.validator

import future.keywords.if
import future.keywords.in
import future.keywords.every

default allow = false
default decision = {"status": "BLOCKED", "reason": "DEFAULT_DENY"}

# -----------------------------------------------------------------------------
# 0) PRIME DIRECTIVE — Fail-Closed
# -----------------------------------------------------------------------------
allow if {
  schema_ok
  workflow_ok
  authority_ok
  evidence_ok
  signing_ok
}

decision := {"status": "APPROVED", "reason": "OK"} if allow

# -----------------------------------------------------------------------------
# 1) SCHEMA & CONTEXT (Structural Integrity)
# -----------------------------------------------------------------------------
schema_ok if {
  input.meta.schema_version == "1.0"
  input.meta.environment == "production"
  input.context.workflow_type != ""
  input.context.subject_token != ""
  input.context.jurisdiction_code != ""
}

# -----------------------------------------------------------------------------
# 2) WORKFLOW LOGIC (Constitution)
# -----------------------------------------------------------------------------
workflow_ok if {
  input.context.workflow_type == "TERMINATION_DECISION"
  termination_invariants
}

workflow_ok if {
  input.context.workflow_type == "EXEC_OVERRIDE"
  exec_override_invariants
}

# If you later add INVESTIGATION_CLOSE / PIP_FAIL, bolt them in here.

termination_invariants if {
  input.assertions.risk_acceptance == true
  input.assertions.parity_attested == true

  # IMPORTANT: "cleared == false" means no active ER context.
  # true or unknown must block.
  input.assertions.er_clearance.cleared == false
}

exec_override_invariants if {
  input.assertions.risk_acceptance == true
  input.assertions.override_scope != ""
  input.assertions.policy_deviation != ""
}

# -----------------------------------------------------------------------------
# 3) AUTHORITY VALIDATION (Role-based)
# -----------------------------------------------------------------------------
authority_ok if {
  allowed := data.roles[input.context.workflow_type]
  input.authority.issuer_role in allowed
}

# -----------------------------------------------------------------------------
# 4) EVIDENCE CHAIN (Airlock)
# -----------------------------------------------------------------------------
evidence_ok if {
  requires_evidence(input.context.workflow_type)
  count(input.evidence_pointers) > 0
  every p in input.evidence_pointers { cep_pointer_valid(p) }
}

# Override: evidence optional by design
evidence_ok if {
  not requires_evidence(input.context.workflow_type)
}

# CEP pointer must match: hash, type, status, not expired
cep_pointer_valid(p) if {
  cep := data.ceps[p.cep_id]

  # 1) integrity
  p.hash == cep.final_hash

  # 2) type-swap prevention
  p.type == cep.type

  # 3) lifecycle
  cep.status == "ACTIVE"
  time.parse_rfc3339_ns(cep.valid_until_utc) > time.now_ns()
}

# -----------------------------------------------------------------------------
# 5) SIGNING + TIME (RSA + TSA aware)
# -----------------------------------------------------------------------------
signing_ok if {
  # cryptographic signature verification happens outside OPA (recommended),
  # but OPA enforces TIME + KEY WINDOW correctness.
  key := data.signing_keys[input.seal.signing_key_id]

  # signed_at must be within key validity window
  signed_at := time.parse_rfc3339_ns(input.seal.signed_at_utc)
  valid_from := time.parse_rfc3339_ns(key.valid_from_utc)

  signed_at >= valid_from

  not key_valid_to_violated(key, signed_at)
  not key_revocation_violated(key, signed_at)

  # tsa_token must exist (time anchoring)
  input.seal.tsa_token != ""
  input.seal.signature != ""
  input.seal.payload_hash != ""
}

key_valid_to_violated(key, signed_at) if {
  key.valid_to_utc != null
  valid_to := time.parse_rfc3339_ns(key.valid_to_utc)
  signed_at > valid_to
}

key_revocation_violated(key, signed_at) if {
  key.revoked_at_utc != null
  revoked_at := time.parse_rfc3339_ns(key.revoked_at_utc)
  signed_at >= revoked_at
}

# -----------------------------------------------------------------------------
# 6) Evidence requirement map
# -----------------------------------------------------------------------------
requires_evidence("TERMINATION_DECISION") = true
requires_evidence("INVESTIGATION_CLOSE") = true
requires_evidence("PIP_FAIL") = true
requires_evidence("EXEC_OVERRIDE") = false
