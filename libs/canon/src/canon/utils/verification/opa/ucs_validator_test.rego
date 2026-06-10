# UCS-v1 Validator Test Suite (OPA/Rego)
# Author: Jason La Barbera
# Captured: 2026-01-13
#
# Run with: opa test . -v

package ucs.validator_test

import data.ucs.validator.allow

# -----------------------------------------------------------------------------
# Test data (roles, CEPs, keys)
# -----------------------------------------------------------------------------
test_data := {
  "roles": {
    "TERMINATION_DECISION": ["HRBP_DIRECTOR", "ER_LEAD", "LEGAL_COUNSEL"],
    "EXEC_OVERRIDE": ["CHRO", "GC", "CEO"]
  },
  "ceps": {
    "CEP-OK": {
      "type": "CEP_CONDUCT_RECORD",
      "final_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      "status": "ACTIVE",
      "valid_until_utc": "2030-01-01T00:00:00Z"
    },
    "CEP-EXPIRED": {
      "type": "CEP_CONDUCT_RECORD",
      "final_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "status": "ACTIVE",
      "valid_until_utc": "2000-01-01T00:00:00Z"
    },
    "CEP-REVOKED": {
      "type": "CEP_CONDUCT_RECORD",
      "final_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "status": "REVOKED",
      "valid_until_utc": "2030-01-01T00:00:00Z"
    },
    "CEP-PERF": {
      "type": "CEP_PERF_METRIC",
      "final_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "status": "ACTIVE",
      "valid_until_utc": "2030-01-01T00:00:00Z"
    }
  },
  "signing_keys": {
    "kms-key-001": {
      "valid_from_utc": "2025-01-01T00:00:00Z",
      "valid_to_utc": null,
      "revoked_at_utc": null
    },
    "kms-key-revoked-yesterday": {
      "valid_from_utc": "2025-01-01T00:00:00Z",
      "valid_to_utc": null,
      "revoked_at_utc": "2026-01-12T00:00:00Z"
    }
  }
}

# -----------------------------------------------------------------------------
# Helper: A baseline valid termination certificate input
# -----------------------------------------------------------------------------
base_termination := {
  "meta": {
    "certificate_id": "11111111-1111-4111-8111-111111111111",
    "schema_version": "1.0",
    "issued_at_utc": "2026-01-13T12:00:00Z",
    "environment": "production"
  },
  "context": {
    "workflow_type": "TERMINATION_DECISION",
    "subject_token": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "jurisdiction_code": "US-CA"
  },
  "authority": {
    "issuer_id": "user_123",
    "issuer_role": "LEGAL_COUNSEL",
    "delegation_chain": null
  },
  "assertions": {
    "policy_basis": { "code": "POL-TERM-004", "exception_flag": false },
    "risk_acceptance": true,
    "parity_attested": true,
    "er_clearance": { "cleared": false, "timestamp_utc": "2026-01-13T11:59:00Z", "system_ref": "ERCHK-1" },
    "termination_type": "EGREGIOUS_CONDUCT"
  },
  "evidence_pointers": [
    {
      "cep_id": "CEP-OK",
      "type": "CEP_CONDUCT_RECORD",
      "hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    }
  ],
  "seal": {
    "previous_cert_hash": null,
    "payload_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "signature": "SIG",
    "signing_key_id": "kms-key-001",
    "signed_at_utc": "2026-01-13T12:00:00Z",
    "tsa_token": "TSA"
  }
}

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

test_allow_valid_termination {
  allow with input as base_termination
       with data as test_data
}

# --- Type-swap attack: pointer lies about CEP type ---
test_block_type_swap {
  bad := base_termination
  bad.evidence_pointers[0].cep_id = "CEP-PERF"
  bad.evidence_pointers[0].hash = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  bad.evidence_pointers[0].type = "CEP_CONDUCT_RECORD" # LIE

  not allow with input as bad
           with data as test_data
}

# --- Hash mismatch attack ---
test_block_hash_mismatch {
  bad := base_termination
  bad.evidence_pointers[0].hash = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

  not allow with input as bad
           with data as test_data
}

# --- Expired CEP blocks ---
test_block_expired_cep {
  bad := base_termination
  bad.evidence_pointers[0].cep_id = "CEP-EXPIRED"
  bad.evidence_pointers[0].hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  bad.evidence_pointers[0].type = "CEP_CONDUCT_RECORD"

  not allow with input as bad
           with data as test_data
}

# --- Revoked CEP blocks ---
test_block_revoked_cep {
  bad := base_termination
  bad.evidence_pointers[0].cep_id = "CEP-REVOKED"
  bad.evidence_pointers[0].hash = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  bad.evidence_pointers[0].type = "CEP_CONDUCT_RECORD"

  not allow with input as bad
           with data as test_data
}

# --- ER clearance true blocks (active ER context) ---
test_block_er_clearance_true {
  bad := base_termination
  bad.assertions.er_clearance.cleared = true

  not allow with input as bad
           with data as test_data
}

# --- ER clearance unknown blocks ---
test_block_er_clearance_unknown {
  bad := base_termination
  bad.assertions.er_clearance.cleared = "unknown"

  not allow with input as bad
           with data as test_data
}

# --- Role mismatch blocks ---
test_block_role_not_allowed {
  bad := base_termination
  bad.authority.issuer_role = "MANAGER_L1"

  not allow with input as bad
           with data as test_data
}

# --- Signing key revoked before signed_at blocks (time-aware) ---
test_block_revoked_key_at_signing_time {
  bad := base_termination
  bad.seal.signing_key_id = "kms-key-revoked-yesterday"
  bad.seal.signed_at_utc = "2026-01-13T12:00:00Z" # after revoked_at

  not allow with input as bad
           with data as test_data
}

# --- Exec override allows without evidence (still requires authority + risk_acceptance) ---
test_allow_exec_override_without_evidence {
  override := {
    "meta": {
      "certificate_id": "22222222-2222-4222-8222-222222222222",
      "schema_version": "1.0",
      "issued_at_utc": "2026-01-13T12:00:00Z",
      "environment": "production"
    },
    "context": {
      "workflow_type": "EXEC_OVERRIDE",
      "subject_token": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
      "jurisdiction_code": "US-CA"
    },
    "authority": {
      "issuer_id": "user_gc",
      "issuer_role": "GC",
      "delegation_chain": null
    },
    "assertions": {
      "override_scope": "Bypass standard warning requirement",
      "policy_deviation": "POL-TERM-004 requires prior warning; unmet",
      "risk_acceptance": true,
      "supporting_certificate_ids": []
    },
    "evidence_pointers": [],
    "seal": {
      "previous_cert_hash": null,
      "payload_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
      "signature": "SIG",
      "signing_key_id": "kms-key-001",
      "signed_at_utc": "2026-01-13T12:00:00Z",
      "tsa_token": "TSA"
    }
  }

  allow with input as override
       with data as test_data
}
