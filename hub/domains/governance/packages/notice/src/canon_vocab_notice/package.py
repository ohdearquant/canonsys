"""Notice vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

NOTICE = VocabularyPackage(
    name="notice",
    description="Formal compliance notice delivery, acknowledgment tracking, and waiting period management.",
    # NOTE: These map to NoticeService._handle_* methods, not phrase functions.
    # The notice package uses a service-oriented pattern (BaseService + models)
    # rather than the phrase-based pattern used by other packages.
    feature_names=frozenset(
        {
            "create_pre_adverse",
            "create_adverse",
            "check_waiting",
            "pause_waiting",
            "resume_waiting",
            "record_delivery",
            "get_waiting",
            "get_deliveries",
            "create_notice",
            "record_acknowledgment",
            "get_notice",
            "require_notice_delivered",
        }
    ),
    schema_names=frozenset(
        {
            "RequireNoticeDeliveredSpecs",
            "CheckWaitingOptions",
            "CreateAdverseOptions",
            "CreatePreAdverseOptions",
            "CreateNoticeOptions",
            "DeliveryAttempt",
            "DeliveryMethod",
            "DeliveryStatus",
            "GetDeliveriesOptions",
            "GetNoticeOptions",
            "GetWaitingOptions",
            "NoticeAction",
            "NoticePayload",
            "NoticeRequest",
            "NoticeType",
            "PauseWaitingOptions",
            "RecordAcknowledgmentOptions",
            "RecordDeliveryOptions",
            "ResumeWaitingOptions",
            "WaitingPeriod",
        }
    ),
    regulatory_basis=(
        "FCRA \u00a7 1681m",
        "WARN Act",
    ),
    version="2026.01",
    domain_module="canon_vocab_notice",
)
