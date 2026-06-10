"""Charter vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CHARTER = VocabularyPackage(
    name="charter",
    description="Charter lifecycle management, surface binding, and decision evaluation.",
    feature_names=frozenset(
        {
            "activate_charter",
            "bind_surface",
            "create_charter",
            "evaluate_decision",
        }
    ),
    schema_names=frozenset(
        {
            "ActivateCharterResult",
            "BindSurfaceResult",
            "Charter",
            "CharterContent",
            "CharterStatus",
            "CharterSurfaceBinding",
            "CharterSurfaceBindingContent",
            "CreateCharterResult",
            "DecisionResult",
            "SurfaceBinding",
        }
    ),
    regulatory_basis=(
        "SOX \u00a7 404",
        "SOC 2 CC1.1",
    ),
    version="2026.01",
    domain_module="canon_vocab_charter",
)
