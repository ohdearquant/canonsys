"""Canonical enums for the CanonSys vocabulary system.

Provides cross-cutting type-safe enums that replace bare str fields:

    PhraseActionType: Classifies phrase action prefixes (verify_, require_, etc.)
    DataClassification: Data sensitivity levels for access control and redaction
    DecisionClass: Control surface decision classes

These are definition-only types. Existing phrase code is NOT refactored to
consume them yet -- that is a separate pass (Phase 2 gates).
"""

from __future__ import annotations

from .base import Enum

__all__ = [
    "DataClassification",
    "DecisionClass",
    "PhraseActionType",
]


# =============================================================================
# PhraseActionType
# =============================================================================


class PhraseActionType(Enum):
    """Classifies phrase action prefixes in the vocabulary system.

    Every phrase name starts with a verb prefix that determines its
    semantics (verify_*, require_*, derive_*, etc.). This enum makes
    that classification explicit and type-safe.

    Named PhraseActionType (not ActionType) to avoid collision with
    the existing certification.ActionType and workflow queue.ActionType
    which serve different purposes.
    """

    # --- Gate phrases (binary pass/fail) ---
    VERIFY = "verify"
    """verify_* phrases: Check a condition, return bool. Never raises."""

    REQUIRE = "require"
    """require_* phrases: Assert a condition. Always raises on failure."""

    CHECK = "check"
    """check_* phrases: Inspect state, return status. Never raises."""

    # --- Mutation phrases ---
    CERTIFY = "certify"
    """certify_* phrases: Issue an immutable decision certificate."""

    EMIT = "emit"
    """emit_* phrases: Produce an output artifact (certificate, hash)."""

    RECORD = "record"
    """record_* phrases: Persist a fact or attestation."""

    SAVE = "save"
    """save_* phrases: Persist evidence or state."""

    REVOKE = "revoke"
    """revoke_* phrases: Invalidate a prior grant or token."""

    CASCADE = "cascade"
    """cascade_* phrases: Propagate an action to dependent entities."""

    GRANT = "grant"
    """grant_* phrases: Issue a permission or token."""

    LOCK = "lock"
    """lock_* phrases: Freeze state to prevent further mutation."""

    CREATE = "create"
    """create_* phrases: Instantiate a new entity."""

    COMPLETE = "complete"
    """complete_* phrases: Mark a workflow or process as finished."""

    # --- Derivation phrases ---
    DERIVE = "derive"
    """derive_* phrases: Compute a value from existing data."""

    COMPUTE = "compute"
    """compute_* phrases: Calculate a hash, metric, or aggregate."""

    EVALUATE = "evaluate"
    """evaluate_* phrases: Run policy or decision logic."""

    # --- Query phrases ---
    GET = "get"
    """get_* phrases: Retrieve a single entity or record."""

    FIND = "find"
    """find_* phrases: Locate an entity by criteria."""

    LIST = "list"
    """list_* phrases: Retrieve a collection of entities."""

    # --- Lifecycle phrases ---
    LOG = "log"
    """log_* phrases: Append to audit trail."""

    NOTIFY = "notify"
    """notify_* phrases: Send a notification or alert."""

    SCHEDULE = "schedule"
    """schedule_* phrases: Set up a future action."""

    TRIGGER = "trigger"
    """trigger_* phrases: Initiate a downstream process."""

    INVOKE = "invoke"
    """invoke_* phrases: Call an external service or subsystem."""

    CHAIN = "chain"
    """chain_* phrases: Link entities in an evidence chain."""

    MINT = "mint"
    """mint_* phrases: Produce a cryptographic certificate."""

    @classmethod
    def from_phrase_name(cls, name: str) -> PhraseActionType | None:
        """Extract action type from a phrase function name.

        Args:
            name: Snake_case phrase name (e.g., "verify_consent_token").

        Returns:
            The matching PhraseActionType, or None if the prefix is not
            recognized.

        Examples:
            >>> PhraseActionType.from_phrase_name("verify_consent_token")
            <PhraseActionType.VERIFY: 'verify'>
            >>> PhraseActionType.from_phrase_name("require_active_consent")
            <PhraseActionType.REQUIRE: 'require'>
            >>> PhraseActionType.from_phrase_name("unknown_action")
            >>> # None
        """
        prefix = name.split("_", 1)[0] if "_" in name else name
        try:
            return cls(prefix)
        except ValueError:
            return None


