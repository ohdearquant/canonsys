# Finance Surface → Vocabulary Mapping

**Date**: 2026-01-20 **Purpose**: Map Finance surfaces to vocabulary functions
for derived fact computation.

---

## Overview

Finance surfaces require anti-gaming derived facts. This document maps each surface's derived facts
to the vocabulary functions that must be called before policy evaluation.

---

## Vocabulary Functions Available

| Function                   | Module                                        | Purpose                                      |
| -------------------------- | --------------------------------------------- | -------------------------------------------- |
| `derive_amount_band`       | `features.core.actions.primitives`            | Amount → MINOR/MODERATE/MATERIAL/SIGNIFICANT |
| `derive_cumulative_amount` | `features.pattern.actions.cumulative`         | Sum historical amounts for pattern detection |
| `check_pattern_threshold`  | `features.pattern.actions.detection`          | Check if count exceeds threshold             |
| `verify_cfo_approval`      | `features.authorization.actions.verification` | CFO approval verification                    |
| `verify_board_approval`    | `features.authorization.actions.verification` | Board approval verification                  |

---

## Surface Mappings

### BUDGET_REALLOCATION

| Derived Fact                     | Vocabulary Function              | Input Facts                                         | Config                                                        |
| -------------------------------- | -------------------------------- | --------------------------------------------------- | ------------------------------------------------------------- |
| `amount_band`                    | `derive_amount_band`             | `reallocation_amount`                               | `minor_threshold`, `moderate_threshold`, `material_threshold` |
| `cumulative_reallocation_amount` | `derive_cumulative_amount`       | `entity_id`, `metric="reallocation"`, `period_days` | -                                                             |
| `approval_chain_complete`        | `verify_approval_chain_complete` | `workflow_record_id`                                | `required_roles`                                              |

### VENDOR_PAYMENT_OVERRIDE

| Derived Fact         | Vocabulary Function         | Input Facts                                              | Config     |
| -------------------- | --------------------------- | -------------------------------------------------------- | ---------- |
| `amount_band`        | `derive_amount_band`        | `payment_amount`                                         | thresholds |
| `override_count_30d` | `derive_prior_action_count` | `vendor_id`, `action_type="payment_override"`, `days=30` | -          |

### EXPENSE_POLICY_EXCEPTION

| Derived Fact                  | Vocabulary Function         | Input Facts                                                | Config     |
| ----------------------------- | --------------------------- | ---------------------------------------------------------- | ---------- |
| `amount_band`                 | `derive_amount_band`        | `expense_amount`                                           | thresholds |
| `overage_percentage`          | `derive_overage_percentage` | `expense_amount`, `policy_limit`                           | -          |
| `cumulative_exception_amount` | `derive_cumulative_amount`  | `employee_id`, `metric="expense_exception"`, `period_days` | -          |

### REVENUE_RECOGNITION_OVERRIDE

| Derived Fact               | Vocabulary Function         | Input Facts                                             | Config     |
| -------------------------- | --------------------------- | ------------------------------------------------------- | ---------- |
| `amount_band`              | `derive_amount_band`        | `revenue_amount`                                        | thresholds |
| `quarter_end_proximity`    | `derive_quarter_end`        | `effective_date`                                        | -          |
| `prior_overrides_contract` | `derive_prior_action_count` | `contract_id`, `action_type="revenue_override"`, `days` | -          |

### INTERCOMPANY_TRANSFER

| Derived Fact                | Vocabulary Function         | Input Facts                                                       | Config     |
| --------------------------- | --------------------------- | ----------------------------------------------------------------- | ---------- |
| `amount_band`               | `derive_amount_band`        | `transfer_amount`                                                 | thresholds |
| `prior_transfers_same_pair` | `derive_prior_action_count` | `entity_pair_hash`, `action_type="intercompany_transfer"`, `days` | -          |

### TAX_JURISDICTION_CHANGE

| Derived Fact                 | Vocabulary Function         | Input Facts                                                | Config     |
| ---------------------------- | --------------------------- | ---------------------------------------------------------- | ---------- |
| `amount_band`                | `derive_amount_band`        | `impact_amount`                                            | thresholds |
| `prior_jurisdiction_changes` | `derive_prior_action_count` | `entity_id`, `action_type="jurisdiction_change"`, `months` | -          |

### FINANCIAL_AUDIT_WAIVER

| Derived Fact          | Vocabulary Function      | Input Facts          | Config     |
| --------------------- | ------------------------ | -------------------- | ---------- |
| `amount_band`         | `derive_amount_band`     | `waiver_scope_value` | thresholds |
| `justification_class` | `classify_justification` | `waiver_reason`      | -          |

### CREDIT_LIMIT_OVERRIDE

| Derived Fact              | Vocabulary Function       | Input Facts                        | Config |
| ------------------------- | ------------------------- | ---------------------------------- | ------ |
| `overage_amount`          | `derive_overage_amount`   | `requested_limit`, `current_limit` | -      |
| `credit_assessment_fresh` | `verify_credit_freshness` | `assessment_date`, `max_age_days`  | -      |

### TREASURY_POSITION_CHANGE

| Derived Fact            | Vocabulary Function  | Input Facts              | Config     |
| ----------------------- | -------------------- | ------------------------ | ---------- |
| `amount_band`           | `derive_amount_band` | `position_change_amount` | thresholds |
| `quarter_end_proximity` | `derive_quarter_end` | `effective_date`         | -          |

---

## Service Layer Implementation Pattern

```python
from canon.features.core.actions.primitives import derive_amount_band
from canon.features.pattern.actions.cumulative import derive_cumulative_amount
from canon.features.charter.actions.evaluate_decision import evaluate_decision

async def process_budget_reallocation(
    charter_id: UUID,
    raw_facts: dict,
    ctx: RequestContext,
) -> DecisionResult:
    # Step 1: Derive facts using vocabulary
    amount_band_result = await derive_amount_band(
        amount=raw_facts["reallocation_amount"],
        ctx=ctx,
        config=AmountBandConfig(
            bands=[
                ("MINOR", Decimal(0)),
                ("MODERATE", Decimal(25000)),
                ("MATERIAL", Decimal(100000)),
                ("SIGNIFICANT", Decimal(500000)),
            ]
        ),
    )

    cumulative_result = await derive_cumulative_amount(
        entity_id=raw_facts["source_category_id"],
        metric="reallocation",
        period_days=365,
        ctx=ctx,
    )

    # Step 2: Combine raw + derived facts
    all_facts = {
        **raw_facts,
        "amount_band": amount_band_result.band,
        "cumulative_reallocation_amount": cumulative_result.cumulative_amount,
    }

    # Step 3: Evaluate against charter policy
    result = await evaluate_decision(
        charter_id=charter_id,
        surface_id="this surface",
        facts=all_facts,
        ctx=ctx,
    )

    return result
```

---

## Status

| Surface | Vocabulary Mapping | Functions Available                      | Wiring Status   |
| ------- | ------------------ | ---------------------------------------- | --------------- |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | PARTIAL (classify_justification missing) | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |
| this surface  | COMPLETE           | YES                                      | SERVICE_PENDING |

---

_Generated by λ:canonsys | 2026-01-20_
