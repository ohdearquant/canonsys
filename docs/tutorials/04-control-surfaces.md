# Control Surface Charters

This guide covers control surface charters - the decision points where compliance requirements
must be enforced.

## What is a Control Surface?

A control surface is a **decision point** where an organization must:

1. Evaluate risk and regulatory requirements
2. Gather evidence to justify the decision
3. Obtain appropriate approvals
4. Certify the decision for audit

Examples:

- **Layoff/RIF Inclusion**: Deciding who is included in a reduction in force
- **Large Wire Transfer**: Executing high-value financial transfers
- **Break Glass Access**: Granting emergency privileged access
- **Vulnerability Exemption**: Deferring security patch application

## Control Surface Domains

| Domain       | Examples                                            |
| ------------ | --------------------------------------------------- |
| HR           | Layoff, resignation, promotion, severance           |
| Identity     | Privilege escalation, MFA exemption, break glass    |
| Infra        | Database access, failover, kubernetes bypass        |
| Security     | Vulnerability exemption, incident closure           |
| Data         | PII export, cross-border transfer, retention        |
| Finance      | Wire transfer, budget reallocation, audit waiver    |
| Legal        | Legal hold, privilege waiver, settlement            |
| AI           | Model deployment, bias waiver, human review bypass  |
| Corporate    | Due diligence, M&A integration, material disclosure |
| Supplemental | Monitoring removal, DLP disable, export control     |

## Charter Naming Convention

```
{descriptive_name}.canon
```

Examples:

- `layoff_rif.canon`
- `break_glass.canon`
- `vulnerability_exemption.canon`

## Anatomy of a Control Surface Charter

### Header with Metadata

```
charter "Vulnerability Exemption" v1.0

# SECURITY Domain - TIME_BOUNDED_EXCEPTION Archetype
# Risk Tier: HIGH
# Regulatory Basis: CISA BOD 22-01, SOC 2 CC7.1, ISO 27001 A.12.6.1, PCI-DSS 6.2
```

### Packages (Vocabulary Imports)

```
packages:
    - controls
    - evidence
    - certification
    - authorization
    - lifecycle
    - policy
    - justification
    - workflow
    - timing
```

### Triggers (External Events)

```
triggers:
    vulnerability_reported
    risk_assessment_submitted
    controls_evaluated
    business_justification_submitted
    security_review_completed
    executive_approves
    exemption_granted
    exemption_expires
```

### Workflow with Event-Driven Phases

```
workflow vulnerability_exemption:
    phase vulnerability_intake:
        await vulnerability_reported
        action check_exploitability_status()
        action create_workflow_run()
        action save_evidence()
        when exploitability == "WEAPONIZED":
            require verify_ciso_approval()
            require verify_board_approval()
        when exploitability == "KEV_LISTED":
            require verify_ciso_approval()
        evidence vulnerability_intake_record

    phase risk_assessment:
        require vulnerability_intake.passed
        await risk_assessment_submitted
        action assess_control_coverage()
        action chain_evidence()
        when severity == "CRITICAL":
            require require_dual_approval()
            require verify_executive_approval()
        when severity == "HIGH":
            require verify_ciso_approval()
        evidence risk_assessment_record
        certify hashable

    # ... more phases ...

    phase lifecycle_monitoring:
        require exemption_grant.passed
        action verify_rule_expired()
        await exemption_expires
        action verify_override_reverted()
        action emit_certificate()
        action complete_workflow_run()
        certify immutable
        evidence exemption_closure_certificate
```

### Situations (Conditional Requirements)

```
situations:
    when severity == "CRITICAL":
        waiting_period 0..14 days
        require verify_ciso_approval()
        require verify_executive_approval()

    when severity == "HIGH":
        waiting_period 0..30 days
        require verify_ciso_approval()

    when exploitability == "WEAPONIZED":
        waiting_period 0..7 days
        require verify_board_approval()

    when control_coverage == "NONE":
        require verify_executive_approval()
```

### Roles

```
roles:
    security_analyst:
        actions: [save_evidence, chain_evidence, check_exploitability_status]
        requires_mfa: true

    security_lead:
        actions: [derive_control_equivalence_score, record_workflow_step]
        requires_mfa: true

    ciso:
        actions: [verify_approval_chain_complete, emit_certificate]
        requires_mfa: true
        break_glass: true
```

## Control Surface Archetypes

### 1. TIME_BOUNDED_EXCEPTION

Temporary deviation from policy with automatic expiry.

**Characteristics:**

- `schedule_auto_revert()` action
- `enforce_expiry()` lifecycle action
- Closure phase with `verify_override_reverted()`

**Examples:** MFA Exemption, Vulnerability Exemption

### 2. EXECUTION_AUTHORIZATION

High-stakes action requiring approval chain.

