# Event-Driven Workflows

This guide covers triggers and await statements for event-driven charter workflows.

## Why Event-Driven?

Traditional workflows assume phases execute immediately in sequence. Real compliance workflows
require **waiting for external events**:

- Manager approval received
- Waiting period elapsed
- Employee acknowledged plan
- Incident resolved

The Charter DSL supports this with **triggers** and **await** statements.

## Triggers

Triggers declare external events that the workflow can wait for:

```
charter "Performance Improvement Plan" v1.0

triggers:
    manager_initiates_pip
    employee_acknowledges_plan
    midpoint_review_scheduled
    final_review_completed
    hr_certifies_outcome

workflow pip_workflow:
    phase initiation:
        await manager_initiates_pip        # Block until event fires
        require require_subject_exists()
        action create_workflow_run()
        evidence initiation_record
```

### Trigger Naming Convention

Use descriptive names following these patterns:

- `{actor}_{action}` - `manager_approves`, `employee_signs`
- `{event}_{state}` - `review_completed`, `period_expired`
- `{resource}_{lifecycle}` - `access_granted`, `access_expires`

## Await Statements

`await` blocks a phase until an external event fires:

```
phase employee_acknowledgment:
    require initiation.passed
    await employee_acknowledges_plan       # Wait for employee action
    require verify_acknowledgment_captured()
    action record_acknowledgment()
    evidence acknowledgment_record
```

### Await at Phase Start

The most common pattern - wait for an event before phase begins:

```
phase approval:
    await approval_requested               # Entry gate
    require verify_request_valid()
    action process_approval()
```

### Multiple Phases Awaiting Different Events

```
phase manual_closure:
    require monitoring.passed
    await incident_resolved                # Manual resolution
    action verify_containment()

phase auto_closure:
    require monitoring.passed
    await auto_close_triggered             # Automatic timeout
    action verify_override_reverted()
```

## Inline When Blocks with Await

Conditional await based on context:

```
phase closure:
    require monitoring.passed
    when closure_type == "AUTO":
        await auto_close_triggered
        action verify_override_reverted()
    when closure_type == "MANUAL":
        await incident_resolved
        require require_containment_verified()
    action emit_certificate()
    certify immutable
    evidence closure_certificate
```

## Complete Event-Driven Example

```
charter "Break Glass Activation" v1.0

packages:
    - identity
    - authorization
    - certification
    - incident
    - pattern
    - lifecycle
    - policy

triggers:
    emergency_declared
    activator_requests_access
    witness_attests
    access_granted
    incident_resolved
    auto_close_triggered

workflow break_glass_activation:
    phase emergency_declaration:
        await emergency_declared
        require require_incident_declared()
        require verify_request_source_authenticated()
        action save_evidence()
        evidence emergency_declaration_record

    phase activator_verification:
        require emergency_declaration.passed
        await activator_requests_access
        require verify_strong_auth_posture()
        action check_prior_bypasses()
        when prior_bypasses_30d > 3:
            require require_dual_approval()
            action escalate_frequent_usage()
        evidence activator_verification_record

    phase witness_attestation:
        require activator_verification.passed
        await witness_attests
        require require_distinct_identities()
        action record_attestation()
        when access_scope == "CLUSTER":
            require require_dual_approval()
        when access_scope == "DATACENTER":
            require require_dual_approval()
            action notify_incident_commander()
        evidence witness_attestation_record
        certify hashable

    phase access_grant:
        require witness_attestation.passed
        require require_policy_pass("break_glass")
        action invoke_break_glass()
        action schedule_auto_revert()
        evidence access_grant_record

    phase monitoring:
        require access_grant.passed
        await access_granted
        action derive_prior_action_count()
        action trigger_recertification()
        evidence monitoring_record

    phase closure:
        require monitoring.passed
        when closure_type == "AUTO":
            await auto_close_triggered
            action verify_override_reverted()
        when closure_type == "MANUAL":
            await incident_resolved
            require require_containment_verified()
        action verify_case_integrity()
        action emit_certificate()
        certify immutable
        evidence break_glass_certificate

situations:
    when access_scope == "CLUSTER":
        require require_dual_approval()

    when access_scope == "DATACENTER":
        require require_dual_approval()

    when systems_affected == "ALL_CRITICAL":
        require require_dual_approval()

roles:
    activator:
        actions: [save_evidence, invoke_break_glass]
        requires_mfa: true

    witness:
        actions: [record_attestation]
        requires_mfa: true

    security_analyst:
        actions: [check_prior_bypasses, escalate_frequent_usage]
        requires_mfa: true

    incident_commander:
        actions: [notify_incident_commander, emit_certificate]
        break_glass: true
```

## Event Flow Visualization

```
emergency_declared
       │
       ▼
┌─────────────────────┐
│ emergency_declaration│
└──────────┬──────────┘
           │
activator_requests_access
           │
           ▼
┌─────────────────────┐
│ activator_verification│
└──────────┬──────────┘
           │
witness_attests
           │
           ▼
┌─────────────────────┐
│ witness_attestation │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    access_grant     │
└──────────┬──────────┘
           │
access_granted
           │
           ▼
┌─────────────────────┐
│     monitoring      │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
auto_close   incident_resolved
     │           │
     └─────┬─────┘
           │
           ▼
┌─────────────────────┐
│      closure        │
└─────────────────────┘
```

## Best Practices

1. **Declare all triggers** - Every `await` must reference a declared trigger
2. **Use descriptive names** - `manager_approves_escalation` not `event1`
3. **Consider timeouts** - Use `auto_close_triggered` for time-bounded operations
4. **Conditional await** - Use `when` blocks for branching event paths
5. **Evidence at each phase** - Capture state for audit trail

## Next Steps

- [Writing Vocabulary Phrases](./03-writing-phrases.md) - Create the phrases your charters use
- [Control Surface Charters](./04-control-surfaces.md) - See real-world examples
