---
doc_type: ADR
title: "ADR-026: Background Job Queue Architecture"
version: "2.0.0"
status: active
created: "2026-01-20"
updated: "2026-01-29"
decision_date: "2026-01-20"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-020-timestamp-tsa"
  - "ADR-006-evidence-chain-cep"
successors:
  - "TDS-026-job-queue"
supersedes: null
superseded_by: null

tags:
  - infrastructure
  - async
  - job-queue
  - workflow
related:
  - "TDS-020-timestamp-tsa"
  - "TDS-006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.95
  sources: 4
  docs: full
---

## Context

### Problem Statement

CanonSys requires reliable asynchronous processing for operations that cannot block user requests or
must survive server restarts. Critical use cases include:

1. **TSA Timestamp Retry**: RFC 3161 timestamp acquisition may fail due to temporary TSA
   unavailability. Failed requests must be retried automatically with exponential backoff.

2. **Evidence Processing**: Background validation and enrichment of compliance evidence before
   sealing.

3. **Notification Delivery**: Async delivery of FCRA adverse action notices and compliance alerts
   with guaranteed delivery.

4. **Report Generation**: Long-running compliance reports and audit exports that exceed request
   timeout limits.

**Why This Matters**: Without reliable async processing, transient failures in critical compliance
operations (timestamp acquisition, notice delivery) would require manual intervention, creating
compliance gaps and operational burden.

### Background

**Current State**: Prior to this decision, all operations were synchronous, causing:

- Timeout failures for long-running operations
- Lost work on server restarts
- No automatic retry for transient failures
- Manual intervention for TSA outages

**Driving Forces**:

- **Durability**: Jobs must survive server restarts
- **Reliability**: Transient failures must trigger automatic retries
- **Isolation**: Multi-tenant workloads must not interfere
- **Auditability**: Job execution must produce evidence for compliance

### Assumptions

1. PostgreSQL is the primary database and can handle job queue workload
2. Job volume is <1000 jobs/second (sufficient for current scale)
3. Most jobs complete within 5 minutes
4. Job payload sizes are reasonable (<1MB)

### Constraints

| Type        | Constraint                               | Impact                                     |
| ----------- | ---------------------------------------- | ------------------------------------------ |
| Technical   | Single database deployment               | In-memory queue not viable (no durability) |
| Technical   | Must not add infrastructure dependencies | Redis/RabbitMQ rejected                    |
| Compliance  | Job execution must be auditable          | Evidence integration required              |
| Operational | No additional services to monitor        | PostgreSQL-only solution preferred         |

---

## Decision

### Summary

**We will** adopt a PostgreSQL-backed job queue with a storage-agnostic protocol design, exponential
backoff retry, and dead letter queue for failed jobs.

### Rationale

**Key factors in the decision**:

1. **Single Database**: PostgreSQL for job storage eliminates operational complexity. No Redis or
   RabbitMQ to deploy, monitor, or secure.

2. **Transactional Consistency**: Jobs and application data share transactions. A job can be created
   atomically with the evidence it references.

3. **Atomic Claiming**: PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` provides atomic job
   claiming without race conditions.

4. **Storage Agnostic**: Protocol-based design allows swapping implementations (PostgreSQL for
   production, in-memory for testing, Redis if scaling requires).

### Implementation Approach

```
Producers (API/Services) --> JobQueue --> JobStorage (PostgreSQL)
                                              |
                                              v
                                         JobWorker --> JobHandler
```

**Job State Machine**:

```
PENDING --> CLAIMED --> RUNNING --> COMPLETED
                          |
                          +--> FAILED (retriable) --> PENDING
                          |
                          +--> DEAD_LETTER (max retries exceeded)

