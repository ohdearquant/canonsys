---
doc_type: ADR
title: "ADR-021: PII Detection with Non-Overridable Blocking Patterns"
version: "2.0.0"
status: active
created: "2026-01-15"
updated: "2026-01-29"
decision_date: "2026-01-15"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - ADR-008-policy-gates
  - ADR-006-evidence-chain-cep
successors:
  - TDS-021-privacy-pii
supersedes: null
superseded_by: null

tags:
  - privacy
  - pii
  - data-protection
  - compliance
related:
  - TDS-021-privacy-pii
  - ADR-008-policy-gates
pr: null

quality:
  confidence: 0.95
  sources: 4
  docs: full
---

# ADR-021: PII Detection with Non-Overridable Blocking Patterns

## Context

### Problem Statement

CanonSys must prevent highly sensitive personally identifiable information from being stored
inappropriately. Storage of certain PII types creates severe liability:

- **SSN storage**: Identity theft risk, regulatory violations
- **Credit card storage**: PCI DSS scope, breach liability
- **Passport storage**: International identity fraud risk

**Why This Matters**: A single breach of stored SSN or credit card data can result in class action
lawsuits, regulatory fines (GDPR up to 4% of global revenue), and reputational damage. The system
must make storage of high-risk PII structurally impossible, not merely policy-prohibited.

### Background

**Current State**: Without PII detection gates, any data field can potentially contain sensitive
information that gets persisted to the database and audit logs.

Previous systems have allowed "justified overrides" for PII blocking, leading to:

1. Override becomes default path for convenience
2. Compliance officers approve overrides without scrutiny
3. Liability exposure when stored PII is breached
4. Regulatory penalties when auditors find stored SSNs

**Driving Forces**:

- **Liability reduction**: Prevent storage of data that creates breach exposure
- **Regulatory compliance**: GDPR, CCPA, PCI DSS, SOC2 all restrict PII handling
- **Performance**: Detection must not slow down normal operations
- **Auditability**: Detection results must be usable as evidence

### Assumptions

1. Regex-based detection is sufficient for structural patterns (SSN format, credit card numbers)
2. Most data flowing through the system does not contain PII (fast-path optimization valid)
3. Legitimate business needs for SSN storage should use dedicated, highly-secured systems outside
   CanonSys

### Constraints

| Type        | Constraint                        | Impact                                                   |
| ----------- | --------------------------------- | -------------------------------------------------------- |
| Technical   | Must not increase latency > 5ms   | Requires fast-path optimization with early termination   |
| Business    | Zero tolerance for SSN/CC storage | No override mechanism can exist                          |
| Operational | Must produce audit-grade evidence | Scan results must be serializable without leaking PII    |
| Regulatory  | GDPR, PCI DSS, SOC2 compliance    | Detection categories must map to regulatory requirements |

---

## Decision

### Summary

**We will** implement a two-layer PII detection system where SSN, Credit Card, and Passport patterns
are non-overridable blocking patterns that cannot be persisted, with position-only storage in scan
results to prevent PII leakage through audit logs.

### Rationale

**Key factors in the decision**:

1. **Human factors**: Override paths become default paths over time - removing the override option
   eliminates this failure mode
2. **Liability**: Company cannot claim "we tried to prevent it" if an override mechanism exists
3. **Simplicity**: Binary enforcement is easier to audit than "sometimes blocked, sometimes allowed"

### Implementation Approach

```python
# Blocking patterns - NO EXCEPTIONS
_BLOCKING = frozenset({
    PIIPattern.SSN,
    PIIPattern.CREDIT_CARD,
    PIIPattern.PASSPORT,
})

@dataclass(frozen=True, slots=True)
class PIIMatch:
    pattern: PIIPattern
    start: int
    end: int
    # NOTE: No 'value' field - intentionally excluded to prevent PII leakage
```

**Two-Layer Architecture**:

```
Detection Layer (utils/pii.py):
  - PIIPattern enum
  - scan_for_pii() -> PIIScanResult
  - has_blocking_pii() -> bool

Enforcement Layer (enforcement/catalog/pii.py):
  - PIISafeGate
  - Integrates with gate framework
  - Position in Decision Kill Chain
```

### Alternatives Considered

#### Alternative 1: ML-Based Detection

**Description**: Use machine learning model for higher accuracy PII detection.

| Criterion       | Score (1-5) | Notes                                      |
| --------------- | ----------- | ------------------------------------------ |
| Performance     | 2           | ~100ms vs ~1ms for regex                   |
| Accuracy        | 5           | Better context-aware detection             |
| Auditability    | 2           | Non-deterministic results complicate audit |
| Maintainability | 2           | Requires model deployment/maintenance      |

**Why Not Chosen**: Performance impact too high for hot path. Regex sufficient for structural
patterns.

#### Alternative 2: Soft Enforcement with Override

**Description**: Allow override with elevated permissions and justification.

| Criterion     | Score (1-5) | Notes                                      |
| ------------- | ----------- | ------------------------------------------ |
| Flexibility   | 5           | Handles edge cases                         |
| Liability     | 1           | Creates "why did you allow override?" risk |
| Human factors | 1           | Override paths become default paths        |
| Audit clarity | 2           | Must explain every override                |

**Why Not Chosen**: Override capability creates liability and human factor risks.

#### Alternative 3: Store Hash Instead of Position

