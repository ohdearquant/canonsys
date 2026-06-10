---
doc_type: ADR
title: "ADR-024: Rego Policy Builder"
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
  - ADR-009-opa
  - ADR-011-policy-resolution
successors:
  - TDS-024-rego-builder
supersedes: null
superseded_by: null

tags:
  - rego
  - policy-builder
  - transpilation
  - two-key-model
related:
  - TDS-024-rego-builder
  - ADR-009-opa
  - ADR-011-policy-resolution
pr: null

quality:
  confidence: 0.90
  sources: 3
  docs: full
---

# ADR-024: Rego Policy Builder

## Context

### Problem Statement

CanonSys requires programmatic generation of Rego policies from PolicyDefinition entities. The
Two-Key Model mandates that Legal owns WHAT is required (PolicyDefinition) while Engineering owns
HOW enforcement happens (Rego transpilation). Neither key alone can modify enforcement behavior.

**Why This Matters**: Manual Rego authoring is error-prone, inconsistent across authors, and
violates the Two-Key Model because Legal cannot verify raw Rego. Generated Rego must be type-safe,
fail-closed by default, and produce structured output compatible with the Evidence system.

### Background

**Current State**: PolicyDefinition entities define governance rules. These must be transpiled to
executable Rego for OPA/regorus evaluation.

**Requirements**:

1. **Type-Safe Generation**: Rego source must be generated from typed PolicyDefinition entities
2. **Fail-Closed Defaults**: All generated Rego must include `default allow := false`
3. **Template Consistency**: Common patterns (gate composition, deny reasons) must be uniform
4. **Validation Before Deployment**: Generated Rego must pass validation before bundle building
5. **Version Control Integration**: Bundle revisions must be deterministic
6. **Evidence Integration**: Generated Rego must produce structured output for audit

**Driving Forces**:

- **Two-Key Model**: Legal edits PolicyDefinition; Engineering owns transpilation
- **Fail-closed requirement**: Undefined inputs must deny, never allow
- **Audit trail**: Generated Rego must produce evidence-grade output
- **Reproducibility**: Same policy versions = same bundle revision

### Assumptions

1. PolicyDefinition schema is stable and covers most policy requirements
2. Complex policies can be expressed through template extensions, not custom Rego
3. OPA/regorus execution is the target runtime for generated Rego

### Constraints

| Type        | Constraint                         | Impact                                                |
| ----------- | ---------------------------------- | ----------------------------------------------------- |
| Technical   | Must generate valid Rego v1 syntax | Use `import rego.v1` and modern syntax                |
| Business    | Two-Key Model compliance           | Neither Legal nor Engineering can unilaterally change |
| Regulatory  | Fail-closed by construction        | `default allow := false` in every policy              |
| Operational | Deterministic bundles              | Same inputs = same revision hash                      |

---

## Decision

### Summary

**We will** use a type-safe RegoBuilder that transpiles PolicyDefinition to Rego source code via
template-based generation, with validation before deployment and deterministic bundle revision
hashing.

### Rationale

**Key factors in the decision**:

1. **Two-Key Model enforcement**: PolicyDefinition is Legal's interface; RegoBuilder is
   Engineering's
2. **Fail-closed by construction**: Templates always include `default allow := false`
3. **Audit integration**: Structured `gate_output` integrates with Evidence system
4. **Reproducibility**: Hash-based revision enables cache invalidation and rollback verification

### Implementation Approach

**Two-Key Architecture**:

```
PolicyDefinition (Key 1)           RegoBuilder (Key 2)
+------------------+               +------------------+
| policy_id        |               | transpile()      |
| jurisdictions    |      +        | validate()       |
| required_gates   |               | build_bundle()   |
| authority        |               | templates        |
+------------------+               +------------------+
         |                                  |
         +----------------+-----------------+
                          |
                          v
                +------------------+
                | Executable Rego  |
                | (Enforcement)    |
                +------------------+
```

**Generated Rego Structure**:

