# Package Namespace Enforcement

This guide explains how vocabulary packages work and how namespace enforcement ensures charter
correctness.

## The Problem

Without namespace enforcement, charters can reference any phrase name:

```
charter "Bad Charter" v1.0

workflow example:
    phase foo:
        require nonexistent_phrase()     # Typo? Wrong package? Who knows!
        action make_up_anything()        # No validation
```

This leads to:

- Runtime errors when phrases don't exist
- Typos that go undetected until execution
- Unclear dependencies between charters and vocabulary

## The Solution: Package Declarations

Charters declare which vocabulary packages they use:

```
charter "Good Charter" v1.0

packages:
    - authorization
    - certification
    - consent

workflow example:
    phase foo:
        require require_manager_approved()   # From authorization package ✓
        action emit_certificate()            # From certification package ✓
        require verify_consent_token()       # From consent package ✓
```

The compiler validates that **every phrase used** is exported by a declared package.

## How It Works

### 1. Package Definition

Each package declares its exported phrases:

```python
# packages/authorization/package.py
from canon.hub.package import VocabularyPackage

AUTHORIZATION_PACKAGE = VocabularyPackage(
    name="authorization",
    domain_module="canon_vocab_authorization",
    feature_names=frozenset({
        "require_manager_approved",
        "require_dual_approval",
        "require_separation_of_duties",
        "verify_approval_chain_complete",
        "get_approval_chain",
        # ...
    }),
    regulatory_basis="SOC 2 CC6.1-6.3, SOX 404",
)
```

### 2. Charter Declaration

Charters import packages in the `packages:` section:

```
packages:
    - authorization
    - certification
```

### 3. Compilation Validation

During compilation, the resolver:

1. Collects all phrases from declared packages
2. Checks every `require` and `action` phrase against the allowed set
3. Raises `UndeclaredPhraseError` if a phrase isn't found

```python
from canon.hub.hub import build_hub

hub = build_hub()
try:
    compiled = hub.compile(charter_source)
except ExceptionGroup as eg:
    for error in eg.exceptions:
        if isinstance(error, UndeclaredPhraseError):
            print(f"Unknown phrase: {error.phrase_name}")
            print(f"  Imported packages: {error.declared_packages}")
            if error.suggested_package:
                print(f"  Did you mean to import: {error.suggested_package}")
```

## Error Messages

### Undeclared Phrase

```
UndeclaredPhraseError: Undeclared phrase: 'verify_consent_token' is not exported
by any imported package. Imported packages: authorization, certification.
Did you mean to import 'consent'?
```

### Multiple Errors

```python
ExceptionGroup: Charter 'Example' has 3 resolution error(s)
  - Undeclared phrase: 'verify_consent_token' (line 15)
  - Undeclared phrase: 'require_active_consent' (line 18)
  - Undeclared phrase: 'revoke_consent' (line 25)
```

## Available Packages

| Package           | Phrases | Purpose                                          |
| ----------------- | ------- | ------------------------------------------------ |
| `authorization`   | 22      | Approval chains, dual control, role verification |
| `certification`   | 10      | Certificate minting, attestation                 |
| `consent`         | 17      | Consent capture, verification, revocation        |
| `controls`        | 6       | Compensating controls                            |
| `core`            | 18      | Common operations (save_evidence, etc.)          |
| `data_protection` | 10      | PII classification, encryption                   |
| `deployment`      | 7       | Deployment approval, rollback                    |
| `evidence`        | 22      | Evidence chain, integrity verification           |
| `export_control`  | 11      | ITAR, EAR, OFAC compliance                       |
| `freshness`       | 10      | Data currency checks                             |
| `hr`              | 7       | HR-specific operations                           |
| `identity`        | 6       | Auth posture, MFA verification                   |
| `incident`        | 5       | Incident declaration, containment                |
| `infra`           | 10      | Infrastructure operations                        |
| `investigation`   | 5       | Investigation workflow                           |
| `justification`   | 5       | Business justification                           |
| `legal`           | 12      | Legal review, privilege                          |
| `lifecycle`       | 16      | Expiry, recertification                          |
| `notice`          | 11      | Notice delivery, waiting periods                 |
| `pattern`         | 10      | Abuse detection, history analysis                |
| `policy`          | 13      | Policy evaluation                                |
| `rif`             | 5       | RIF-specific operations                          |
| `scope`           | 10      | Scope definition, minimization                   |
| `timing`          | 13      | SLA verification, deadlines                      |
| `workflow`        | 4       | Workflow lifecycle                               |

## Listing Package Contents

```python
from canon.hub.packages import ALL_PACKAGES

for pkg in ALL_PACKAGES:
    print(f"\n{pkg.name} ({len(pkg.feature_names)} phrases):")
    for phrase in sorted(pkg.feature_names):
        print(f"  - {phrase}")
```

## Backward Compatibility

Charters without a `packages:` section compile without namespace enforcement:

```
charter "Legacy Charter" v1.0

# No packages section - all phrases allowed (legacy mode)

workflow example:
    phase foo:
        require any_phrase_name()    # No validation
```

This allows gradual migration of existing charters.

## Best Practices

### 1. Declare All Required Packages

Start with the packages you know you need:

```
packages:
    - authorization     # For approval flows
    - certification     # For certificates
    - evidence          # For evidence chain
    - policy            # For policy gates
```

### 2. Use Compiler Feedback

Let the compiler tell you what's missing:

```bash
# Compile and see errors
uv run python -c "
from canon.hub.hub import build_hub
hub = build_hub()
hub.compile(open('my_charter.canon').read())
"
```

### 3. Keep Package Lists Minimal

Only import packages you actually use. This documents dependencies clearly.

### 4. Check Package Contents

Before writing a charter, see what phrases are available:

```python
from canon.hub.registry import PackageRegistry
from canon.hub.packages import ALL_PACKAGES

reg = PackageRegistry(ALL_PACKAGES)
phrases = reg.get_package_phrases("authorization")
print(sorted(phrases))
```

## Adding New Phrases

When you need a phrase that doesn't exist:

1. Identify the appropriate package (by domain)
2. Create the phrase file (see [Writing Phrases](./03-writing-phrases.md))
3. Add to the package's `feature_names`
4. The phrase becomes available to charters importing that package

## Summary

Package namespace enforcement:

- **Validates** that all phrases come from declared packages
- **Documents** charter dependencies explicitly
- **Catches errors** at compile time, not runtime
- **Suggests fixes** when phrases are missing

This makes charters self-documenting and prevents runtime surprises.
