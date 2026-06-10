# Glossary: Certified Decision Gate (CDG)

**Version**: 1.0 (2026-01-17) **Status**: Canonical **Author**: Jason La Barbera

---

## Certified Decision Gate (CDG)

### Definition

A Certified Decision Gate is a tenant-aware, policy-bound admission control that determines whether
a consequential action is allowed to proceed at runtime, and emits a cryptographic decision
certificate if permitted.

### What it does (and only does)

- Evaluates authority, policy, and evidence presence
- Makes a yes/no determination at the decision boundary
- Issues an immutable certificate that proves the action was allowed at that moment
- Gets out of the way

### What it is not

- Not a workflow engine
- Not an approval UI
- Not a compliance report
- Not process enforcement

---

## One-Line Summary

> CanonSys provides a Certified Decision Gate that enforces tenant-aware admission control for
> consequential actions and emits immutable proof at runtime.

---

## Related Concepts

- **Decision Certificate**: The artifact produced by a CDG when an action is allowed
- **Decision Control Plane**: The infrastructure layer that hosts CDGs
- **Policy Evaluation**: The deterministic check performed by the CDG
- **Evidence Binding**: Cryptographic linking of evidence to certificates
