# CanonSys

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**CanonSys is an agent governance framework** — a policy DSL and runtime enforcement core for what AI agents (and humans) may or may not do. It makes compliance decisions provable by enforcing them as substrate, not as an afterthought.

> "We don't help you make decisions. We make sure the decisions you make are provable."

The name comes from Greek *kanon* — rule, standard, measure.

---

## What it solves

Modern AI agents operate in regulated domains: employment, healthcare, finance, data privacy. Governance today is either absent or bolted on. CanonSys makes compliance a compile-time property: you describe *what must happen* in a declarative DSL, the compiler validates it against your vocabulary and policies, and the runtime executes the resulting DAG with a cryptographically-verifiable evidence trail.

Compliance errors become **compile-time errors** — caught before execution, not in production.

---

## Quickstart

```bash
git clone https://github.com/ohdearquant/canonsys
cd canonsys
uv sync
uv run pytest libs/kron/       # 331 tests, self-contained
uv run pytest libs/canon/tests/ --ignore=libs/canon/tests/db --ignore=libs/canon/tests/integration
```

### Write a Charter (policy DSL)

The Charter DSL compiles human-readable compliance workflows into validated DAGs. The following is a real example from the test suite — it compiles and resolves correctly against the feature/policy registries:

```python
from canon.dsl import compile_charter, SchemaCatalog
from canon.dsl.catalog import SchemaCatalog

# Register your schema types
catalog = SchemaCatalog()
catalog.register("canon.hr", "2026.01", "PIPReport", PIPReport)
catalog.register("canon.hr", "2026.01", "EligibilityReport", EligibilityReport)
catalog.register("canon.hr", "2026.01", "TerminationCertificate", TerminationCertificate)

charter_source = """\
charter "Performance Improvement Plan" v1.0

schemas: canon.hr@2026.01

policies:
    - employment.pip
    - employment.termination

workflow pip_workflow:
    phase eligibility:
        require verify_consent("background_check")
        action assess_eligibility()
        output EligibilityReport

    phase review:
        require eligibility.passed
        action evaluate_performance()
        action conduct_review()
        output PIPReport

    phase decision:
        require review.passed
        action certify_termination()
        output TerminationCertificate
        certify immutable
        evidence termination_record

situations:
    when jurisdiction == "NYC":
        waiting_period 30..90 days
        require verify_consent("aedt_disclosure")

roles:
    hr_manager:
        actions: [assess_eligibility, evaluate_performance, conduct_review]
        break_glass: false
        requires_mfa: true
    legal_counsel:
        actions: [certify_termination]
        break_glass: true
        requires_mfa: true
"""

compiled = compile_charter(charter_source, catalog=catalog)

# Phase order is topologically sorted:
# compiled.phase_order["pip_workflow"] -> ("eligibility", "review", "decision")
print(compiled.phase_order["pip_workflow"])

# Features the runtime must provide:
# compiled.feature_names -> frozenset({"verify_consent", "assess_eligibility", ...})
print(compiled.feature_names)

# Policies that must be loaded:
# compiled.policy_ids -> {"employment.pip", "employment.termination"}
print(compiled.policy_ids)
```

A minimal charter that compiles to a single-phase workflow:

```
charter "Minimal" v0.1

workflow basic:
    phase step_one:
        action verify_consent()
```

```python
from canon.dsl import compile_charter

compiled = compile_charter('charter "Minimal" v0.1\n\nworkflow basic:\n    phase step_one:\n        action verify_consent()\n')
assert compiled.name == "Minimal"
assert "verify_consent" in compiled.feature_names
```

---

## Modules

**`kron`** — Type system, phrase infrastructure, and DAG execution engine. Provides `Node`, `Element`, `Progression`, `Pile`, `Flow` (persistable graph entities), `Spec`/`Phrase`/`Operable` (framework-agnostic field specifications), concurrency utilities, and the `Session`/`Exchange` conversation orchestration layer. Self-contained — no external dependencies at test time.

**`canon`** — Policy enforcement engine built on kron. Contains the Charter DSL (lexer → parser → compiler → resolver), the charter runtime (DAG execution with dependency resolution, evidence trails, role-based grants), OPA/Rego integration for policy evaluation, KMS/TSA cryptographic utilities, and vendor integrations (AWS KMS, S3, HashiCorp Vault). Depends on kron.

**`hub`** — The governance vocabulary built on canon. 15 foundation packages (consent, evidence, authorization, certification, timing, scope, controls, justification, identity, …), domain packages for corporate and governance concerns (export control, data protection, AI governance, incident, legal, notice), and 60+ charter surfaces written in the Charter DSL — real, compiling policies for AI governance (model deployment overrides, human-review bypass, agent autonomy grants), security (DLP disable, audit-logging changes, access reinstatement), finance, legal, identity, and infrastructure. Every charter compiles in CI (`uv run pytest hub/tests`).

```bash
uv run pytest hub/tests    # 461 tests: every charter surface compiles + executor/vocabulary suites
```

---

## Credit

CanonSys began as a commissioned project — [Jason La Barbera](https://github.com/ShortyLTD) saw the need for agent governance early and funded the original work.

---

## License

Apache-2.0. Copyright 2026 HaiyangLi. See [LICENSE](LICENSE).

---

## Optional: Rego policy evaluation (regorus)

OPA/Rego policy evaluation in `canon` is powered by [regorus](https://github.com/microsoft/regorus), Microsoft's Rust Rego engine. As of June 2026 regorus has no usable PyPI release, so it ships as an opt-in extra built from source (requires a Rust toolchain):

```bash
uv sync --package canon --extra rego
```

Without the extra, everything else works — the Charter DSL, runtime, and crypto utilities have no regorus dependency, and the regorus-dependent tests skip automatically.
