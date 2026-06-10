# 026-job-queue - Vocabulary Mapping

## Package Mapping

| Aspect   | Value                                             |
| -------- | ------------------------------------------------- |
| Package  | `workflow` (planned)                              |
| Location | `hub/foundation/packages/workflow/` |
| Status   | Infrastructure (no direct phrases)                |

## Phrases

This is an infrastructure component. The job queue does not implement vocabulary phrases directly,
but enables async execution of compliance operations.

### Supported Operations

| Consumer Operation    | Job Type           | Vocabulary Phrase               |
| --------------------- | ------------------ | ------------------------------- |
| Timestamp attestation | `timestamp_retry`  | `request_timestamp_attestation` |
| Notice delivery       | `notice_delivery`  | `verify_notice_delivered`       |
| Evidence processing   | `evidence_process` | `chain_evidence`                |
| Report generation     | `report_generate`  | N/A (infrastructure)            |

## Control Surfaces

| Surface                  | Description              | Integration                                          |
| ------------------------ | ------------------------ | ---------------------------------------------------- |
| PII Export Authorization | PII Export Authorization | Large export jobs processed via JobQueue with retry  |
| Disaster Recovery Test   | Disaster Recovery Test   | Long-running DR test jobs with progress tracking     |
| AI Incident Disclosure   | AI Incident Disclosure   | Async notification delivery with exponential backoff |
| All                      | Timestamp Retry          | RFC 3161 timestamps acquired even after TSA outage   |

## Code Paths

### Primary Implementation

- `libs/canon-services/src/canon_services/jobs/`

### Key Files

| File                         | Purpose                        |
| ---------------------------- | ------------------------------ |
| `jobs/enums.py`              | JobStatus, JobPriority enums   |
| `jobs/models.py`             | Job, QueueStats data models    |
| `jobs/protocols.py`          | JobStorage protocol definition |
| `jobs/queue.py`              | JobQueue implementation        |
| `jobs/worker.py`             | JobWorker implementation       |
| `jobs/handlers/timestamp.py` | RFC 3161 timestamp retry       |

## Dependencies

### Upstream

| Component          | Purpose                    |
| ------------------ | -------------------------- |
| `canon.utils` | canonicalize, compute_hash |

### Downstream

| Component             | Purpose                         |
| --------------------- | ------------------------------- |
| Timestamp attestation | TSA retry on failure            |
| Notification service  | Async delivery with retry       |
| Report generation     | Long-running background jobs    |
| Evidence processing   | Async validation and enrichment |

## Verification

- **Last verified**: 2026-01-29
- **Design doc version**: 2.0.0
