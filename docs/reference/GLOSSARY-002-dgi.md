# Glossary: Decision Governance Infrastructure (DGI)

**Version**: 1.0 (2026-01-18) **Status**: Canonical **Author**: Jason La Barbera

---

## Decision Governance Infrastructure (DGI)

### Definition

Decision Governance Infrastructure is a pre-action control plane that intercepts irreversible human
and machine decisions, enforces policy under bounded certainty, fails closed under ambiguity, and
emits a verifiable verdict at the moment of execution.

### What It Replaces

- PDFs, policies, and training
- Post-hoc logs and approvals
- "Trust the operator" governance
- Compliance as interpretation

### What It Introduces

- Executable requirements (law, policy, intent)
- Deterministic decision gates
- Replayable, court-grade evidence
- Scoped, time-bound authority
- Safe autonomy for AI agents

---

## The 10 Highest-Value Irreversible Decisions

Enterprise-agnostic decisions where mistakes are asymmetric (downside >> upside) and post-hoc logs
are useless.

| #  | Decision                                                   | Why Irreversible                                                                                |
| -- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1  | **Employment Termination / Adverse Action**                | Once executed, you can't un-fire someone. Liability is statutory, reputational, and permanent.  |
| 2  | **Access Revocation / Privilege Grant** (Prod, Data, Keys) | One bad grant or missed revoke = breach, outage, or regulatory incident.                        |
| 3  | **Production Deploy / Schema Migration**                   | You can roll code back; you can't roll impact back once data or customers are hit.              |
| 4  | **AI Agent Action with External Effect**                   | Sending emails, denying credit, changing pricing, triggering enforcement. Once sent, it's real. |
| 5  | **Financial Transfer / Contractual Commitment**            | Money moves, obligations attach. Undo is legal, slow, and expensive.                            |
| 6  | **Investigation Close / Compliance Attestation**           | Declaring "we're done" or "we're compliant" creates legal reliance.                             |
| 7  | **Data Use / Data Sharing Boundary Crossing**              | Once sensitive data is accessed or exported, the violation already happened.                    |
| 8  | **Incident Response Override (Break-Glass)**               | Emergency actions taken under pressure cause the second outage if ungated.                      |
| 9  | **Model Promotion / Policy Change to Active State**        | Promoting a model or policy affects thousands of downstream decisions instantly.                |
| 10 | **Organizational Authority Delegation** (Human or Agent)   | Granting someone—or something—the right to decide on your behalf is itself irreversible.        |

**Common Property**: The decision matters more than the execution.

---

## The One-Sentence Wedge

> "We don't govern systems after they act. We govern decisions before they execute."

---

## Category Differentiation

### Why DGI Is a New Category (Not GRC, Not Compliance)

| Existing Category    | What It Does             | What DGI Does                    |
| -------------------- | ------------------------ | -------------------------------- |
| **GRC**              | Manages risk artifacts   | Governs decision execution       |
| **Compliance Tools** | Document process         | Enforce requirements             |
| **Observability**    | Explains failures        | Prevents invalid actions         |
| **Access Control**   | Answers _who_ and _what_ | Answers _should this happen now_ |

**DGI sits between intent and action.** No existing system owns that layer.

---

## Anchoring Principle

People will try to shove DGI into:

- "compliance"
- "policy engines"
- "workflow automation"

**Response**: Anchor everything around **irreversibility** and **pre-action proof**.

If an action can be safely undone, it's not your fight. If it can't—you own it.

---

## Related Concepts

- **[Certified Decision Gate (CDG)](GLOSSARY-001-cdg.md)**: The admission control component within
  DGI
- **Decision Certificate**: The artifact emitted when a decision is allowed
- **Fail Closed**: System behavior when certainty is insufficient (block, don't allow)
- **Bounded Certainty**: Policy evaluation with known evidence state

---

**Source**: Jason La Barbera, 2026-01-18
