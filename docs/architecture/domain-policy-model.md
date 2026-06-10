# Policy Binding Model

## Decision (2026-02-07)

Policies live in charters, not in domain.toml.

## Three Layers

| Layer | Role | Owns |
|-------|------|------|
| `hub/policies/` | Physical storage, organized by jurisdiction | `.rego` files |
| Charter DSL | Behavioral binding — which policy evaluates at which phase | `policy <name>` directive |
| `domain.toml` | Namespace — groups charters (and thus indirectly their policies) by domain | `charters = [...]` |

## Why Not domain.toml?

- domain.toml is organizational (namespace), not behavioral (execution).
- Charters already declare packages — they should also declare policies.
- Adding `policies` to domain.toml duplicates what charters specify.
- Policy applicability is derivable: domain.toml → charters → policy references.

## Policy Organization

```
hub/policies/
├── manifest.toml
└── jurisdictions/
    ├── federal/
    │   └── policies/
    │       └── compensation/
    │           └── offer_band_check.rego
    ├── nyc/
    │   └── policies/
    │       └── aedt/
    │           └── ll144_bias_audit.rego
    └── eu/
        └── policies/
            └── ai_act/
                └── high_risk_classification.rego
```

Jurisdiction-based organization serves auditors ("show me all federal policies").
Charter-based binding serves developers ("which policies apply to this workflow").

## Charter DSL Extension (Future)

```
charter "Exception Offer" v1.0

schemas: canon.hr@2026.01

workflow approval_chain:
    phase offer_review:
        require initiation.passed
        policy offer_band_check        # <-- policy evaluated here
        action review_compensation()
        output CompensationDecision
```

The `policy` directive tells the executor to evaluate the named policy
(resolved via PolicyEngine) before or during the phase.

## Chain

```
hub/policies/*.rego  →  referenced by charters  →  charters grouped by domain.toml
```

Clean chain, no duplication. Each layer has a single responsibility.
