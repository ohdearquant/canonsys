---
doc_type: mapping
title: "ADR-023 Waiting Period - Code Mapping"
version: "2.0.0"
updated: "2026-01-29"
adr: ADR-023-waiting-period
tds: TDS-023-waiting-period
---

# 023-waiting-period - Code Mapping

## Vocabulary Package Reference

**Primary Packages**:

- `hub/foundation/packages/timing/`
- `hub/domains/governance/packages/notice/`

### Vocabulary Phrases

| Phrase                    | Pattern | Location  | Regulatory Basis       |
| ------------------------- | ------- | --------- | ---------------------- |
| `check_waiting_period`    | check   | `timing/` | FCRA Section 604(b)(3) |
| `verify_notice_delivered` | verify  | `notice/` | FCRA Section 1681m     |
| `derive_notice_required`  | derive  | `notice/` | State-specific rules   |

### Control Surface Bindings

| Surface                       | Phrase Integration                           |
| ----------------------------- | -------------------------------------------- |
| Layoff RIF Inclusion          | WARN Act 60-day notice via WaitingPeriodGate |
| Severance Calculation         | State-specific notice periods                |
| Severance Agreement Execution | OWBPA 21/45-day periods via Calendar         |

### Charter Reference

**Charter**: `fcra_adverse_action.canon`

---

## Primary Code Paths

- `libs/canon/src/canon/enforcement/catalog/waiting_period.py` - WaitingPeriodGate implementation
- `libs/canon/src/canon/utils/calendar.py` - Business day calculations with Calendar class
- `libs/canon/src/canon/utils/loader.py` - JurisdictionRegistry with holidays
- `libs/canon/src/canon/entities/policy/definition.py` - PolicyDefinition.waiting_periods field

## Key Classes/Functions

### Enforcement Gate (enforcement/catalog/waiting_period.py)

- **WaitingPeriodGate** (`waiting_period.py:L9-L56`) - Parameterized gate enforcing mandatory
  waiting periods:
  - **Parameters**: event_type, required_days, reference_time
  - **Dynamic gate_id**: `waiting_period.{event_type}`
  - **Failure reason**: "Mandatory {N} day waiting period has not elapsed"
  - **TODO**: Calendar service integration not yet implemented (placeholder in check())

### Calendar Utilities (utils/calendar.py)

- **Calendar** (`calendar.py:L41-L126`) - Business day calculator:
  - **add()**: Add N business days (positive or negative)
  - **add_audited()**: Same as add() but returns DeadlineRecord for audit trail
  - **count()**: Count business days in range [start, end)
  - **is_business_day()**: Check if date is business day
  - **holidays()**: Get holidays for jurisdiction and year

- **DeadlineRecord** (`calendar.py:L20-L39`) - Frozen dataclass for audit:
  - start, days, result dates
  - jurisdiction code
  - holidays_skipped (for evidence)
  - calculated_at timestamp
  - rule_id for linking to policy

### Jurisdiction Loader (utils/loader.py)

- **JurisdictionRegistry** (`loader.py:L48-L164`) - Registry of jurisdiction configs:
  - **get()**: Get jurisdiction config by code
  - **normalize_required()**: Normalize code to canonical form
  - **hierarchy()**: Get jurisdiction hierarchy (most-specific-first)
  - **get_holidays()**: Get observed holidays for jurisdiction and year (cached)

## Architectural Patterns

- **Event-Type Parameterization**: WaitingPeriodGate parameterized by event_type (e.g.,
  "adverse_action_notice"). Single gate class, multiple event types.

- **Business Days, Not Calendar Days**: Calendar.add() skips weekends AND jurisdiction-specific
  holidays. Critical for regulatory compliance.

- **Audit Trail**: DeadlineRecord captures WHICH holidays were skipped. This proves calculation was
  correct at time of evaluation.

- **Jurisdiction-Aware**: Calendar requires JurisdictionRegistry to look up holidays. Different
  jurisdictions have different holidays.

- **Bidirectional Calculation**: Calendar.add() supports negative days for backward calculation.
  Useful for "what was the deadline 5 days before?"

- **Policy Integration**: PolicyDefinition.waiting_periods stores event_type -> duration mappings
  (e.g., {'PRE_ADVERSE_NOTICE': '3_BUSINESS_DAYS'}).

## Dependencies

- **Depends on**:
  - `canon.enforcement.vocabulary` - Vocabulary-based enforcement (verify_*/require_* phrases)
  - `kron.specs.phrase.PhraseResult` - Phrase result structure
  - `canon.utils.loader.JurisdictionRegistry` - Holiday and jurisdiction data
  - `canon.enforcement.types.RequestContext` - Context for gate evaluation

- **Depended by**:
  - FCRA adverse action workflows - Require waiting periods before final action
  - NYC Fair Chance Act - Pre-adverse action notice periods
  - Any timed compliance requirements

## Key Decisions (for ADR candidates)

1. **Business days are mandatory**: Regulatory waiting periods are in business days, not calendar
   days. No shortcut to calendar days.

2. **Holiday evidence preservation**: DeadlineRecord.holidays_skipped proves calculation correctness
   even if holiday data changes later.

3. **Reference time is required**: Gate blocks if no reference_time provided. Cannot evaluate
   waiting period without knowing when period started.

4. **Jurisdiction-specific holidays**: Calendar uses JurisdictionRegistry, not hardcoded holidays.
   Holidays vary by location.

5. **Placeholder implementation**: WaitingPeriodGate.check() is a placeholder. TODO comment
   indicates calendar service integration needed.

## Open Questions

- How is reference_time populated? Should gate look up "when was notice sent" from Evidence?
- Cross-timezone handling: If notice sent in NYC but applicant in LA, which timezone applies?
- Holiday update handling: If holidays are updated after calculation, should we recalculate?
- Partial day handling: If notice sent at 11pm, does that day count?
- Weekend-adjacent handling: If required period ends on Monday and it's a holiday, extend to
  Tuesday?