```rego
# Generated from PolicyDefinition: {policy_id} v{version}
# DO NOT EDIT - Changes should be made to PolicyDefinition

package canonsys.statutory.{jurisdiction}.{domain}

import rego.v1

metadata := { ... }

default applicable := false
applicable if { ... }

default allow := false
allow if {
    applicable
    gates_passed
    not deny
}

gates_passed if {
    every gate_id in required_gates {
        gate_result_passed(gate_id)
    }
}

default deny := false
deny if { ... }

deny_reasons contains reason if { ... }

gate_output := { ... }
```

**Package Naming Convention**:

```
policy_id: us-nyc.fair_chance.adverse_action
  -> package: canonsys.statutory.nyc.fair_chance

policy_id: us.fcra.background_check
  -> package: canonsys.statutory.us.fcra
```

### Alternatives Considered

#### Alternative 1: Manual Rego Authoring

**Description**: Write Rego policies by hand with code review for correctness.

| Criterion     | Score (1-5) | Notes                                      |
| ------------- | ----------- | ------------------------------------------ |
| Flexibility   | 5           | Full control over Rego expression          |
| Error risk    | 1           | Manual string construction = syntax errors |
| Two-Key Model | 1           | Legal cannot verify raw Rego               |
| Consistency   | 2           | Different authors, different patterns      |

**Why Not Chosen**: Violates Two-Key Model. Error-prone. No fail-closed guarantee.

#### Alternative 2: Rego DSL / Macro System

**Description**: Create a custom DSL that compiles to Rego.

| Criterion      | Score (1-5) | Notes                                |
| -------------- | ----------- | ------------------------------------ |
| Abstraction    | 5           | Higher level than raw Rego           |
| Learning curve | 1           | Another language to learn            |
| Debugging      | 2           | DSL errors map poorly to Rego output |
| Ecosystem      | 2           | Cannot use standard Rego tooling     |

**Why Not Chosen**: Another language to learn. Debugging opacity. OPA ecosystem friction.

#### Alternative 3: Type-Safe AST Builder (Chosen)

**Description**: Build Rego programmatically from PolicyDefinition via template-based generation.

| Criterion         | Score (1-5) | Notes                                   |
| ----------------- | ----------- | --------------------------------------- |
| Type safety       | 5           | Python types catch errors at generation |
| Two-Key Model     | 5           | PolicyDefinition is Legal's interface   |
| OPA compatibility | 5           | Standard Rego output, all tooling works |
| Fail-closed       | 5           | Templates always include defaults       |

**Why Chosen**: Type safety, Two-Key Model alignment, standard Rego output.

### Decision Matrix

| Criterion          | Weight | Manual Rego | DSL/Macro | Chosen (Template) |
| ------------------ | ------ | ----------- | --------- | ----------------- |
| Two-Key compliance | 30%    | 1           | 3         | 5                 |
| Type safety        | 25%    | 2           | 4         | 5                 |
| Fail-closed        | 25%    | 2           | 4         | 5                 |
| Maintainability    | 20%    | 3           | 2         | 4                 |
| **Weighted Total** | 100%   | **1.85**    | **3.30**  | **4.80**          |

---

## Consequences

### Positive Consequences

1. **Consistency**: All generated Rego follows identical patterns - gate composition, fail-closed
   defaults, output structure
2. **Type Safety**: PolicyDefinition is typed. Generation errors caught at transpilation time, not
   OPA runtime
3. **Two-Key Model Enforcement**: Legal edits PolicyDefinition. Engineering owns RegoBuilder.
   Neither unilaterally changes enforcement
4. **Evidence Integration**: Structured `gate_output` integrates directly with Evidence system
5. **Fail-Closed by Construction**: Templates always include `default allow := false` - impossible
   to generate fail-open
6. **Reproducible Builds**: Deterministic revision hashing enables reproducible deployments

### Negative Consequences

1. **Abstraction Leakage**: Complex policies may require template extensions
   - **Mitigation**: Extend PolicyDefinition schema before adding custom templates
