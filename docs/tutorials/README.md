# CanonSys Hub Tutorials

Welcome to the Charter DSL and vocabulary system tutorials.

## Getting Started

1. **[Charter DSL Basics](./01-charter-dsl-basics.md)** - Introduction to charter structure
2. **[Event-Driven Workflows](./02-event-driven-workflows.md)** - Triggers and await statements
3. **[Writing Vocabulary Phrases](./03-writing-phrases.md)** - Create custom phrases
4. **[Control Surface Charters](./04-control-surfaces.md)** - Real-world examples
5. **[Package Namespace Enforcement](./05-namespace-enforcement.md)** - How packages work

## Quick Reference

### Compile a Charter

```python
from canon.hub.hub import build_hub

hub = build_hub()
compiled = hub.compile("""
charter "Example" v1.0

packages:
    - authorization
    - certification

workflow example:
    phase approval:
        require require_manager_approved()
        action emit_certificate()
        evidence approval_record
        certify immutable

roles:
    approver:
        actions: [emit_certificate]
        requires_mfa: true
""")

print(compiled.name)           # "Example"
print(compiled.feature_names)  # frozenset({'require_manager_approved', 'emit_certificate'})
```

### List Available Packages

```python
from canon.hub.packages import ALL_PACKAGES

for pkg in ALL_PACKAGES:
    print(f"{pkg.name}: {len(pkg.feature_names)} phrases")
```

### Check Package Phrases

```python
from canon.hub.registry import PackageRegistry
from canon.hub.packages import ALL_PACKAGES

reg = PackageRegistry(ALL_PACKAGES)
phrases = reg.get_package_phrases("authorization")
print(sorted(phrases))
```

## Charter Structure

```
charter "Name" v1.0

packages:           # Vocabulary imports
    - package_name

triggers:           # External events
    event_name

workflow name:
    phase name:
        await trigger          # Wait for event
        require phrase()       # Gate condition
        action phrase()        # Execute operation
        when condition:        # Conditional block
            require ...
            action ...
        evidence name          # Bind evidence
        certify immutable      # Certification level

situations:
    when field == "value":
        waiting_period X..Y days
        require phrase()

roles:
    role_name:
        actions: [action1, action2]
        requires_mfa: true
        break_glass: false
```

## Vocabulary Packages (28 total)

| Package       | Count | Purpose                       |
| ------------- | ----- | ----------------------------- |
| authorization | 22    | Approval chains, dual control |
| certification | 10    | Certificate minting           |
| consent       | 17    | Consent management            |
| evidence      | 22    | Evidence chain                |
| lifecycle     | 16    | Expiry, recertification       |
| policy        | 13    | Policy evaluation             |
| timing        | 13    | SLA, deadlines                |
| ...           | ...   | ...                           |

**Total: 279 phrases across 28 packages**

## Control Surfaces (92 total)

| Domain       | Count |
| ------------ | ----- |
| HR           | 9     |
| Identity     | 10    |
| Infra        | 15    |
| Security     | 10    |
| Data         | 9     |
| Finance      | 10    |
| Legal        | 8     |
| AI           | 7     |
| Corporate    | 5     |
| Supplemental | 9     |

## Further Resources

- **Charter files**: `hub/charters/`
- **Package definitions**: `hub/foundation/packages/` and `hub/domains/*/packages/`
- **DSL source**: `libs/canon/src/canon/dsl/`
