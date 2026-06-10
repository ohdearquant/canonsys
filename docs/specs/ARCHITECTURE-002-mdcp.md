# Material Decision Control Plane (MDCP-02)

**Document type**: Product Requirements Document **Status**: Architecture-ready (post-pressure test)
**Owner**: CanonSys **Audience**: Infrastructure, Security, Legal, Compliance, Regulated R&D
**Scope**: Domain-neutral decision governance for irreversible actions

---

## 1. Problem Statement

Enterprises increasingly rely on humans, automated systems, and AI agents to initiate materially
impactful decisions. These decisions are often irreversible, high-risk, and legally or safety
consequential.

Existing controls answer:

- Who are you? (Identity Providers)
- Can you access this resource? (RBAC / ABAC)

They do not answer:

- Should this action be executed right now, given current context and policy?

Current mechanisms—process documents, approvals, and logs—fail under automation, scale, and time
pressure. Logs record what happened; they do not prove why an action was allowed.

There is a missing infrastructure layer: a Decision Control Plane that authorizes materially
impactful actions before execution and produces proof at decision time.

---

## 2. Definitions

### Material Decision

An action that satisfies one or more of the following:

- Irreversible or costly to reverse
- Asymmetric downside risk
- Regulatory, legal, safety, or ethical exposure
- Requires future justification to internal or external parties

### Examples (illustrative)

- Personnel termination
- Privileged access grant or revocation
- Emergency infrastructure override
- Advancement of a drug candidate to the next research phase
- Approval of high-value financial transactions
- Closure of investigations or enforcement actions

---

## 3. Product Objective

Design a pre-action decision control plane that:

1. Intercepts material decisions prior to execution
2. Evaluates them against explicit policy and evidence
3. Fails closed under uncertainty, with explicit exception handling
4. Produces a cryptographically verifiable proof artifact at authorization time

The system must operate consistently for human actors, automated workflows, and AI agents.

---

## 4. Non-Goals

The system does not:

- Generate recommendations
- Replace domain expertise
- Act as an AI agent or workflow engine
- Perform advisory-only risk scoring
- Rely on post-hoc auditing as a control

Its sole function is authorization.

---

## 5. Functional Requirements

### 5.1 Decision Intent Declaration

All material actions require an explicit intent declaration containing:

- Decision class
- Target object
- Proposed action
- Claimed justification
- Initiator identity (human, system, or agent)

No implicit or ambient authority is permitted.

---

### 5.2 Context Assembly

The system assembles a decision context that is:

- Explicit and serializable
- Reviewable post hoc
- Time-bound with freshness guarantees

Context may include:

- Target attributes
- Source data references
- Risk indicators
- Prior related decisions
- Applicable policies and constraints

Each context element must include a timestamp and TTL defining acceptable staleness.

---

### 5.3 Gate Evaluation

Decisions are evaluated through a deterministic sequence of gates.

Each gate must be:

- Deterministic
- Explainable
- Justifiable via policy or evidence

#### Gate Categories

- Policy compliance checks
- Threshold validation
- Evidence sufficiency checks
- Conflict or exclusion checks
- Escalation gates (human-in-the-loop)

#### Escalation Gate

If automated gates pass but residual risk exceeds a defined threshold:

- Execution is suspended
- A human approval request is triggered
- Human attestation becomes part of the decision context and evidence set

Any gate failure or indeterminate result denies the decision.

---

### 5.4 Authorization Outcome

#### Approval

If approved, the system generates a Decision Certificate with the following properties:

- Cryptographically signed by the MDCP
- Includes:
  - Hash of decision intent
  - Hash of assembled context
  - Policy version identifiers
  - Gate evaluation results
  - Timestamp of authorization
  - Initiator identity
- Immutable and independently verifiable

#### Denial

If denied:

- A structured denial reason is returned
- No downstream execution is permitted

---

### 5.5 Enforcement Mechanism (Last-Mile Control)

Execution systems must enforce authorization by validating the Decision Certificate prior to action.

**Preferred enforcement model:**

- Cryptographic token validation (e.g., signed JWT or equivalent)
- Downstream systems must reject execution without a valid, unexpired certificate bound to the
  specific action

Network proxying is optional but not required; cryptographic binding is the primary enforcement
mechanism.

---

### 5.6 Controlled Execution

Execution is permitted only when:

- A valid Decision Certificate is presented
- Certificate scope, TTL, and binding match the requested action

---

## 6. Invariants

- No material action executes without explicit authorization
- No authorization exists without sufficient context
- No approval exists without a signed proof artifact
- All default failures are safe failures (fail-closed)
- Authorization occurs at the moment of execution, not after

---

## 7. Exception Handling

### 7.1 Break-Glass Protocol

A controlled bypass is permitted only under explicitly defined emergency conditions.

**Requirements:**

- Explicit invocation of break-glass mode
- Immediate notification to predefined executive and security stakeholders
- Permanent, distinct marking in the Decision Certificate
- Mandatory post-incident review

Break-glass is treated as a separate decision class, not an implicit override.

---

## 8. Operational Requirements

- Availability target: higher than downstream execution systems
- Deterministic behavior under partial context failure
- Transparent policy evaluation where safe to disclose
- Composable decision classes sharing a common control plane

---

## 9. Validation Criteria

The system is validated if:

- Multiple domains independently map it to existing workflows
- The same control plane applies with policy-only variation
- Objections focus on thresholds or latency, not necessity
- Reviewers recognize current manual equivalents

---

## 10. Summary

MDCP-02 defines a missing enterprise infrastructure layer: a Decision Control Plane that authorizes
irreversible actions before execution, enforces that authorization cryptographically, and produces
proof at the moment a decision is allowed.

It shifts enterprises from post-hoc auditing to pre-action governance, enabling safe operation in
environments with autonomous systems, AI agents, and high-stakes automated workflows.

---

## Pharma/Drug Discovery Application

This architecture is particularly compelling for regulated R&D environments:

| Decision Class                               | Material Impact                              |
| -------------------------------------------- | -------------------------------------------- |
| Phase advancement (IND → Phase I → II → III) | Irreversible spend, regulatory commitment    |
| Protocol amendment approval                  | Patient safety, regulatory exposure          |
| Data lock for regulatory submission          | Cannot be undone, timeline implications      |
| Safety signal escalation                     | DSMB notification, potential trial halt      |
| Manufacturing batch release                  | Patient exposure, recall liability           |
| Investigator site activation                 | Contractual, regulatory, patient recruitment |

**Why pharma needs this:**

1. **21 CFR Part 11 compliance**: Cryptographic certificates provide audit trail integrity
2. **ICH E6(R2) GCP**: Documented decision rationale at moment of action
3. **FDA inspection readiness**: Proof artifact answers "why was this allowed?"
4. **Cross-functional accountability**: Clear record of who attested to what, when
