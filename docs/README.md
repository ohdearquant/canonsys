# CanonSys Documentation

Curated technical documentation from the CanonSys design corpus.

## Start here

- **[tutorials/](tutorials/)** — 5-part Charter DSL series: DSL basics, event-driven
  workflows, writing phrases, control surfaces, namespace enforcement.

## Architecture

- **[specs/](specs/)** — `ARCHITECTURE-001..002` (technical architecture, MDCP)
  and core specs: CEP factory, cryptographic verification, UCS
  validation/enforcement, universal certificate schema, safe simulation loop,
  governance kernel.
- **[architecture/domain-policy-model.md](architecture/domain-policy-model.md)** —
  how domains, packages, and policies relate.

## Design records

- **[design/](design/)** — 35 numbered design areas, each with an ADR (decision +
  rationale) and TDS (technical design spec): tenant isolation, immutability,
  evidence chain (CEP), decision certificates, policy gates, OPA integration,
  single enforcement point, UCS verification, JIT roles, break-glass, policy
  release, RSA cryptography, jurisdiction handling, TSA timestamps, PII/privacy,
  consent, waiting periods, rego builder, charters, job queue, vendor endpoints,
  observability, caching, compensating controls, registry allowlists, segregation
  of duties, corporate transactions, audit-logging governance, ethics investigation.

## Reference

- **[reference/](reference/)** — Glossaries (CDG, DGI).
- **[prds/](prds/)** — `PRD-001` (the core decision governance & certification
  engine) and `PRD-018` (the canonical control-surface template all surfaces
  inherit from).

Some documents cite internal doc IDs (e.g. `CONSTRAINTS-001`) that are not part of
this release; treat those as historical citations.
