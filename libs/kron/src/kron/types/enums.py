"""Canonical enums for the CanonSys vocabulary system.

Provides cross-cutting type-safe enums that replace bare str fields:

    PhraseActionType: Classifies phrase action prefixes (verify_, require_, etc.)
    DataClassification: Data sensitivity levels for access control and redaction
    DecisionClass: The 92 control surface decision classes (CS-001 through CS-092)

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
    """The 92 control surface decision classes.

    Each member maps a human-readable name to its CS-NNN identifier.
    These correspond 1:1 to charter definitions in hub/charters/surfaces/.

    Grouped by domain:
        CS-001..017: HR
        CS-018..025: Identity
        CS-026..038: Infrastructure
        CS-039..046: Data
        CS-047..055: Security
        CS-056..064: Finance
        CS-065..071: Legal
        CS-072..078: AI
        CS-079..083: Corporate
        CS-084..092: Supplemental
    """

    # --- HR (CS-001 .. CS-017) ---
    LAYOFF_RIF_INCLUSION = "CS-001"
    """Layoff / Reduction-In-Force inclusion decision."""

    CONTESTED_RESIGNATION = "CS-002"
    """Contested resignation acceptance."""

    PRIVILEGED_ROLE_ESCALATION = "CS-003"
    """Privileged role escalation grant."""

    CREDENTIAL_ISSUANCE = "CS-004"
    """Long-lived service credential issuance."""

    DESTRUCTIVE_MIGRATION = "CS-005"
    """Destructive schema migration execution."""

    FORCED_FAILOVER = "CS-006"
    """Forced failover execution."""

    DATA_SHARING = "CS-007"
    """External sensitive data sharing."""

    LEGAL_HOLD = "CS-008"
    """Legal hold placement."""

    WIRE_TRANSFER = "CS-009"
    """Large wire transfer execution."""

    INCIDENT_CLOSURE = "CS-010"
    """Security incident closure."""

    EXIT_INTERVIEW_DISCLOSURE = "CS-011"
    """Exit interview disclosure."""

    REHIRE_ELIGIBILITY_OVERRIDE = "CS-012"
    """Rehire eligibility override."""

    PROMOTION_WITHOUT_POSTING = "CS-013"
    """Promotion without job posting."""

    SALARY_BAND_EXCEPTION = "CS-014"
    """Salary band exception."""

    REMOTE_WORK_REVOCATION = "CS-015"
    """Remote work arrangement revocation."""

    VISA_SPONSORSHIP_TERMINATION = "CS-016"
    """Visa sponsorship termination."""

    SEVERANCE_AGREEMENT_EXECUTION = "CS-017"
    """Severance agreement execution."""

    # --- Identity (CS-018 .. CS-025) ---
    MFA_EXEMPTION = "CS-018"
    """MFA exemption grant."""

    SSO_BYPASS = "CS-019"
    """SSO bypass approval."""

    EMERGENCY_ACCOUNT = "CS-020"
    """Emergency account creation."""

    SERVICE_ACCOUNT_PRIVILEGE = "CS-021"
    """Service account privilege grant."""

    BREAK_GLASS = "CS-022"
    """Break-glass activation."""

    CA_TRUST = "CS-023"
    """Certificate authority trust establishment."""

    FEDERATION_LINK = "CS-024"
    """Identity federation link."""

    BIOMETRIC_BYPASS = "CS-025"
    """Biometric enrollment bypass."""

    # --- Infrastructure (CS-026 .. CS-038) ---
    PRODUCTION_DATABASE_ACCESS = "CS-026"
    """Production database access grant."""

    FIREWALL_RULE_BYPASS = "CS-027"
    """Firewall rule bypass."""

    LOAD_BALANCER_OVERRIDE = "CS-028"
    """Load balancer configuration override."""

    DNS_ZONE_DELEGATION = "CS-029"
    """DNS zone delegation."""

    SSL_CERTIFICATE_REVOCATION = "CS-030"
    """SSL certificate revocation."""

    CONTAINER_REGISTRY_PUSH = "CS-031"
    """Container registry push authorization."""

    KUBERNETES_ADMISSION_BYPASS = "CS-032"
    """Kubernetes admission controller bypass."""

    NETWORK_SEGMENTATION_OVERRIDE = "CS-033"
    """Network segmentation override."""

    BACKUP_RETENTION_OVERRIDE = "CS-034"
    """Backup retention policy override."""

    DISASTER_RECOVERY_TEST = "CS-035"
    """Disaster recovery test execution."""

    CAPACITY_OVERCOMMIT = "CS-036"
    """Capacity overcommit authorization."""

    MAINTENANCE_WINDOW_OVERRIDE = "CS-037"
    """Maintenance window override."""

    SLA_DEGRADATION_ACCEPTANCE = "CS-038"
    """SLA degradation acceptance."""

    # --- Data (CS-039 .. CS-046) ---
    PII_EXPORT = "CS-039"
    """PII export authorization."""

    RETENTION_OVERRIDE = "CS-040"
    """Data retention policy override."""

    CROSS_BORDER_TRANSFER = "CS-041"
    """Cross-border data transfer."""

    ANONYMIZATION_EXEMPTION = "CS-042"
    """Anonymization exemption."""

    CLASSIFICATION_DOWNGRADE = "CS-043"
    """Data classification downgrade."""

    SCHEMA_ROLLBACK = "CS-044"
    """Schema migration rollback."""

    DATASET_PUBLISH = "CS-045"
    """Dataset external publish."""

    LAKE_ACCESS = "CS-046"
    """Data lake access grant."""

    # --- Security (CS-047 .. CS-055) ---
    VULNERABILITY_EXEMPTION = "CS-047"
    """Vulnerability exemption."""

    PATCH_DEFERRAL = "CS-048"
    """Patch deferral."""

    PENETRATION_TEST_SCOPE = "CS-049"
    """Penetration test scope definition."""

    SECURITY_TOOL_BYPASS = "CS-050"
    """Security tool bypass."""

    THREAT_INTEL_DISCLOSURE = "CS-051"
    """Threat intelligence disclosure."""

    FORENSIC_IMAGE_RELEASE = "CS-052"
    """Forensic image release."""

    INCIDENT_ESCALATION_OVERRIDE = "CS-053"
    """Incident escalation override."""

    SECURITY_EXCEPTION_GRANT = "CS-054"
    """Security exception grant."""

    RED_TEAM_ENGAGEMENT = "CS-055"
    """Red team engagement authorization."""

    # --- Finance (CS-056 .. CS-064) ---
    BUDGET_REALLOCATION = "CS-056"
    """Budget reallocation authorization."""

    VENDOR_PAYMENT_OVERRIDE = "CS-057"
    """Vendor payment override."""

    EXPENSE_POLICY_EXCEPTION = "CS-058"
    """Expense policy exception."""

    REVENUE_RECOGNITION_OVERRIDE = "CS-059"
    """Revenue recognition override."""

    INTERCOMPANY_TRANSFER = "CS-060"
    """Intercompany transfer authorization."""

    TAX_JURISDICTION_CHANGE = "CS-061"
    """Tax jurisdiction change."""

    FINANCIAL_AUDIT_WAIVER = "CS-062"
    """Financial audit waiver."""

    CREDIT_LIMIT_OVERRIDE = "CS-063"
    """Credit limit override."""

    TREASURY_POSITION_CHANGE = "CS-064"
    """Treasury position change."""

    # --- Legal (CS-065 .. CS-071) ---
    LITIGATION_HOLD_RELEASE = "CS-065"
    """Litigation hold release."""

    PRIVILEGE_WAIVER = "CS-066"
    """Attorney-client privilege waiver."""

    SETTLEMENT_AUTHORITY = "CS-067"
    """Settlement authority grant."""

    REGULATORY_DISCLOSURE = "CS-068"
    """Regulatory disclosure."""

    CONTRACT_AMENDMENT = "CS-069"
    """Contract amendment execution."""

    IP_ASSIGNMENT = "CS-070"
    """Intellectual property assignment."""

    INDEMNIFICATION_WAIVER = "CS-071"
    """Indemnification waiver."""

    # --- AI (CS-072 .. CS-078) ---
    MODEL_DEPLOYMENT_OVERRIDE = "CS-072"
    """AI model deployment override."""

    TRAINING_DATA_INCLUSION = "CS-073"
    """Training data inclusion decision."""

    BIAS_ASSESSMENT_WAIVER = "CS-074"
    """Bias assessment waiver."""

    HUMAN_REVIEW_BYPASS = "CS-075"
    """Human review bypass for AI decisions."""

    AGENT_AUTONOMY_GRANT = "CS-076"
    """AI agent autonomy grant."""

    MODEL_RETIREMENT_OVERRIDE = "CS-077"
    """Model retirement override."""

    AI_INCIDENT_DISCLOSURE = "CS-078"
    """AI incident disclosure."""

    # --- Corporate (CS-079 .. CS-083) ---
    DUE_DILIGENCE_ACCESS = "CS-079"
    """Due diligence access grant."""

    INTEGRATION_SYSTEM_LINK = "CS-080"
    """Integration system link."""

    CARVE_OUT_EXECUTION = "CS-081"
    """Carve-out execution."""

    MATERIAL_CHANGE_DISCLOSURE = "CS-082"
    """Material change disclosure."""

    CLOSING_CONDITION_WAIVER = "CS-083"
    """Closing condition waiver."""

    # --- Supplemental (CS-084 .. CS-092) ---
    PRIVILEGED_FINANCE_ROLE = "CS-084"
    """Privileged finance role promotion."""

    MONITORING_REMOVAL = "CS-085"
    """Monitoring scope removal."""

    DLP_DISABLE = "CS-086"
    """Data loss prevention disable."""

    EXPORT_PERMISSION = "CS-087"
    """Sensitive system export permission."""

    ETHICS_CASE_CLOSURE = "CS-088"
    """Ethics case closure without action."""

    REINSTATE_ACCESS = "CS-089"
    """Reinstate terminated access exception."""

    EXPORT_CONTROL_OVERRIDE = "CS-090"
    """Export control restriction override."""

    DISABLE_AUDIT_LOGGING = "CS-091"
    """Disable audit logging for system."""

    LEGAL_DATA_RELEASE = "CS-092"
    """Release customer data under legal demand."""

    @classmethod
    def from_code(cls, code: str) -> DecisionClass | None:
        """Look up a DecisionClass by its CS-NNN code.

        Args:
            code: The decision class code (e.g., "CS-001").

        Returns:
            The matching DecisionClass, or None if not found.

        Examples:
            >>> DecisionClass.from_code("CS-001")
            <DecisionClass.LAYOFF_RIF_INCLUSION: 'CS-001'>
            >>> DecisionClass.from_code("CS-999")
            >>> # None
        """
        try:
            return cls(code)
        except ValueError:
            return None

    @property
    def code(self) -> str:
        """Return the CS-NNN code (alias for .value).

        Examples:
            >>> DecisionClass.LAYOFF_RIF_INCLUSION.code
            'CS-001'
        """
        return self.value

    @property
    def number(self) -> int:
        """Return the numeric portion of the code.

        Examples:
            >>> DecisionClass.LAYOFF_RIF_INCLUSION.number
            1
        """
        return int(self.value.split("-")[1])
