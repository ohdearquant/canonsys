# SPEC-009: Governance Kernel Protobuf Definition

> Source: Jason La Barbera (2026-01-19 08:00) Status: Machine Contract Type: Protocol Buffer
> Definition

---

## Purpose

This file (`governance_kernel.proto`) is the **source of truth** for the system.

If a control surface cannot be serialized into this format, it is invalid.

---

## Why This Matters

- **Bridges the gap**: Management reads Parts A/B/C. Engineering reads Part D. They describe the
  exact same system.
- **Forces rigidity**: The `google.protobuf.Struct` facts field tells engineers: "The shape of the
  data goes here, but the governance of that data stays in the kernel."
- **Creates a Factory**: The PRDs are just configuration files that populate the
  `DecisionRequest` message.

---

## Protobuf Definition

```protobuf
syntax = "proto3";

package governance.kernel.v1;

import "google/protobuf/timestamp.proto";
import "google/protobuf/struct.proto";

// THE KERNEL: Everything inherits from this structure.

// 1. The Request (Input)
message DecisionRequest {
  string decision_id = 1; // UUID
  string control_surface_id = 2; // e.g., "PRD-09-WIRE-TRANSFER"
  Archetype archetype = 3;

  // The Facts: Specific to the control surface (Strict Schema)
  google.protobuf.Struct facts = 4;

  // The Evidence: Artifacts proving due process
  repeated EvidenceArtifact evidence = 5;

  // The Signers: Who is requesting this?
  repeated Signer signers = 6;
}

// 2. The Certificate (Output / Immutable Record)
message DecisionCertificate {
  string certificate_id = 1;
  string decision_request_id = 2;

  Verdict verdict = 3;
  string reason_code = 4; // e.g., "POLICY_CHECK_FAILURE"

  // Cryptographic Proofs
  string facts_hash = 5;    // SHA-256 of the facts struct
  string evidence_hash = 6; // Merkle root of evidence artifacts
  string policy_hash = 7;   // SHA-256 of the Rego/Wasm policy used

  google.protobuf.Timestamp issued_at = 8;
  string issuer_signature = 9; // The Governance Engine's signature
}

// 3. Supporting Types

enum Verdict {
  VERDICT_UNSPECIFIED = 0;
  VERDICT_DENY = 1; // Default state (Fail Closed)
  VERDICT_ALLOW = 2;
}

enum Archetype {
  ARCHETYPE_UNSPECIFIED = 0;
  ARCHETYPE_STATUS_CHANGE = 1;
  ARCHETYPE_PERMISSION_GRANT = 2;
  ARCHETYPE_EXECUTION_AUTHORIZATION = 3;
  ARCHETYPE_OVERRIDE_EXCEPTION = 4;
  ARCHETYPE_DISCLOSURE_EXPOSURE = 5;
  ARCHETYPE_DESTRUCTION_LOSS = 6;
}

message EvidenceArtifact {
  string artifact_id = 1;
  string type = 2; // e.g., "FRAUD_SCREEN_PDF"
  string uri = 3;  // Location in blob storage
  string hash = 4; // SHA-256 of the file content
}

message Signer {
  string signer_id = 1;
  string role = 2; // e.g., "CFO"
  bool is_human = 3;
  string cryptographic_signature = 4; // The approval signature
}
```

---

## Registry Format (Swarm-Ingestible)

PRDs are for humans + governance reviews; the registry is what runs.

```yaml
registry_version: cs-registry-v1
surfaces:
  - decision_name: LARGE_WIRE_TRANSFER_EXECUTION
    domain: FINANCE_TREASURY
    archetype: EXECUTION_AUTHORIZATION
    risk_tier: HIGH
    facts_schema_id: facts.wire_transfer.v1
    policy:
      engine: OPA
      package: finance.wire_transfer
      version: v1.0.0
    config:
      thresholds:
        amount_usd_hard_gate_min: 100000
      required_roles:
        - FINANCE_CONTROLLER
        - CFO
      min_human_signers: 2
      replay_retention_days: 2555
```

**Swarms load registry → route requests → enforce policy → mint certs.**

---

## Integration Notes

1. All control surfaces must serialize to `DecisionRequest`
2. All verdicts produce a `DecisionCertificate`
3. Evidence artifacts are referenced by hash, stored in blob storage
4. Signers include both agents and humans with distinct key types