**Characteristics:**

- Multi-phase approval workflow
- Dual approval for high-risk scenarios
- Evidence binding at each phase

**Examples:** Wire Transfer, Break Glass

### 3. PERMISSION_GRANT

Granting access or privileges.

**Characteristics:**

- Justification validation
- Resource owner verification
- Lifecycle management (recertification)

**Examples:** Privileged Escalation, Database Access

### 4. DISCLOSURE_DECISION

Releasing information externally.

**Characteristics:**

- Privilege review phase
- PII/confidentiality checks
- Legal approval gates

**Examples:** Regulatory Disclosure, Threat Intel Disclosure

### 5. CERTIFICATION_DECISION

Formal decision requiring immutable record.

**Characteristics:**

- Multiple attestation phases
- Hash-based evidence integrity
- Immutable certification

**Examples:** Layoff RIF, PIP Workflow

## Example: Finance Domain Charter

```
charter "Large Wire Transfer Execution" v1.0

# FINANCE Domain - EXECUTION_AUTHORIZATION Archetype
# Risk Tier: CRITICAL
# Regulatory Basis: BSA/AML, SOX 404, OFAC Sanctions

packages:
    - authorization
    - certification
    - core
    - evidence
    - freshness
    - identity
    - justification
    - pattern
    - policy
    - workflow

triggers:
    payment_requested
    fraud_screening_completed
    dual_approval_obtained
    callback_verified
    wire_executed
    confirmation_received

workflow wire_transfer_execution:
    phase request_intake:
        await payment_requested
        require verify_request_source_authenticated()
        action create_workflow_run()
        action derive_amount_band()
        when amount_band == "LARGE":
            require require_dual_approval()
        when amount_band == "SIGNIFICANT":
            require verify_cfo_approval()
            require require_dual_approval()
        evidence request_intake_record

    phase fraud_screening:
        require request_intake.passed
        await fraud_screening_completed
        action record_vendor_call()
        action chain_evidence()
        when screening_result == "FLAGGED":
            require require_sox_compliance_review()
        evidence fraud_screening_record
        certify hashable

    phase approval_collection:
        require fraud_screening.passed
        await dual_approval_obtained
        require verify_approval_chain_complete()
        action record_attestation()
        evidence approval_record

    phase callback_verification:
        require approval_collection.passed
        await callback_verified
        action verify_callback_completed()
        when recipient_new == true:
            require require_dual_approval()
        evidence callback_record

    phase execution:
        require callback_verification.passed
        await wire_executed
        require require_policy_pass("wire_transfer")
        action record_workflow_step()
        evidence execution_record

    phase certification:
        require execution.passed
        await confirmation_received
        action verify_case_integrity()
        action get_case_history()
        action emit_certificate()
        action complete_workflow_run()
        certify immutable
        evidence wire_transfer_certificate

situations:
    when amount_band == "LARGE":
        waiting_period 1..4 hours
        require require_dual_approval()

    when amount_band == "SIGNIFICANT":
        waiting_period 4..24 hours
        require verify_cfo_approval()

    when recipient_country == "HIGH_RISK":
        require require_sox_compliance_review()

    when recipient_new == true:
        require require_dual_approval()

    when quarter_end == true:
        require require_sox_compliance_review()

roles:
    payment_initiator:
        actions: [create_workflow_run, derive_amount_band]
        requires_mfa: true

    fraud_analyst:
        actions: [record_vendor_call, chain_evidence]
        requires_mfa: true

    approver:
        actions: [record_attestation]
        requires_mfa: true

    treasury_ops:
        actions: [verify_callback_completed, record_workflow_step]
        requires_mfa: true

    cfo:
        actions: [emit_certificate, complete_workflow_run]
        requires_mfa: true
        break_glass: true
```

## Best Practices

### 1. Risk-Based Escalation

Use `when` blocks to escalate approval requirements based on risk:

```
when severity == "CRITICAL":
    require require_dual_approval()
    require verify_executive_approval()
```

### 2. Evidence at Every Phase

Bind evidence to capture audit trail:

```
phase approval:
    ...
    evidence approval_record
    certify hashable
```

### 3. Lifecycle Management

For time-bounded exceptions:

```
phase grant:
    action schedule_auto_revert()
    action enforce_expiry()

phase closure:
    action verify_override_reverted()
```

### 4. Jurisdiction-Aware Situations

Handle regulatory variations:

```
situations:
    when jurisdiction == "California":
        waiting_period 7..14 days
        require require_active_consent("ca_disclosure")

    when jurisdiction == "NYC":
        require verify_ll144_compliance()
```

## Next Steps

- [Package Namespace Enforcement](./05-namespace-enforcement.md) - How packages work
- Browse actual charters in `hub/charters/surfaces/`
