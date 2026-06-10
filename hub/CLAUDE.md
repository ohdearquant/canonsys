# Canon Hub

The distributable compliance vocabulary layer. Contains 29 vocabulary packages (15 foundation +
14 domain), charter definitions, OPA policies, and service implementations. Depends on `canon`
for the framework (kron/specs, DSL, entities, DB). See root `CLAUDE.md` for architecture principles.

---

## Package Structure

Each package is self-contained with phrases, types, exceptions, and a service wrapper.
Naming convention: `canon_vocab_{domain}`.

Reference example (`consent/`):

```
hub/foundation/packages/consent/
├── canon.toml                            # Package metadata
├── pyproject.toml                        # Python package config
├── src/canon_vocab_consent/
│   ├── __init__.py
│   ├── api.py                            # Public API
│   ├── package.py                        # Package registration
│   ├── schema.py                         # Schema definitions
│   ├── service.py                        # CanonService wrapper
│   ├── exceptions.py                     # Domain exceptions
│   ├── types/
│   │   ├── scope.py                      # ConsentScope enum
│   │   ├── status.py                     # ConsentStatus enum
│   │   └── token.py                      # ConsentToken type
│   └── phrases/
│       ├── constraints.py                # Shared constraint logic
│       ├── verify_token.py               # verify_consent_token
│       ├── grant_token.py                # grant_consent_token
│       ├── revoke_token.py               # revoke_consent_token
│       ├── require_active_consent.py     # require_active_consent
│       ├── require_valid_consent.py      # require_valid_consent
│       ├── require_not_expired.py
│       ├── require_not_withdrawn.py
│       ├── find_token.py
│       ├── list_tokens.py
│       ├── renew_token.py
│       ├── get_history.py
│       ├── cascade_revoke_token.py
│       └── verify_scope_covers.py
└── tests/
```

### All 29 Packages

Packages are organized into a **foundation** layer (cross-cutting primitives) and **domain** layers
(regulation-specific compositions).

#### Foundation (`hub/foundation/packages/`) — 15 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `authorization` | Access control | SOC 2 CC6.1-6.3 |
| `certification` | Decision certification | Employment law |
| `charter` | Charter workflows | Internal |
| `consent` | Consent management | FCRA 1681b(b), GDPR Art. 6-7 |
| `controls` | Control definitions | SOC 2 |
| `core` | Cross-cutting | SOX 302/404 |
| `evidence` | Evidence chains | FRE 901, ISO 27037 |
| `freshness` | Data freshness | Internal |
| `identity` | Identity verification | NIST SP 800-63B |
| `justification` | Business justification | SOX 404, COSO |
| `pattern` | Pattern matching | Internal |
| `policy` | Policy definitions | Internal |
| `scope` | Data scope limits | GDPR Art. 5(1)(c) |
| `timing` | Timing requirements | FCRA 1681m |
| `workflow` | Workflow orchestration | Internal |

#### Corporate (`hub/domains/corporate/packages/`) — 3 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `corporate` | Corporate governance | SOX |
| `deployment` | Deployment controls | SOC 2 CC7.1-8.1 |
| `infra` | Infrastructure | SOC 2 CC7.1 |

#### Employee (`hub/domains/employee/packages/`) — 4 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `hr` | HR operations | Employment law |
| `investigation` | Investigations | Employment law |
| `lifecycle` | Entity lifecycle | SOX 404, SOC 2 CC6.1 |
| `rif` | Reduction in force | WARN Act |

#### Governance (`hub/domains/governance/packages/`) — 6 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `ai_governance` | AI/ML governance | EU AI Act, NYC LL144 |
| `data_protection` | Data protection | GDPR Art. 32, HIPAA |
| `export_control` | Export control | ITAR, EAR, OFAC |
| `incident` | Incident management | GDPR Art. 33, HIPAA |
| `legal` | Legal compliance | Employment law, FRCP |
| `notice` | Notice & notification | Employment law |

#### Talent (`hub/domains/talent/packages/`) — 1 package

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `hiring_brief` | Hiring workflows | Internal |

---

## Charter Definitions

```
hub/charters/
├── cep.canon                    # Compliance Evidence Package
├── exception_offer.charter      # Exception offer approval workflow
├── executive_override.canon     # Executive override workflow
├── fcra_adverse_action.canon    # FCRA adverse action flow
├── tdc.canon                    # Termination Decision Certificate
├── workflows/                   # Reusable workflow definitions
└── surfaces/                    # Charter UI surface categories
    ├── ai/                      # AI-related surfaces
    ├── corporate/               # Corporate governance
    ├── data/                    # Data management
    ├── finance/                 # Financial controls
    └── ...
```

Charter files use the Charter DSL (see `libs/canon/CLAUDE.md` for DSL syntax and compilation).
Files ending in `.canon` or `.charter` — both use the same DSL.

---

## Policies

OPA/Rego policy files evaluated by the Regorus engine (Rust OPA implementation).

```
hub/policies/
├── manifest.toml                # Policy registry
└── jurisdictions/
    └── federal/
        └── policies/
            └── compensation/
                └── offer_band_check.rego    # Compensation band policy
```

Policy evaluation: `canon.utils.opa.PolicyEngine` loads policies at startup,
called via `PolicyEngine.evaluate_single()` from routers.

---

## Services

Hub-level service implementations (not CanonService subclasses — standalone):

| Service | Purpose |
|---------|---------|
| `services/auth/` | Authentication |
| `services/jit/` | Just-In-Time document access grants |
| `services/llm/` | LLM integration |
| `services/metering/` | Usage metering |
| `services/redaction/` | PII redaction |
| `services/vendor/` | Vendor management |

---

## Adding a New Package

1. Create package in the appropriate layer with `canon.toml`, `pyproject.toml`:
   - Foundation: `hub/foundation/packages/{name}/`
   - Domain: `hub/domains/{domain}/packages/{name}/`
2. Create `src/canon_vocab_{name}/` with `__init__.py`, `package.py`
3. Add phrases in `phrases/` — one file per phrase, using `create_phrase()` from `canon.kron.specs`
4. Add types in `types/` — enums, dataclasses for domain concepts
5. Add `exceptions.py` for domain-specific errors
6. Add `service.py` wrapping phrases in a `CanonService` subclass
7. Write tests in `tests/`
8. Register in `hub/catalogs/` if distributable

### Testing

```bash
cd hub
uv run pytest tests/                                       # All hub tests
uv run pytest foundation/packages/{name}/tests/            # Foundation package tests
uv run pytest domains/{domain}/packages/{name}/tests/      # Domain package tests
```
