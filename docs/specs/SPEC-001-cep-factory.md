# CEP Factory Specification (The Sanitization Engine)

**Author**: Jason La Barbera **Captured**: 2026-01-13 **Status**: Ready for Implementation

_Role: The "Vault" — The only admissible input for decision certification._

---

## 1. Core Philosophy (The "Clean Room" Principle)

Legal discovery is often lost because an organization produced "too much." A 50-page Slack export
containing one relevant harassment claim and 49 pages of irrelevant banter is a liability, not
evidence.

The CEP system exists to:

1. **Ingest** raw data from source systems
2. **Sanitize** it (redact, scope, focus)
3. **Seal** it cryptographically
4. **Disconnect** it from the live source

**Once a CEP is minted, the link to the original "radioactive" source is severed. The CEP stands
alone.**

---

## 2. The Factory Logic (Input → Transformation → Output)

The CEP is not a file upload. It is a **generated artifact**.

### Phase A: Ingestion (The Scope)

The system connects to a source (e.g., Slack, Jira, Workday) and requests a specific, time-bounded
slice of data.

**Constraint**: Data must be pulled via API, not dragged-and-dropped by a human (prevents
fabrication).

### Phase B: Sanitization (The Filter)

A human operator (Investigator/ER) is presented with the raw slice. They must:

- Select the relevant frames (specific messages/tickets)
- Redact PII of bystanders
- Mask irrelevant channels or context
- Tag the specific policy violation

### Phase C: Attestation (The Oath)

The operator must digitally sign:

> "I certify this is a true extraction of the source data and all irrelevant context has been
> redacted."

### Phase D: Sealing (The Freeze)

The system generates a static PDF/JSON of the sanitized state, hashes it, and stores it in WORM
(Write Once Read Many) storage.

---

## 3. Allowed CEP Types (The Menu)

To prevent "garbage in," the system only permits specific schema types. **There is no "General
Evidence" bucket.**

| CEP Type                   | Permitted Content                                     | Strictly Banned                                   |
| -------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| `CEP_PERF_METRIC`          | Quantitative scores, quota attainment, error rates    | Narrative feedback, "vibes," personality comments |
| `CEP_POLICY_LOG`           | Specific access logs, timecards, security alerts      | Inferences about why the log exists               |
| `CEP_CONDUCT_RECORD`       | Specific, redacted chat/email excerpts (exact quotes) | The full thread, surrounding banter, emojis       |
| `CEP_INVESTIGATION_RULING` | The Final Finding statement only                      | Witness interview transcripts, raw notes          |
| `CEP_PIP_FAIL`             | The signed PIP document + binary failure status       | Ongoing coaching notes/chats                      |

**Rule**: If you cannot fit your "proof" into one of these boxes, it is not evidence; it is an
opinion.

---

## 4. The Artifact Schema (JSON)

This is what the UCS Validator reads.

```json
{
  "cep_meta": {
    "id": "CEP-TERM-2024-8892",
    "schema_version": "1.0",
    "type": "CEP_CONDUCT_RECORD",
    "created_at_utc": "2024-10-22T14:30:00Z"
  },
  "provenance": {
    "source_system": "SLACK_ENTERPRISE_GRID",
    "ingestion_method": "API_V2_EXPORT",
    "extraction_window": {
      "start": "2024-10-01T09:00:00Z",
      "end": "2024-10-01T09:15:00Z"
    }
  },
  "sanitization": {
    "redaction_method": "HUMAN_OPERATOR_V1",
    "operator_role": "ER_INVESTIGATOR",
    "operator_attestation": true
  },
  "payload": {
    "summary": "Employee shared customer PII in #general channel.",
    "static_asset_ref": "s3://immutable-vault/2024/10/CEP-8892.pdf",
    "asset_hash": "sha256:a7f..."
  },
  "seal": {
    "final_hash": "sha256:...",
    "signature": "RSA-4096"
  }
}
```

---

## 5. The Anti-Patterns (What Breaks the Factory)

If any of these are detected during creation, the Factory fails-closed.

### The "Hyperlink" Trap

- **Attempt**: Linking to a Jira ticket URL
- **Response**: `BLOCK`. Links rot. Content changes. The factory must snapshot the state, not point
  to it.

### The "Context" Dump

- **Attempt**: Attaching a full .pst email archive
- **Response**: `BLOCK`. File size limit exceeded. Redaction validation failed.

### The "Metadata" Leak

- **Attempt**: Uploading a Word doc with "Track Changes" history
- **Response**: `BLOCK`. System forces conversion to flattened PDF/JSON before sealing.

---

## 6. The Lifecycle (Evidence Rot)

Evidence is not valid forever.

### Expiration

A `CEP_PERF_METRIC` from 3 years ago cannot support a termination today.

**Rule**: CEPs have a `valid_until` date based on type:

| CEP Type                   | Validity Period |
| -------------------------- | --------------- |
| `CEP_PERF_METRIC`          | 12 months       |
| `CEP_POLICY_LOG`           | 24 months       |
| `CEP_CONDUCT_RECORD`       | 36 months       |
| `CEP_INVESTIGATION_RULING` | Indefinite      |
| `CEP_PIP_FAIL`             | 18 months       |

### Revocation

If an Investigation is overturned, the `CEP_INVESTIGATION_RULING` must be explicitly **REVOKED**.

**Effect**: Any TDC referencing a revoked CEP immediately becomes invalid (via the Validator's chain
check).

---

## 7. Strategic Value (Why This Wins)

When a plaintiff attorney demands "All communications regarding the termination," you do not hand
over a raw Slack dump.

You hand over **The Certificate (TDC)** and **the Certified Evidence Packets (CEPs)**.

> **Attorney**: "I want the raw messages."
>
> **You**: "We do not retain raw messages for termination purposes. We rely exclusively on the
> Certified Evidence Packets, which are contemporaneous, authenticated, and sanitized records of the
> event."

You have moved the battlefield from "What did they say?" to "Is the packet valid?"

**And since the packet is valid, you win.**

---

## 8. Final System Assembly

We have completed the trinity:

| Component     | Document      | Role                                 |
| ------------- | ------------- | ------------------------------------ |
| **The Gate**  | TDC PRD       | Defines **when** we can terminate    |
| **The Guard** | UCS Validator | Enforces **how** we verify authority |
| **The Vault** | CEP PRD       | Controls **what** evidence exists    |

**This is a complete, closed-loop legal defense system.**

---

## 9. Implementation Notes

### Source System Integrations Required

| Source                | API                   | Priority |
| --------------------- | --------------------- | -------- |
| Slack Enterprise Grid | Export API v2         | HIGH     |
| Jira Cloud            | REST API v3           | MEDIUM   |
| Workday               | RAAS                  | MEDIUM   |
| Email (O365/Gmail)    | Graph API / Gmail API | LOW      |

### Storage Requirements

- WORM-compliant object storage (S3 Object Lock, Azure Immutable Blob)
- Retention per CEP type validity periods
- Cross-region replication for durability

### Sanitization UI Requirements

- Side-by-side view: raw slice | sanitized output
- Redaction tools: blur, mask, delete
- Attestation checkbox with legal language
- Preview of final sealed artifact before commit

---

## 10. Related Documents

- [PRD: Termination Decision Certification](./PRD-termination-decision-certification.md)
- [SPEC: Universal Certificate Schema](./SPEC-universal-certificate-schema.md)
- [SPEC: UCS Validator Enforcement](./SPEC-ucs-validator-enforcement.md)
- [PRD: Certified Evidence Packet](./PRD-certified-evidence-packet.md)
