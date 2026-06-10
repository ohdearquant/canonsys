---
doc_type: mapping
title: "ADR-024 Rego Builder - Code Mapping"
version: "2.0.0"
updated: "2026-01-29"
adr: ADR-024-rego-builder
tds: TDS-024-rego-builder
---

# 024-rego-builder - Code Mapping

## Vocabulary Package Reference

**Primary Package**: `hub/foundation/packages/policy/`

### Infrastructure Role

RegoBuilder is **infrastructure**, not vocabulary. It transpiles PolicyDefinition (which references
vocabulary phrases) to executable Rego.

### PolicyDefinition Integration

| PolicyDefinition Field | Rego Output                                                   |
| ---------------------- | ------------------------------------------------------------- |
| `required_gates`       | `gates_passed if { every gate_id in required_gates { ... } }` |
| `deny_conditions`      | `deny if { ... }`                                             |
| `metadata.authority`   | `metadata := { "authority": { ... } }`                        |

### Control Surface Impact

Every control surface with a `policy:` section uses RegoBuilder:

- Transpiles PolicyDefinition to Rego package
- Generates fail-closed defaults (`default allow := false`)
- Produces structured `gate_output` for Evidence integration

---

## Primary Code Paths

- `libs/canon/src/canon/utils/opa/rego_builder.py` - RegoBuilder implementation (812 lines)
- `libs/canon/src/canon/utils/opa/engine.py` - PolicyEngine using regorus
- `libs/canon/src/canon/utils/opa/resolver.py` - PolicyResolver for policy lookup
- `libs/canon/src/canon/utils/opa/gate.py` - OPAGate for Rego-based gates
- `libs/canon/src/canon/entities/policy/definition.py` - PolicyDefinition entity

## Key Classes/Functions

### RegoBuilder Types

- **RegoModule** (`rego_builder.py:L39-L74`) - Generated Rego module:
  - package, source, policy_id, version, generated_at, metadata
  - Properties: `filename`, `relative_path` (derived from package)

- **ValidationSeverity** (`rego_builder.py:L77-L82`) - StrEnum: ERROR, WARNING, INFO

- **ValidationIssue** (`rego_builder.py:L85-L101`) - Validation finding with severity, message,
  line, column, rule

- **ValidationResult** (`rego_builder.py:L104-L126`) - Validation result:
  - valid (bool), issues (tuple), parsed_at
  - Properties: `errors`, `warnings`

- **BundleInfo** (`rego_builder.py:L129-L152`) - Built bundle metadata:
  - revision, path, loaded_at, policy_count, roots, metadata
  - Property: `hash` (sha256:{revision})

### RegoBuilder Class

- **transpile()** (`rego_builder.py:L196-L227`) - Generate RegoModule from PolicyDefinition
- **validate()** (`rego_builder.py:L229-L260`) - Validate Rego syntax and semantics
- **build_bundle()** (`rego_builder.py:L262-L322`) - Build OPA bundle from modules + data

### Transpilation Internals

- **_derive_package()** (`rego_builder.py:L348-L379`) - Derive package from policy_id (e.g.,
  `us-nyc.fair_chance.adverse_action` -> `canonsys.statutory.nyc.fair_chance`)
- **_generate_rego()** (`rego_builder.py:L381-L497`) - Template-based Rego generation with:
  - Metadata section from PolicyDefinition
  - Applicability rules from jurisdictions/action_types
  - Gate requirements from required_gates
  - Main evaluation (allow, deny, deny_reasons)
  - Structured output for Evidence integration

### Validation Helpers

- **_check_required_elements()** (`rego_builder.py:L605-L644`) - Package declaration, default allow,
  rego.v1 import
- **_check_syntax_issues()** (`rego_builder.py:L646-L678`) - Brace balancing, common typos
- **_check_best_practices()** (`rego_builder.py:L680-L710`) - Metadata object, deny_reasons presence

## Architectural Patterns

- **Two-Key Model**: PolicyDefinition (Legal's WHAT) + RegoBuilder (Engineering's HOW). Neither
  alone modifies enforcement.

- **Template-Based Generation**: Rego generated from templates with PolicyDefinition field
  substitution. Not arbitrary Rego authoring.

- **Fail-Closed Default**: Generated Rego includes `default allow := false`. Explicit fail-closed
  semantics.

- **Structured Output Contract**: `gate_output` object provides standardized Evidence integration
  format.

- **OPA Bundle Format**: Builds standard OPA bundle directory structure with .manifest, .rego files,
  and data/ subdirectory.

- **Revision Hashing**: Bundle revision derived from policy_id:version pairs. Deterministic
  versioning.

## Dependencies

- **Depends on**:
  - `canon.entities.policy.PolicyDefinition` - Source for transpilation
  - `canon.utils.compute_hash` - Revision generation
  - `canon.exceptions.TranspilationError, BundleError` - Error types
  - `kron.utils.now_utc` - Timestamp generation

- **Depended by**:
  - `canon.utils.opa.engine.PolicyEngine` - Loads built bundles
  - Policy release workflows - Transpile and bundle policies

## Key Decisions (for ADR candidates)

1. **Transpile, not interpret**: PolicyDefinition is transpiled to Rego at deploy time, not
   interpreted at runtime. Rego is the execution format.

2. **Package naming convention**: `canonsys.statutory.{jurisdiction}.{domain}` derived from
   policy_id. Consistent namespace.

3. **Rego v1 mandatory**: Generated Rego requires `import rego.v1`. Modern Rego syntax only.

4. **Gate composition in Rego**: `gates_passed` rule composes required_gates via
   `every gate_id in required_gates`. Composition is in Rego, not Python.

5. **Validation is regex-based**: Syntax validation uses regex, not full OPA parser. Trade-off:
   simpler, less complete.

6. **Bundle as deployment unit**: Policies deployed as OPA bundles, not individual files. Bundle
   revision provides versioning.

## Open Questions

- Full ASN.1 validation: Should we use `opa check` or regorus parser for complete syntax validation?
- Incremental updates: Can bundles be updated incrementally or always full rebuild?
- WASM compilation: Should bundles include WASM for performance?
- Hot reload: How to reload policies without service restart?
- Multi-tenant bundles: One bundle per tenant or shared bundle with tenant data?
