# Canon Vocab: Authorization

Access control, role-based approval chains, dual approval, delegation, time-bounded access, and segregation of duties.

## Import

```python
from canon_vocab_authorization import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_access_justification`
- `require_distinct_identities`
- `require_dual_approval`
- `require_release_clearance`
- `require_role_authorized`
- `require_segregation_analysis`
- `require_separation_of_duties`
- `require_time_bounded_access`

### Verify

- `verify_approval_chain_complete`
- `verify_board_approval`
- `verify_cfo_approval`
- `verify_ciso_approval`
- `verify_compliance_approval`
- `verify_cto_approval`
- `verify_delegation_valid`
- `verify_dpo_approval`
- `verify_executive_approval`
- `verify_gc_approval`
- `verify_hr_approval`
- `verify_role_approval`

### Action

- `check_er_clearance`
- `get_approval_chain`


## Types

- `ApprovalChainStatus`
- `ApproverStatus`
- `ClearanceLevel`
- `ERClearanceResult`
- `ERClearanceStatus`
- `RequireDistinctIdentitiesResult`
- `RequireDualApprovalResult`
- `RequireSegregationAnalysisResult`
- `RoleApprovalResult`
- `SegregationStatus`
- `VerifyApprovalChainCompleteResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_authorization import verify_approval_chain_complete

# Use in a Canon workflow
result = await verify_approval_chain_complete(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
