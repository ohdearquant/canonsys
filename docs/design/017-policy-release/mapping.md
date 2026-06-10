# 017-Policy-Release - Code Mapping

## Vocabulary Packages

| Package   | Path                                             | Key Phrases                                                        |
| --------- | ------------------------------------------------ | ------------------------------------------------------------------ |
| `policy`  | `hub/foundation/packages/policy/`  | create_release, publish_release, create_definition, create_adapter |
| `charter` | `hub/foundation/packages/charter/` | activate_charter, create_charter                                   |
| `core`    | `hub/foundation/packages/core/`    | ratify_charter                                                     |

## Phrase Locations

### Policy Package

| Phrase                           | File                                        | Purpose                                 |
| -------------------------------- | ------------------------------------------- | --------------------------------------- |
| `create_policy_release`          | `phrases/create_release.py`                 | Create draft release with version       |
| `publish_policy_release`         | `phrases/publish_release.py`                | Freeze content, transition to published |
| `create_policy_definition`       | `phrases/create_definition.py`              | Legal-authored policy specification     |
| `create_policy_adapter`          | `phrases/create_adapter.py`                 | Engineering implementation              |
| `require_policy_active`          | `phrases/require_policy_active.py`          | Gate: policy must be active             |
| `require_policy_version_current` | `phrases/require_policy_version_current.py` | Gate: version lock validation           |
| `evaluate_policy`                | `phrases/evaluate_policy.py`                | Evaluate policy against data            |
| `resolve_policy`                 | `phrases/resolve_policy.py`                 | Resolve policy by ID                    |

### Charter Package

| Phrase              | File                           | Purpose                           |
| ------------------- | ------------------------------ | --------------------------------- |
| `activate_charter`  | `phrases/activate_charter.py`  | DRAFT -> ACTIVE transition        |
| `create_charter`    | `phrases/create_charter.py`    | Create draft charter              |
| `bind_surface`      | `phrases/bind_surface.py`      | Bind control surface to charter   |
| `evaluate_decision` | `phrases/evaluate_decision.py` | Evaluate decision against charter |

### Core Package

| Phrase           | File                        | Purpose                                   |
| ---------------- | --------------------------- | ----------------------------------------- |
| `ratify_charter` | `phrases/ratify_charter.py` | Record signatories with ratification_hash |

## Core Entity Locations

| Entity             | File                         | Purpose                             |
| ------------------ | ---------------------------- | ----------------------------------- |
| `PolicyRelease`    | `libs/canon/src/canon/entities/policy/release.py`  | Immutable policy library release    |
| `PolicyDefinition` | `libs/canon/src/canon/entities/policy/definition.py`  | Legal-authored policy specification |
| `PolicyAdapter`    | `libs/canon/src/canon/entities/policy/adapter.py`  | Engineering implementation          |
| `Charter`          | `libs/canon/src/canon/entities/charter/charter.py` | Tenant-scoped governance document   |

## Key Architectural Patterns

### Two-Key Model

Neither Legal nor Engineering can unilaterally modify enforcement:

- **Key 1**: `PolicyDefinition` - Legal owns WHAT to enforce
- **Key 2**: `PolicyAdapter` - Engineering owns HOW to enforce

Version lock enforced by `require_policy_version_current` phrase.

### Immutable After Publish

`publish_policy_release` freezes content permanently. Changes require new release version.

### Charter Activation

`activate_charter` phrase handles:

- Status transition (DRAFT -> ACTIVE)
- Retiring previous active charter
- Recording effective date

### Ratification Hash

`ratify_charter` computes cryptographic hash over:

- charter_id
- content_hash
- signatories
- ratified_at timestamp

## Dependencies

**Depends on:**

- `canon.entities.entity.Entity, ContentModel` - Base class with content_hash
- `kron.utils.compute_hash` - For ratification_hash
- `canon.db` - CRUD operations

**Depended by:**

- `canon.enforcement.types.RequestContext` - Receives policies from release
- `canon.utils.opa.engine.PolicyEngine` - Evaluates policies from release bundle