**Description**: Store hash of matched content for deduplication.

| Criterion  | Score (1-5) | Notes                                       |
| ---------- | ----------- | ------------------------------------------- |
| PII safety | 2           | Hash of SSN still sensitive (rainbow table) |
| Utility    | 3           | Same as positions for most use cases        |
| Redaction  | 1           | Hash doesn't help with redaction workflow   |

**Why Not Chosen**: Hash of SSN is still sensitive. Positions provide same utility without leakage.

### Decision Matrix

| Criterion          | Weight | ML-Based | Override | Hash    | Chosen (Regex+Block) |
| ------------------ | ------ | -------- | -------- | ------- | -------------------- |
| Performance        | 30%    | 2        | 4        | 4       | 5                    |
| Liability          | 30%    | 3        | 1        | 3       | 5                    |
| Audit clarity      | 20%    | 2        | 2        | 3       | 5                    |
| Maintainability    | 20%    | 2        | 3        | 4       | 4                    |
| **Weighted Total** | 100%   | **2.2**  | **2.3**  | **3.5** | **4.8**              |

---

## Consequences

### Positive Consequences

1. **Zero storage risk**: Blocking patterns structurally cannot persist - not a policy violation,
   but a system constraint
2. **Audit-ready**: Scan results are evidence-grade (position-only, no PII leakage)
3. **Performance**: Fast path keeps normal operations quick (O(n) with early termination)
4. **Clarity**: Binary enforcement is unambiguous for developers and auditors

### Negative Consequences

1. **Rigidity**: Legitimate blocking pattern storage requires separate system
   - **Mitigation**: Tax reporting systems that need SSN should be dedicated, highly-secured systems
2. **False positives**: Regex may flag phone numbers as SSN-like
   - **Mitigation**: Pattern tuning; future context-aware detection for edge cases
3. **US-centric**: Current patterns are US-focused
   - **Mitigation**: Extend to EU VAT, UK NI, Canadian SIN in future versions

### Neutral Consequences

1. **Two-layer separation**: Detection utilities are reusable across contexts, but adds
   architectural complexity

### Risks

| Risk                         | Likelihood | Impact | Mitigation                                    |
| ---------------------------- | ---------- | ------ | --------------------------------------------- |
| False positive rate too high | M          | M      | Pattern tuning, allowlist for known safe data |
| Regex bypass via encoding    | L          | H      | Normalize text before scanning                |
| Performance regression       | L          | M      | Benchmark gates, monitor latency              |

### Dependencies Introduced

| Dependency | Type   | Version | Stability | Notes                         |
| ---------- | ------ | ------- | --------- | ----------------------------- |
| `re`       | stdlib | N/A     | Stable    | Python standard library regex |

### Migration Impact

**Backwards Compatibility**: Breaking for any code that stored PII in evidence/audit records

**Migration Steps**:

1. Audit existing evidence records for PII
2. Deploy PIISafeGate in monitoring mode (log, don't block)
3. Review alerts for false positives
4. Switch to blocking mode

**Rollback Plan**:

1. Disable PIISafeGate via feature flag
2. Review blocked operations manually

---

## Verification

### Success Criteria

- [ ] Zero SSN/CC/Passport values stored in evidence or audit tables
- [ ] PIISafeGate latency < 5ms at p99
- [ ] 100% coverage of blocking pattern detection in tests
- [ ] False positive rate < 1% on production data sample

### Metrics to Track

| Metric                    | Baseline | Target | Review Date |
| ------------------------- | -------- | ------ | ----------- |
| PIISafeGate latency (p99) | N/A      | < 5ms  | 2026-02-15  |
| False positive rate       | N/A      | < 1%   | 2026-02-15  |
| Blocked operations/day    | N/A      | < 10   | 2026-02-15  |

### Review Schedule

- **Initial Review**: 2026-02-15 (30 days after activation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: alpha[architect]

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate protocol and Decision Kill Chain positioning
- `ADR-006-evidence-chain-cep`: Evidence structure for audit trails

### Impacts

- `TDS-021-privacy-pii`: Technical implementation specification
- All services that persist user-provided text data

---

## Vocabulary Mapping

### Package Reference

**Primary Package**: `hub/domains/governance/packages/data_protection/`

### Vocabulary Phrases

| Phrase                           | Pattern | Regulatory Basis    |
| -------------------------------- | ------- | ------------------- |
| `require_pii_classification`     | require | GDPR Art. 32, SOC2  |
| `require_encrypted_transmission` | require | GDPR Art. 32, HIPAA |
| `verify_data_minimization`       | verify  | GDPR Art. 5(1)(c)   |

### Control Surfaces

| Surface                  | Key Integration                                         |
| ------------------------ | ------------------------------------------------------- |
| PII Export Authorization | PIISafeGate validates minimization_verified fact        |
| Cross-Border Transfer    | PII scanning determines data sensitivity                |
| Anonymization Exemption  | PII detection identifies fields requiring anonymization |

---

## References

- TDS: `docs-shared/canonsys/01_design/021-privacy-pii/TDS-021-privacy-pii.md`
- Detection: `libs/canon/src/canon/utils/pii.py`
- Gate: `libs/canon/src/canon/enforcement/catalog/pii.py`
- GDPR Article 87: National identification numbers
- PCI DSS Requirement 3: Protect stored cardholder data
- CCPA Section 1798.140: Definition of personal information