# =============================================================================
# DataClassification
# =============================================================================


class DataClassification(Enum):
    """Data sensitivity classification for access control and redaction.

    Maps to regulatory data categories used across vocabulary packages
    for scope validation, redaction rules, and access gating.
    """

    PII = "pii"
    """Personally identifiable information (GDPR Art. 4, CCPA)."""

    SENSITIVE = "sensitive"
    """Sensitive personal data (GDPR Art. 9 special categories)."""

    PROTECTED = "protected"
    """Protected class data (Title VII, ADA, ADEA)."""

    BGC = "bgc"
    """Background check data (FCRA regulated)."""

    COMP = "comp"
    """Compensation data (pay equity, NLRA protected)."""

    MEDICAL = "medical"
    """Medical/health data (HIPAA, ADA, GINA)."""

    PUBLIC = "public"
    """Publicly available information."""

    INTERNAL = "internal"
    """Internal business data, not regulated but access-controlled."""

    CONFIDENTIAL = "confidential"
    """Confidential business data (trade secrets, NDA-bound)."""


# =============================================================================
# DecisionClass
# =============================================================================


class DecisionClass(Enum):
    """Control surface decision classes.

    Each member maps a human-readable name to a stable snake_case identifier.
    These correspond to charter definitions in hub/charters/surfaces/.

    """

    # --- HR ---
    LAYOFF_RIF_INCLUSION = "layoff_rif_inclusion"
    """Layoff / Reduction-In-Force inclusion decision."""

    CONTESTED_RESIGNATION = "contested_resignation"
    """Contested resignation acceptance."""

    PRIVILEGED_ROLE_ESCALATION = "privileged_role_escalation"
    """Privileged role escalation grant."""

    CREDENTIAL_ISSUANCE = "credential_issuance"
    """Long-lived service credential issuance."""

    DESTRUCTIVE_MIGRATION = "destructive_migration"
    """Destructive schema migration execution."""

    FORCED_FAILOVER = "forced_failover"
    """Forced failover execution."""

    DATA_SHARING = "data_sharing"
    """External sensitive data sharing."""

    LEGAL_HOLD = "legal_hold"
    """Legal hold placement."""

    WIRE_TRANSFER = "wire_transfer"
    """Large wire transfer execution."""

    INCIDENT_CLOSURE = "incident_closure"
    """Security incident closure."""

    EXIT_INTERVIEW_DISCLOSURE = "exit_interview_disclosure"
    """Exit interview disclosure."""

    REHIRE_ELIGIBILITY_OVERRIDE = "rehire_eligibility_override"
    """Rehire eligibility override."""

    PROMOTION_WITHOUT_POSTING = "promotion_without_posting"
    """Promotion without job posting."""

    SALARY_BAND_EXCEPTION = "salary_band_exception"
    """Salary band exception."""

    REMOTE_WORK_REVOCATION = "remote_work_revocation"
    """Remote work arrangement revocation."""

    VISA_SPONSORSHIP_TERMINATION = "visa_sponsorship_termination"
    """Visa sponsorship termination."""

    SEVERANCE_AGREEMENT_EXECUTION = "severance_agreement_execution"
    """Severance agreement execution."""

    # --- Identity ---
    MFA_EXEMPTION = "mfa_exemption"
    """MFA exemption grant."""

    SSO_BYPASS = "sso_bypass"
    """SSO bypass approval."""

    EMERGENCY_ACCOUNT = "emergency_account"
    """Emergency account creation."""

    SERVICE_ACCOUNT_PRIVILEGE = "service_account_privilege"
    """Service account privilege grant."""

    BREAK_GLASS = "break_glass"
    """Break-glass activation."""

    CA_TRUST = "ca_trust"
    """Certificate authority trust establishment."""

    FEDERATION_LINK = "federation_link"
    """Identity federation link."""

    BIOMETRIC_BYPASS = "biometric_bypass"
    """Biometric enrollment bypass."""

    # --- Infrastructure ---
    PRODUCTION_DATABASE_ACCESS = "production_database_access"
    """Production database access grant."""

    FIREWALL_RULE_BYPASS = "firewall_rule_bypass"
    """Firewall rule bypass."""

    LOAD_BALANCER_OVERRIDE = "load_balancer_override"
    """Load balancer configuration override."""

    DNS_ZONE_DELEGATION = "dns_zone_delegation"
    """DNS zone delegation."""

    SSL_CERTIFICATE_REVOCATION = "ssl_certificate_revocation"
    """SSL certificate revocation."""

    CONTAINER_REGISTRY_PUSH = "container_registry_push"
    """Container registry push authorization."""

    KUBERNETES_ADMISSION_BYPASS = "kubernetes_admission_bypass"
    """Kubernetes admission controller bypass."""

    NETWORK_SEGMENTATION_OVERRIDE = "network_segmentation_override"
    """Network segmentation override."""

    BACKUP_RETENTION_OVERRIDE = "backup_retention_override"
    """Backup retention policy override."""

    DISASTER_RECOVERY_TEST = "disaster_recovery_test"
    """Disaster recovery test execution."""

    CAPACITY_OVERCOMMIT = "capacity_overcommit"
    """Capacity overcommit authorization."""

    MAINTENANCE_WINDOW_OVERRIDE = "maintenance_window_override"
    """Maintenance window override."""

    SLA_DEGRADATION_ACCEPTANCE = "sla_degradation_acceptance"
    """SLA degradation acceptance."""

    # --- Data ---
    PII_EXPORT = "pii_export"
    """PII export authorization."""

    RETENTION_OVERRIDE = "retention_override"
    """Data retention policy override."""

    CROSS_BORDER_TRANSFER = "cross_border_transfer"
    """Cross-border data transfer."""

    ANONYMIZATION_EXEMPTION = "anonymization_exemption"
    """Anonymization exemption."""

    CLASSIFICATION_DOWNGRADE = "classification_downgrade"
    """Data classification downgrade."""

    SCHEMA_ROLLBACK = "schema_rollback"
    """Schema migration rollback."""

    DATASET_PUBLISH = "dataset_publish"
    """Dataset external publish."""

    LAKE_ACCESS = "lake_access"
    """Data lake access grant."""

    # --- Security ---
    VULNERABILITY_EXEMPTION = "vulnerability_exemption"
    """Vulnerability exemption."""

    PATCH_DEFERRAL = "patch_deferral"
    """Patch deferral."""

    PENETRATION_TEST_SCOPE = "penetration_test_scope"
    """Penetration test scope definition."""

    SECURITY_TOOL_BYPASS = "security_tool_bypass"
    """Security tool bypass."""

    THREAT_INTEL_DISCLOSURE = "threat_intel_disclosure"
    """Threat intelligence disclosure."""

    FORENSIC_IMAGE_RELEASE = "forensic_image_release"
    """Forensic image release."""

    INCIDENT_ESCALATION_OVERRIDE = "incident_escalation_override"
    """Incident escalation override."""

    SECURITY_EXCEPTION_GRANT = "security_exception_grant"
    """Security exception grant."""

    RED_TEAM_ENGAGEMENT = "red_team_engagement"
    """Red team engagement authorization."""

    # --- Finance ---
    BUDGET_REALLOCATION = "budget_reallocation"
    """Budget reallocation authorization."""

    VENDOR_PAYMENT_OVERRIDE = "vendor_payment_override"
    """Vendor payment override."""

    EXPENSE_POLICY_EXCEPTION = "expense_policy_exception"
    """Expense policy exception."""

    REVENUE_RECOGNITION_OVERRIDE = "revenue_recognition_override"
    """Revenue recognition override."""

    INTERCOMPANY_TRANSFER = "intercompany_transfer"
    """Intercompany transfer authorization."""

    TAX_JURISDICTION_CHANGE = "tax_jurisdiction_change"
    """Tax jurisdiction change."""

    FINANCIAL_AUDIT_WAIVER = "financial_audit_waiver"
    """Financial audit waiver."""

    CREDIT_LIMIT_OVERRIDE = "credit_limit_override"
    """Credit limit override."""

    TREASURY_POSITION_CHANGE = "treasury_position_change"
    """Treasury position change."""

    # --- Legal ---
    LITIGATION_HOLD_RELEASE = "litigation_hold_release"
    """Litigation hold release."""

    PRIVILEGE_WAIVER = "privilege_waiver"
    """Attorney-client privilege waiver."""

    SETTLEMENT_AUTHORITY = "settlement_authority"
    """Settlement authority grant."""

    REGULATORY_DISCLOSURE = "regulatory_disclosure"
    """Regulatory disclosure."""

    CONTRACT_AMENDMENT = "contract_amendment"
    """Contract amendment execution."""

    IP_ASSIGNMENT = "ip_assignment"
    """Intellectual property assignment."""

    INDEMNIFICATION_WAIVER = "indemnification_waiver"
    """Indemnification waiver."""

    # --- AI ---
    MODEL_DEPLOYMENT_OVERRIDE = "model_deployment_override"
    """AI model deployment override."""

    TRAINING_DATA_INCLUSION = "training_data_inclusion"
    """Training data inclusion decision."""

    BIAS_ASSESSMENT_WAIVER = "bias_assessment_waiver"
    """Bias assessment waiver."""

    HUMAN_REVIEW_BYPASS = "human_review_bypass"
    """Human review bypass for AI decisions."""

    AGENT_AUTONOMY_GRANT = "agent_autonomy_grant"
    """AI agent autonomy grant."""

    MODEL_RETIREMENT_OVERRIDE = "model_retirement_override"
    """Model retirement override."""

    AI_INCIDENT_DISCLOSURE = "ai_incident_disclosure"
    """AI incident disclosure."""

    # --- Corporate ---
    DUE_DILIGENCE_ACCESS = "due_diligence_access"
    """Due diligence access grant."""

    INTEGRATION_SYSTEM_LINK = "integration_system_link"
    """Integration system link."""

    CARVE_OUT_EXECUTION = "carve_out_execution"
    """Carve-out execution."""

    MATERIAL_CHANGE_DISCLOSURE = "material_change_disclosure"
    """Material change disclosure."""

    CLOSING_CONDITION_WAIVER = "closing_condition_waiver"
    """Closing condition waiver."""

    # --- Supplemental ---
    PRIVILEGED_FINANCE_ROLE = "privileged_finance_role"
    """Privileged finance role promotion."""

    MONITORING_REMOVAL = "monitoring_removal"
    """Monitoring scope removal."""

    DLP_DISABLE = "dlp_disable"
    """Data loss prevention disable."""

    EXPORT_PERMISSION = "export_permission"
    """Sensitive system export permission."""

    ETHICS_CASE_CLOSURE = "ethics_case_closure"
    """Ethics case closure without action."""

    REINSTATE_ACCESS = "reinstate_access"
    """Reinstate terminated access exception."""

    EXPORT_CONTROL_OVERRIDE = "export_control_override"
    """Export control restriction override."""

    DISABLE_AUDIT_LOGGING = "disable_audit_logging"
    """Disable audit logging for system."""

    LEGAL_DATA_RELEASE = "legal_data_release"
    """Release customer data under legal demand."""

    @classmethod
    def from_code(cls, code: str) -> DecisionClass | None:
        """Look up a DecisionClass by its identifier.

        Args:
            code: The decision class identifier (e.g., "layoff_rif_inclusion").

        Returns:
            The matching DecisionClass, or None if not found.

        Examples:
            >>> DecisionClass.from_code("layoff_rif_inclusion")
            <DecisionClass.LAYOFF_RIF_INCLUSION: 'layoff_rif_inclusion'>
            >>> DecisionClass.from_code("unknown")
            >>> # None
        """
        try:
            return cls(code)
        except ValueError:
            return None

    @property
    def code(self) -> str:
        """Return the decision class identifier (alias for .value).

        Examples:
            >>> DecisionClass.LAYOFF_RIF_INCLUSION.code
            'layoff_rif_inclusion'
        """
        return self.value

