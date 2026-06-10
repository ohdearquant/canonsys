# 031 Registry Allowlists - Vocabulary Mapping

**Status**: Implemented (vocabulary layer)

## Package Mapping

### Primary Package: `deployment`

**Location**: `hub/domains/corporate/packages/deployment/`

| Component          | Path            | Status      |
| ------------------ | --------------- | ----------- |
| Package definition | `package.py`    | Implemented |
| Service            | `service.py`    | Implemented |
| Exceptions         | `exceptions.py` | Implemented |

### Phrases

| Phrase                           | Path                                        | Regulatory Basis |
| -------------------------------- | ------------------------------------------- | ---------------- |
| `require_deployment_approval`    | `phrases/require_deployment_approval.py`    | SOC 2 CC7.1      |
| `verify_backup_complete`         | `phrases/verify_backup_complete.py`         | SOC 2 CC7.1      |
| `require_backup_verified`        | `phrases/require_backup_verified.py`        | SOC 2 CC7.1      |
| `require_production_environment` | `phrases/require_production_environment.py` | SOC 2 CC7.1      |
| `require_rollback_tested`        | `phrases/require_rollback_tested.py`        | SOC 2 CC7.1      |
| `verify_rollback_plan_present`   | `phrases/verify_rollback_plan_present.py`   | SOC 2 CC8.1      |
| `require_monitoring_active`      | `phrases/require_monitoring_active.py`      | SOC 2 CC7.2      |

### Secondary Package: `infra`

**Location**: `hub/domains/corporate/packages/infra/`

| Phrase                   | Path                                | Regulatory Basis |
| ------------------------ | ----------------------------------- | ---------------- |
| `verify_traffic_drained` | `phrases/verify_traffic_drained.py` | SOC 2 CC7.1      |

## Control Surface Coverage

| Surface             | Description         | Phrases                                                                                         |
| ------------------- | ------------------- | ----------------------------------------------------------------------------------------------- |
| Deployment Approval | Deployment approval | `require_deployment_approval`, `require_production_environment`, `verify_rollback_plan_present` |
| Backup Verification | Backup verification | `verify_backup_complete`, `require_backup_verified`                                             |

## Architectural Patterns

### Registry Pattern (Planned)

The registry pattern provides centralized allowlist management:

```python
# Usage pattern
result = await verify_in_allowlist(
    registry_type=RegistryType.DEPLOYMENT,
    entry_id="production-deploy-approval",
    ctx=ctx,
)
if not result.is_allowed:
    raise DeploymentNotApproved(result.reason)
```

### Evidence Integration

All deployment phrases emit evidence:

- `deployment.approval_verified` - When deployment approval checked
- `deployment.backup_complete` - When backup completion verified
- `deployment.rollback_present` - When rollback plan confirmed

## Dependencies

### This Design Depends On

- **ADR-008-policy-gates**: Gate system integration
- **ADR-029-caching-mechanism**: Decision cache for lookups
- **ADR-002-entity**: Entity patterns for AllowlistEntry

### Designs That Depend On This

- **ADR-015-jit-role**: Uses registry for JIT role validation
- **TDS-027-vendor-endpoints**: May use vendor registry

## Implementation Status

| Component             | Status      | Notes                           |
| --------------------- | ----------- | ------------------------------- |
| deployment package    | Implemented | 7 phrases                       |
| infra package         | Implemented | Traffic drain support           |
| Registry base class   | Planned     | Unified registry abstraction    |
| AllowlistEntry entity | Planned     | Single table for all registries |
| Cache integration     | Planned     | 300s TTL, invalidation on write |

## Charter Integration

**Charter**: None (infrastructure-level, not workflow)

**Control Surfaces**: Deployment Approval, Backup Verification
