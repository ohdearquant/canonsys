# Charter DSL Basics

This guide introduces the Charter DSL - a declarative language for defining compliance workflows.

## What is a Charter?

A charter is a **declarative compliance workflow specification** that compiles to a validated DAG
(Directed Acyclic Graph). Charters define:

- **Phases** - Sequential steps in a workflow
- **Requirements** - Gates that must pass before proceeding
- **Actions** - Operations performed within phases
- **Situations** - Conditional requirements based on context
- **Roles** - Who can perform which actions

## Minimal Charter Example

```
charter "Simple Approval" v1.0

packages:
    - authorization
    - certification

workflow simple_approval:
    phase request:
        require require_subject_exists()
        action save_evidence()
        evidence request_record

    phase approval:
        require request.passed
        require require_manager_approved()
        action collect_manager_approval()
        evidence approval_record

    phase certification:
        require approval.passed
        action emit_certificate()
        certify immutable
        evidence approval_certificate

roles:
    requester:
        actions: [save_evidence]
        requires_mfa: true

    manager:
        actions: [collect_manager_approval]
        requires_mfa: true

    certifier:
        actions: [emit_certificate]
        requires_mfa: true
```

## Charter Structure

### Header

```
charter "Charter Name" v1.0
```

Every charter starts with a name and version.

### Packages Section

```
packages:
    - authorization
    - certification
    - consent
```

Lists vocabulary packages that provide the phrases used in the charter. **Namespace enforcement**
ensures all phrases come from declared packages.

### Workflow Section

```
workflow workflow_name:
    phase phase_name:
        require ...
        action ...
        evidence evidence_name
```

Defines the phases of your workflow. Phases execute in dependency order.

### Phase Dependencies

```
phase approval:
    require request.passed    # Wait for request phase to pass
```

Use `phase_name.passed` to create dependencies between phases.

### Situations Section

```
situations:
    when jurisdiction == "California":
        waiting_period 7..14 days
        require require_active_consent("ca_disclosure")

    when risk_tier == "HIGH":
        require require_dual_approval()
```

Conditional requirements based on runtime context.

### Roles Section

```
roles:
    manager:
        actions: [collect_approval, sign_off]
        requires_mfa: true

    executive:
        actions: [override_decision]
        break_glass: true
```

Defines who can perform actions. `break_glass: true` enables emergency override.

## Compiling Charters

```python
from canon.hub.hub import build_hub

hub = build_hub()
compiled = hub.compile(charter_source)

print(compiled.name)                    # "Simple Approval"
print(compiled.phase_order)             # {'simple_approval': ('request', 'approval', 'certification')}
print(compiled.feature_names)           # frozenset({'require_subject_exists', ...})
```

## Common Patterns

### Gate Pattern (require)

```
require require_manager_approved()     # Must return satisfied=True
require verify_consent_token()         # Must return verified=True
```

Gates block phase progression if they fail.

### Action Pattern

```
action save_evidence()
action collect_manager_approval()
action emit_certificate()
```

Actions perform operations and may record evidence.

### Evidence Binding

```
phase approval:
    ...
    evidence approval_record           # Bind evidence type to phase
```

### Certification

```
certify hashable    # Evidence can be hashed for audit
certify immutable   # Evidence cannot be modified
```

## Next Steps

- [Event-Driven Workflows](./02-event-driven-workflows.md) - Add triggers and await
- [Writing Vocabulary Phrases](./03-writing-phrases.md) - Create custom phrases
- [Control Surface Charters](./04-control-surfaces.md) - Real-world examples