PENDING --> CANCELLED
DEAD_LETTER --> PENDING (manual retry)
```

**Retry Schedule** (exponential backoff with 10% jitter):

| Attempt | Base Delay | With Jitter |
| ------- | ---------- | ----------- |
| 1       | 60s        | 54s-66s     |
| 2       | 120s       | 108s-132s   |
| 3       | 240s       | 216s-264s   |

### Alternatives Considered

#### Alternative 1: Redis-Based Queue (Rejected)

**Description**: Use Redis for job storage with pub/sub for worker notification.

| Criterion              | Score (1-5) | Notes                      |
| ---------------------- | ----------- | -------------------------- |
| Operational simplicity | 2           | Additional infrastructure  |
| Transactional          | 2           | No atomicity with app data |
| Durability             | 3           | Requires AOF configuration |
| Latency                | 5           | Push-based, sub-second     |

**Why Not Chosen**: Adds infrastructure complexity without proportional benefit at current scale.

#### Alternative 2: Celery/RQ (Rejected)

**Description**: Use mature job queue library with broker abstraction.

| Criterion              | Score (1-5) | Notes                             |
| ---------------------- | ----------- | --------------------------------- |
| Ecosystem              | 5           | Mature, many integrations         |
| Operational simplicity | 2           | Requires Redis/RabbitMQ           |
| Control                | 2           | Opinionated patterns may conflict |
| Compliance integration | 2           | No built-in evidence binding      |

**Why Not Chosen**: Heavy dependencies and no control over compliance-specific behaviors.

#### Alternative 3: Cloud-Native (SQS/Cloud Tasks) (Rejected)

**Description**: Use managed cloud queue service.

| Criterion              | Score (1-5) | Notes                          |
| ---------------------- | ----------- | ------------------------------ |
| Operational simplicity | 5           | Fully managed                  |
| Transactional          | 1           | No atomicity with app data     |
| Data sovereignty       | 2           | Data leaves our infrastructure |
| Audit completeness     | 2           | Evidence chain fragmentation   |

**Why Not Chosen**: Data sovereignty concerns and evidence chain fragmentation unacceptable.

### Decision Matrix

| Criterion          | Weight | Redis   | Celery  | Cloud   | **PostgreSQL** |
| ------------------ | ------ | ------- | ------- | ------- | -------------- |
| Operational        | 30%    | 2       | 2       | 5       | **5**          |
| Transactional      | 25%    | 2       | 2       | 1       | **5**          |
| Control            | 20%    | 4       | 2       | 3       | **5**          |
| Compliance         | 15%    | 3       | 2       | 2       | **5**          |
| Latency            | 10%    | 5       | 4       | 4       | **3**          |
| **Weighted Total** | 100%   | **2.8** | **2.3** | **3.0** | **4.7**        |

---

## Consequences

### Positive Consequences

1. **Operational Simplicity**: No additional infrastructure beyond PostgreSQL
2. **Transactional Consistency**: Jobs and application data share transactions
3. **Full Auditability**: Job lifecycle events integrated with compliance evidence
4. **Reliable Retry**: Exponential backoff with jitter handles transient failures gracefully
5. **Graceful Degradation**: Dead letter queue preserves failed jobs for analysis
6. **Testing Simplicity**: In-memory storage enables fast, isolated tests
7. **Priority Control**: Critical compliance operations get precedence

### Negative Consequences

1. **Latency Floor**: PostgreSQL polling introduces minimum ~5s delay vs. push-based queues
   - _Mitigation_: Acceptable for async operations; critical path remains synchronous

2. **Scale Ceiling**: Single PostgreSQL limits throughput to ~1000 jobs/second
   - _Mitigation_: Sufficient for current scale; Redis can be added later via storage protocol

3. **Dead Letter Accumulation**: Requires operational attention
   - _Mitigation_: Alerting on dead letter queue depth; dashboard for visibility

### Neutral Consequences

1. **Worker Deployment**: Currently runs as background task; can scale to separate process if needed

### Risks

| Risk                       | Likelihood | Impact | Mitigation                                 |
| -------------------------- | ---------- | ------ | ------------------------------------------ |
| PostgreSQL bottleneck      | L          | M      | Monitor; Redis fallback via protocol       |
| Orphaned CLAIMED jobs      | L          | M      | Heartbeat timeout; automatic reset         |
| Dead letter growth         | M          | L      | Alerting; periodic review process          |
| Clock skew affecting retry | L          | L      | Use monotonic time for internal scheduling |

### Dependencies Introduced

| Dependency | Type     | Version | Stability | Notes                   |
| ---------- | -------- | ------- | --------- | ----------------------- |
| asyncio    | Standard | 3.11+   | Stable    | Python standard library |

### Migration Impact

**Backwards Compatibility**: N/A (new feature)

**Rollback Plan**: Disable worker; jobs remain in queue; re-enable when ready

---

## Verification

### Success Criteria

- [x] Jobs persist across server restarts
- [x] Retry with exponential backoff works correctly
- [x] Dead letter queue captures failed jobs
- [x] Multi-tenant isolation verified
- [x] Idempotency key prevents duplicate jobs
- [x] Graceful shutdown completes in-flight jobs

### Metrics to Track

| Metric              | Baseline | Target | Review Date |
| ------------------- | -------- | ------ | ----------- |
| Job success rate    | N/A      | > 99%  | 2026-02-20  |
| Retry effectiveness | N/A      | > 90%  | 2026-02-20  |
| Dead letter rate    | N/A      | < 0.1% | 2026-02-20  |
| Avg processing time | N/A      | < 30s  | 2026-02-20  |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Platform Team

---

## Related Artifacts

### Builds On

- `ADR-020-timestamp-tsa`: RFC 3161 timestamp integration (primary consumer)
- `ADR-006-evidence-chain-cep`: Evidence entity (timestamp attestation target)
- `ADR-003-immutability`: Immutable records pattern

### Impacts

- `TDS-026-job-queue`: Technical specification implementing this decision

---

## Discussion Record

### Key Questions

**Q1**: Should we use Redis for lower latency?

- **Answer**: No. 5s polling latency is acceptable for async operations. Operational simplicity
  wins.
- **Raised By**: Architecture review
- **Date**: 2026-01-20

**Q2**: How do we handle jobs orphaned by crashed workers?

- **Answer**: Jobs in CLAIMED state beyond heartbeat timeout are reset to PENDING.
- **Raised By**: Operations review
- **Date**: 2026-01-20

### Approval Record

| Reviewer | Role    | Decision | Date       |
| -------- | ------- | -------- | ---------- |
| Ocean    | Creator | Approve  | 2026-01-20 |

---

## References

- Implementation: `libs/canon-services/src/canon_services/jobs/`
- TDS: [TDS-026-job-queue.md](./TDS-026-job-queue.md)
- Related: TDS-020-timestamp-tsa (timestamp retry handler)
- Related: TDS-006-evidence-chain-cep (evidence timestamping)

---

## Vocabulary Mapping

### Package

- **Package**: `workflow` (planned)
- **Location**: `hub/foundation/packages/workflow/`

### Phrases

This is an infrastructure component. No vocabulary phrases are directly implemented, but the job
queue supports the following compliance operations:

| Consumer Operation    | Job Type           | Vocabulary Phrase               |
| --------------------- | ------------------ | ------------------------------- |
| Timestamp attestation | `timestamp_retry`  | `request_timestamp_attestation` |
| Notice delivery       | `notice_delivery`  | `verify_notice_delivered`       |
| Evidence processing   | `evidence_process` | `chain_evidence`                |

### Control Surfaces

| Surface                  | Description              | Integration                                          |
| ------------------------ | ------------------------ | ---------------------------------------------------- |
| PII Export Authorization | PII Export Authorization | Large export jobs via JobQueue                       |
| Disaster Recovery Test   | Disaster Recovery Test   | Long-running DR test jobs with progress tracking     |
| AI Incident Disclosure   | AI Incident Disclosure   | Async notification delivery with exponential backoff |
| All                      | Timestamp Retry          | RFC 3161 timestamps acquired after TSA outage        |
