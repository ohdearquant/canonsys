"""Workflow vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

WORKFLOW = VocabularyPackage(
    name="workflow",
    description="Workflow lifecycle, step recording, vendor call provenance, and completion tracking.",
    feature_names=frozenset(
        {
            "complete_workflow_run",
            "create_workflow_run",
            "record_vendor_call",
            "record_workflow_step",
        }
    ),
    schema_names=frozenset(
        {
            "VendorCallStatus",
            "WorkflowRunStatus",
            "WorkflowType",
        }
    ),
    regulatory_basis=(
        "NYC LL144",
        "EU AI Act",
        "SOC 2",
    ),
    version="2026.01",
    domain_module="canon_vocab_workflow",
)
