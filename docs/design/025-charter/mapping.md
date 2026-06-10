---
doc_type: mapping
title: "ADR-025 Charter - Code Mapping"
version: "2.0.0"
updated: "2026-01-29"
adr: ADR-025-charter
tds: TDS-025-charter
---

# 025-charter - Code Mapping

## Vocabulary Package Reference

**Primary Package**: `hub/foundation/packages/charter/`

### Vocabulary Phrases

| Phrase              | Pattern | Location   | Regulatory Basis                |
| ------------------- | ------- | ---------- | ------------------------------- |
| `create_charter`    | action  | `charter/` | SOX 302/404 governance          |
| `activate_charter`  | action  | `charter/` | SOC 2 CC1.1 control environment |
| `ratify_charter`    | action  | `charter/` | Corporate governance            |
| `bind_surface`      | action  | `charter/` | Control surface activation      |
| `evaluate_decision` | action  | `charter/` | SOX 404 decision audit          |

### Control Surface Bindings

Charter is the **foundational governance layer**. Every surface operates within Charter boundaries:

| Surface                        | Description                | Phrase Integration                            |
| ------------------------------ | -------------------------- | --------------------------------------------- |
| All                            | Tenant Governance          | Charter.policy_ids determines active policies |
| Layoff RIF Inclusion           | Layoff RIF Inclusion       | Charter.roles defines HR/Legal requirements   |
| Privileged Role Escalation     | Privileged Role Escalation | Charter.roles.permitted_actions               |
| Break Glass Activation         | Break Glass Activation     | Charter.roles.break_glass_authority           |
| PII Export Authorization       | PII Export Authorization   | Charter.constraints bind DPO review           |
| Settlement Authority           | Settlement Authority       | Charter defines signatory requirements        |

---

## Primary Code Paths

- `libs/canon/src/canon/entities/charter/charter.py` - Charter entity and supporting types
- `hub/foundation/packages/core/types/charter.py` - Charter types (if using features structure)
- `hub/foundation/packages/core/actions/charter.py` - Charter-related actions

## Key Classes/Functions

### Charter Entity

- **CharterContent** - Tenant-scoped governance document content model:
  - **Identity**: tenant_id (FK[Tenant]), version (semantic versioning)
  - **Policy Selection**: policy_release_id, policy_ids (selected from release)
  - **Role Governance**: roles (list of RoleDefinition dicts)
  - **Constraints**: constraints (list of CharterConstraint dicts)
  - **Lifecycle**: status (draft/ratified/active/superseded), effective_from, superseded_at,
    superseded_by_id
  - **Ratification**: ratified_by, ratified_at, ratification_hash

- **Charter** - Entity created via `create_entity("Charter", CharterContent, table_name="charters")`

- **Key Methods**:
  - `compute_ratification_hash()` - SHA256 over ratifiable content
  - `ratify(signatories)` - Record signatories, compute hash, set status=ratified
  - `activate(effective_from)` - Set effective date, status=active (requires ratification)
  - `supersede(replacement_id)` - Mark superseded by newer charter
  - `is_effective(as_of)` - Check if currently effective
  - `is_ratified()` - Check ratification requirements

### Supporting Types

- **Signatory** - Frozen dataclass for ratification record:
  - name, title, organization, signed_at, signature_hash
  - `to_dict()` for serialization

- **RoleDefinition** - Role-based permission:
  - role_id, name, permitted_actions (tuple)
  - break_glass_authority (bool), requires_mfa (bool)
  - `to_dict()` for serialization

- **CharterConstraint** - Enforceable constraint:
  - constraint_id, description
  - **Enforcement binding**: gate_id OR service_check (one must be set)
  - `__post_init__()` validates enforcement binding exists
  - `to_dict()` for serialization

## Architectural Patterns

- **Single Active Charter**: Each tenant has exactly one active Charter at any time. Version changes
  create new records.

- **Immutable After Ratification**: Once ratified, Charter cannot be modified. Changes require new
  version and re-ratification.

- **Two-Phase Activation**: DRAFT -> RATIFIED (requires signatories) -> ACTIVE. No direct
  draft-to-active.

- **Ratification Hash**: Hash computed over all ratifiable content (tenant_id, version, policy_ids,
  roles, constraints, signatories). Tamper evidence.

- **Constraint Enforcement Binding**: Every CharterConstraint MUST reference gate_id or
  service_check. "If there's no code enforcing it, it doesn't belong here." Validated at
  construction time via `__post_init__`.

- **Role-Permission Model**: RoleDefinition defines permitted_actions per role. Charter is the
  single source for "who can do what".

- **Break-Glass Authority**: RoleDefinition.break_glass_authority enables emergency override
  protocol. Explicit, auditable.

## Dependencies

- **Depends on**:
  - `canon.entities.entity.ContentModel` - Base content model
  - `canon.entities.entity.create_entity` - Entity factory
  - `kron.types.db_types.FK` - Type-safe foreign keys
  - `canon.utils.compute_hash` - Ratification hash
  - `kron.utils.now_utc` - Timestamp utilities

- **Depended by**:
  - `canon.enforcement.types.RequestContext` - Carries active Charter
  - `canon.enforcement.service.CanonService` - Resolves situational gates
  - Policy resolution - Uses Charter.policy_ids to determine active policies
  - Role authorization - Uses Charter.roles for permission checks
  - Constraint enforcement - Uses Charter.constraints for gate selection

## Integration with CanonService

The Charter integrates with CanonService through RequestContext:

```python
# In CanonService._gate_hook()
if ctx.charter and service_gates.situational:
    active_policies = set(ctx.charter.content.policy_ids)
    for gate_id in service_gates.situational:
        if gate_id in active_policies:
            gate = create_gate(gate_id)
            if gate:
                gates_to_run.append(gate)
```

## Key Decisions (for ADR candidates)

1. **Charter as governance document**: Not just configuration, but a legal document with
   ratification. Signatory accountability.

2. **Constraints must have enforcement**: CharterConstraint.gate_id or service_check is required. No
   aspirational constraints. Enforced via `__post_init__`.

3. **Version as semantic string**: `version` field is string (e.g., "1.0.0"), not integer. Enables
   semantic versioning.

4. **Supersession, not deletion**: Old charters are superseded, not deleted. Full audit trail of
   governance history.

5. **MFA requirement per role**: RoleDefinition.requires_mfa defaults to True. Security-first for
   privileged actions.

6. **Policy IDs, not embedded policies**: Charter references policy_ids, doesn't embed
   PolicyDefinitions. Policies live in PolicyDefinition table.

7. **ContentModel + create_entity pattern**: Charter uses the standard canon-core entity factory
   pattern rather than direct Entity inheritance.

## Open Questions

- Multi-signatory requirements: Should Charter require minimum number of signatories? (e.g.,
  "requires 2 legal signatories")
- Constraint evaluation order: When multiple constraints apply, what's the evaluation order?
- Role hierarchy: Can roles inherit from other roles, or are they flat?
- Amendment process: How to make minor amendments without full re-ratification?
- Effective date transitions: What happens to in-flight operations when Charter changes?
- Cross-tenant constraints: Can a parent organization impose constraints on child tenants?

## Naming Convention Changes (from Constitution)

| Old Name               | New Name          |
| ---------------------- | ----------------- |
| Constitution           | Charter           |
| ConstitutionConstraint | CharterConstraint |
| constitution.py        | charter.py        |
| types/policy/          | core/             |
