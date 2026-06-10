# Canon Hub

The distributable governance vocabulary layer. Contains 24 vocabulary packages
(15 foundation + 9 domain), 60+ charter surface definitions in the Charter DSL,
and the package catalogs. Depends on `canon` for the framework (kron/specs, DSL,
entities).

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
│       └── ...
└── tests/
```

## Packages

Packages are organized into a **foundation** layer (cross-cutting primitives) and
**domain** layers (regulation-specific compositions).

### Foundation (`hub/foundation/packages/`) — 15 packages

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

### Corporate (`hub/domains/corporate/packages/`) — 3 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `corporate` | Corporate governance | SOX |
| `deployment` | Deployment controls | SOC 2 CC7.1-8.1 |
| `infra` | Infrastructure | SOC 2 CC7.1 |

### Governance (`hub/domains/governance/packages/`) — 6 packages

| Package | Purpose | Regulatory Basis |
|---------|---------|-----------------|
| `ai_governance` | AI/ML governance | EU AI Act, NYC LL144 |
| `data_protection` | Data protection | GDPR Art. 32, HIPAA |
| `export_control` | Export control | ITAR, EAR, OFAC |
| `incident` | Incident management | GDPR Art. 33, HIPAA |
| `legal` | Legal compliance | Employment law, FRCP |
| `notice` | Notice & notification | Employment law |

---

## Charter Definitions

```
hub/charters/
└── surfaces/                    # Charter surface definitions (Charter DSL)
    ├── ai/                      # AI governance surfaces
    ├── corporate/               # Corporate governance
    ├── data/                    # Data management
    ├── finance/                 # Financial controls
    ├── identity/                # Identity & access
    ├── infra/                   # Infrastructure
    ├── legal/                   # Legal & compliance
    ├── security/                # Security operations
    └── supplemental/            # Cross-domain surfaces
```

Charter files use the Charter DSL (`canon.dsl.compile_charter`). Every charter
compiles in CI — see `hub/tests/charters/`.

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

## Testing

```bash
uv run pytest hub/tests/                                   # All hub tests
uv run pytest hub/foundation/packages/{name}/tests/        # Foundation package tests
uv run pytest hub/domains/{domain}/packages/{name}/tests/  # Domain package tests
```
