# Canon Vocab: Consent

Consent collection, verification, revocation, renewal, and audit history.

## Import

```python
from canon_vocab_consent import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_active_consent`
- `require_consent_not_expired`
- `require_consent_not_withdrawn`
- `require_valid_consent`

### Verify

- `verify_consent_scope_covers`
- `verify_consent_token`

### Action

- `cascade_revoke_consent_token`
- `find_consent_token`
- `grant_consent_token`
- `list_consent_tokens`
- `renew_consent_token`
- `revoke_consent_token`
- `get_consent_history`
- `consent_must_be_valid`
- `consent_must_not_be_expired`
- `consent_must_not_be_withdrawn`
- `consent_scope_must_cover`


## Types

- `ConsentScope`
- `ConsentStatus`
- `ConsentToken`
- `ConsentTokenContent`
- `ConsentStatusFilter`
- `ConsentHistoryEntry`
- `CascadeRevokeSpecs`
- `FindConsentSpecs`
- `GetConsentHistorySpecs`
- `GrantConsentSpecs`
- `ListConsentSpecs`
- `RenewConsentSpecs`
- `RequireActiveConsentSpecs`
- `RequireConsentNotExpiredSpecs`
- `RequireConsentNotWithdrawnSpecs`
- `RequireValidConsentSpecs`
- `RevokeConsentSpecs`
- `VerifyConsentScopeCoversSpecs`
- `VerifyConsentSpecs`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_consent import verify_consent_scope_covers

# Use in a Canon workflow
result = await verify_consent_scope_covers(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