2. **Template Maintenance**: New Rego patterns require template updates
   - **Mitigation**: Template changes are Engineering's responsibility (Key 2)
3. **Limited Expressiveness**: Cannot express arbitrary Rego
   - **Mitigation**: Most compliance policies fit standard patterns

### Neutral Consequences

1. **Indirection**: Debugging requires tracing PolicyDefinition -> template -> generated Rego -> OPA
   evaluation

### Risks

| Risk                              | Likelihood | Impact | Mitigation                                      |
| --------------------------------- | ---------- | ------ | ----------------------------------------------- |
| Template bug affects all policies | L          | H      | Validation checks before bundling               |
| Policy schema insufficient        | M          | M      | Extend PolicyDefinition before custom templates |
| Debugging complexity              | M          | L      | Include source policy_id in generated comments  |

### Dependencies Introduced

| Dependency | Type    | Version | Stability | Notes                    |
| ---------- | ------- | ------- | --------- | ------------------------ |
| `regorus`  | Library | 0.2.x   | Stable    | Rust-based OPA evaluator |

### Migration Impact

**Backwards Compatibility**: Existing hand-written Rego must be regenerated

**Migration Steps**:

1. Create corresponding PolicyDefinition entities
2. Generate Rego via RegoBuilder
3. Diff generated vs. hand-written to verify semantic equivalence
4. Replace hand-written with generated
5. Delete hand-written Rego (single source of truth)

**Rollback Plan**:

1. Restore hand-written Rego from version control
2. Skip RegoBuilder in bundle generation

---

## Verification

### Success Criteria

- [ ] All generated Rego includes `default allow := false`
- [ ] Generated Rego passes `opa check` validation
- [ ] Same PolicyDefinition versions produce identical bundle revision
- [ ] `gate_output` structure matches Evidence schema

### Metrics to Track

| Metric                | Baseline | Target | Review Date |
| --------------------- | -------- | ------ | ----------- |
| Validation error rate | N/A      | 0%     | 2026-02-15  |
| Template coverage     | N/A      | > 95%  | 2026-02-15  |
| Build reproducibility | N/A      | 100%   | 2026-02-15  |

### Review Schedule

- **Initial Review**: 2026-02-15 (30 days after activation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: alpha[architect]

---

## Related Artifacts

### Builds On

- `ADR-009-opa`: Embedded Regorus over OPA server (execution target)
- `ADR-011-policy-resolution`: Creates ResolvedPolicy from generated Rego

### Impacts

- `TDS-024-rego-builder`: Technical implementation specification
- All PolicyDefinition entities (source for generation)
- Policy release workflow (generates bundles)

---

## Vocabulary Mapping

### Package Reference

**Primary Package**: `hub/foundation/packages/policy/`

### Infrastructure Role

RegoBuilder is **infrastructure**, not vocabulary. It does not define phrases - it transpiles
PolicyDefinition (which references phrases) to executable Rego. Every control surface with a
`policy:` section uses RegoBuilder indirectly.

### Related Vocabulary

Phrases referenced in PolicyDefinition.required_gates are enforced via generated Rego:

| PolicyDefinition Field | Rego Output                                                   |
| ---------------------- | ------------------------------------------------------------- |
| `required_gates`       | `gates_passed if { every gate_id in required_gates { ... } }` |
| `deny_conditions`      | `deny if { ... }`                                             |
| `metadata.authority`   | `metadata := { "authority": { ... } }`                        |

---

## References

- TDS: `docs-shared/canonsys/01_design/024-rego-builder/TDS-024-rego-builder.md`
- RegoBuilder: `libs/canon/src/canon/utils/opa/rego_builder.py`
- PolicyDefinition: `libs/canon/src/canon/entities/policy/definition.py`
- PolicyEngine: `libs/canon/src/canon/utils/opa/engine.py`
- OPA Documentation: https://www.openpolicyagent.org/docs/latest/
- Rego v1 Syntax: https://www.openpolicyagent.org/docs/latest/policy-language/
