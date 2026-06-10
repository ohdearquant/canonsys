"""Tests for the truth machine exception hierarchy.

Tests cover:
- InvariantViolation base class methods and attributes
- All 6 category classes inherit from InvariantViolation
- All specific exceptions inherit from correct category
- Exception fields are set correctly
- to_dict() and to_evidence_context() serialization
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from canon_vocab_consent.exceptions import (
    ConsentExpiredError,
    ConsentNotValidError,
    ConsentWithdrawnError,
)

from canon.enforcement.exceptions import (  # Base; Category classes; Timing domain; Authorization domain; Evidence domain; Data protection domain; AI governance domain
    AIGovernanceViolation,
    AuthorizationViolation,
    BiasAssessmentMissingError,
    CEPNotSealedError,
    ChainBrokenError,
    ClassificationViolationError,
    ClearanceInsufficientError,
    ConsentViolation,
    DataProtectionViolation,
    DisclosureMissingError,
    DualApprovalMissingError,
    EncryptionMissingError,
    EvidenceNotBoundError,
    EvidenceStaleError,
    EvidenceViolation,
    HashMismatchError,
    HumanReviewMissingError,
    InvariantViolation,
    NoticePrecedenceError,
    PIIExposureError,
    PIIPublicExposureError,
    RetentionExceededError,
    SoDViolationError,
    TimingViolation,
    ToolConfigMismatchError,
    UnencryptedTransmissionError,
    WaitingPeriodNotElapsedError,
)

# =============================================================================
# InvariantViolation Base Class Tests
# =============================================================================


class TestInvariantViolationBase:
    """Tests for InvariantViolation base class."""

    def test_default_initialization(self):
        """Test InvariantViolation with default values."""
        exc = InvariantViolation()

        assert exc.regulation == "CANON"
        assert exc.message == "[CANON] Regulatory invariant violation"
        assert exc.context == {}
        assert str(exc) == "[CANON] Regulatory invariant violation"

    def test_custom_message(self):
        """Test InvariantViolation with custom message."""
        exc = InvariantViolation("Custom violation message")

        assert exc.message == "[CANON] Custom violation message"
        assert str(exc) == "[CANON] Custom violation message"

    def test_custom_regulation(self):
        """Test InvariantViolation with custom regulation."""
        exc = InvariantViolation(regulation="FCRA Section 1681b")

        assert exc.regulation == "FCRA Section 1681b"
        assert str(exc) == "[FCRA Section 1681b] Regulatory invariant violation"

    def test_context_dict(self):
        """Test InvariantViolation with context dict."""
        context = {"subject_id": "12345", "scope": "background_check"}
        exc = InvariantViolation(context=context)

        assert exc.context == context
        assert exc.context["subject_id"] == "12345"

    def test_cause_chaining(self):
        """Test InvariantViolation with cause exception."""
        original = ValueError("Original error")
        exc = InvariantViolation("Wrapped error", cause=original)

        assert exc.__cause__ is original

    def test_to_dict(self):
        """Test to_dict() serialization."""
        exc = InvariantViolation(
            "Test message",
            regulation="TEST_REG",
            context={"key": "value"},
        )
        result = exc.to_dict()

        assert result["violation_type"] == "InvariantViolation"
        assert result["regulation"] == "TEST_REG"
        assert result["message"] == "[TEST_REG] Test message"
        assert result["context"] == {"key": "value"}

    def test_to_evidence_context(self):
        """Test to_evidence_context() for evidence binding."""
        exc = InvariantViolation(
            "Test message",
            regulation="TEST_REG",
            context={"subject_id": "123", "scope": "test"},
        )
        result = exc.to_evidence_context()

        assert result["violation_type"] == "InvariantViolation"
        assert result["regulation_cited"] == "TEST_REG"
        assert result["subject_id"] == "123"
        assert result["scope"] == "test"

    def test_is_exception_subclass(self):
        """Test InvariantViolation is an Exception."""
        assert issubclass(InvariantViolation, Exception)

        exc = InvariantViolation()
        assert isinstance(exc, Exception)


# =============================================================================
# Category Class Tests
# =============================================================================


class TestCategoryClasses:
    """Tests for category exception classes."""

    @pytest.mark.parametrize(
        "category_cls,expected_regulation,expected_message",
        [
            (ConsentViolation, "GDPR Article 7", "Consent requirement not satisfied"),
            (
                TimingViolation,
                "FCRA Section 1681b(b)(3)",
                "Timing requirement not satisfied",
            ),
            (
                AuthorizationViolation,
                "SOX Section 404",
                "Authorization requirement not satisfied",
            ),
            (
                EvidenceViolation,
                "SOX Section 802",
                "Evidence requirement not satisfied",
            ),
            (
                DataProtectionViolation,
                "GDPR Article 32",
                "Data protection requirement not satisfied",
            ),
            (
                AIGovernanceViolation,
                "EU AI Act Article 14",
                "AI governance requirement not satisfied",
            ),
        ],
    )
    def test_category_defaults(self, category_cls, expected_regulation, expected_message):
        """Test category classes have correct default values."""
        exc = category_cls()

        assert exc.regulation == expected_regulation
        assert exc.message == f"[{expected_regulation}] {expected_message}"
        assert issubclass(category_cls, InvariantViolation)
        assert isinstance(exc, InvariantViolation)

    @pytest.mark.parametrize(
        "category_cls",
        [
            ConsentViolation,
            TimingViolation,
            AuthorizationViolation,
            EvidenceViolation,
            DataProtectionViolation,
            AIGovernanceViolation,
        ],
    )
    def test_category_inheritance(self, category_cls):
        """Test all categories inherit from InvariantViolation."""
        assert issubclass(category_cls, InvariantViolation)

    @pytest.mark.parametrize(
        "category_cls",
        [
            ConsentViolation,
            TimingViolation,
            AuthorizationViolation,
            EvidenceViolation,
            DataProtectionViolation,
            AIGovernanceViolation,
        ],
    )
    def test_category_custom_message(self, category_cls):
        """Test categories accept custom messages."""
        exc = category_cls("Custom message")

        assert exc.message == f"[{exc.regulation}] Custom message"


# =============================================================================
# Consent Domain Exception Tests
# =============================================================================


class TestConsentNotValidError:
    """Tests for ConsentNotValidError."""

    def test_initialization(self):
        """Test ConsentNotValidError initialization."""
        subject_id = uuid4()
        exc = ConsentNotValidError(subject_id=subject_id, scope="background_check")

        assert exc.subject_id == subject_id
        assert exc.scope == "background_check"
        assert exc.regulation == "FCRA Section 1681b(b)(2)"
        assert "background_check" in exc.message
        assert str(subject_id) in exc.message

    def test_inherits_from_consent_violation(self):
        """Test ConsentNotValidError inherits from ConsentViolation."""
        exc = ConsentNotValidError(subject_id=uuid4(), scope="test")

        assert isinstance(exc, ConsentViolation)
        assert isinstance(exc, InvariantViolation)

    def test_context_contains_expected_fields(self):
        """Test context dict has expected fields."""
        subject_id = uuid4()
        exc = ConsentNotValidError(subject_id=subject_id, scope="background_check")

        assert exc.context["subject_id"] == str(subject_id)
        assert exc.context["scope"] == "background_check"


class TestConsentExpiredError:
    """Tests for ConsentExpiredError."""

    def test_initialization(self):
        """Test ConsentExpiredError initialization."""
        subject_id = uuid4()
        expired_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        exc = ConsentExpiredError(
            subject_id=subject_id, scope="background_check", expired_at=expired_at
        )

        assert exc.subject_id == subject_id
        assert exc.scope == "background_check"
        assert exc.expired_at == expired_at
        assert exc.regulation == "GDPR Article 7(3)"
        assert "expired" in exc.message.lower()

    def test_inherits_from_consent_violation(self):
        """Test ConsentExpiredError inherits from ConsentViolation."""
        exc = ConsentExpiredError(
            subject_id=uuid4(),
            scope="test",
            expired_at=datetime.now(UTC),
        )

        assert isinstance(exc, ConsentViolation)
        assert isinstance(exc, InvariantViolation)

    def test_context_contains_timestamp(self):
        """Test context dict contains expired_at timestamp."""
        expired_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        exc = ConsentExpiredError(subject_id=uuid4(), scope="test", expired_at=expired_at)

        assert exc.context["expired_at"] == expired_at.isoformat()


class TestConsentWithdrawnError:
    """Tests for ConsentWithdrawnError."""

    def test_initialization(self):
        """Test ConsentWithdrawnError initialization."""
        subject_id = uuid4()
        withdrawn_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        exc = ConsentWithdrawnError(
            subject_id=subject_id, scope="background_check", withdrawn_at=withdrawn_at
        )

        assert exc.subject_id == subject_id
        assert exc.scope == "background_check"
        assert exc.withdrawn_at == withdrawn_at
        assert exc.regulation == "GDPR Article 7(3)"
        assert "withdrawn" in exc.message.lower()

    def test_inherits_from_consent_violation(self):
        """Test ConsentWithdrawnError inherits from ConsentViolation."""
        exc = ConsentWithdrawnError(
            subject_id=uuid4(),
            scope="test",
            withdrawn_at=datetime.now(UTC),
        )

        assert isinstance(exc, ConsentViolation)


# =============================================================================
# Timing Domain Exception Tests
# =============================================================================


class TestWaitingPeriodNotElapsedError:
    """Tests for WaitingPeriodNotElapsedError."""

    def test_initialization(self):
        """Test WaitingPeriodNotElapsedError initialization."""
        notice_id = uuid4()
        exc = WaitingPeriodNotElapsedError(notice_id=notice_id, required_days=5, elapsed_days=2)

        assert exc.notice_id == notice_id
        assert exc.required_days == 5
        assert exc.elapsed_days == 2
        assert exc.regulation == "FCRA Section 1681b(b)(3)"
        assert "2/5 days" in exc.message
        assert "3 days remaining" in exc.message

    def test_inherits_from_timing_violation(self):
        """Test WaitingPeriodNotElapsedError inherits from TimingViolation."""
        exc = WaitingPeriodNotElapsedError(notice_id=uuid4(), required_days=5, elapsed_days=2)

        assert isinstance(exc, TimingViolation)
        assert isinstance(exc, InvariantViolation)

    def test_context_contains_remaining_days(self):
        """Test context contains calculated remaining days."""
        exc = WaitingPeriodNotElapsedError(notice_id=uuid4(), required_days=10, elapsed_days=3)

        assert exc.context["remaining_days"] == 7
        assert exc.context["required_days"] == 10
        assert exc.context["elapsed_days"] == 3


class TestNoticePrecedenceError:
    """Tests for NoticePrecedenceError."""

    def test_initialization(self):
        """Test NoticePrecedenceError initialization."""
        exc = NoticePrecedenceError(
            action_type="adverse_action",
            notice_required="pre_adverse_action",
            notice_status="not_sent",
        )

        assert exc.action_type == "adverse_action"
        assert exc.notice_required == "pre_adverse_action"
        assert exc.notice_status == "not_sent"
        assert exc.regulation == "FCRA Section 1681m"

    def test_inherits_from_timing_violation(self):
        """Test NoticePrecedenceError inherits from TimingViolation."""
        exc = NoticePrecedenceError(
            action_type="test", notice_required="test", notice_status="pending"
        )

        assert isinstance(exc, TimingViolation)


class TestEvidenceStaleError:
    """Tests for EvidenceStaleError."""

    def test_initialization(self):
        """Test EvidenceStaleError initialization."""
        evidence_id = uuid4()
        exc = EvidenceStaleError(evidence_id=evidence_id, max_age_hours=24, actual_age_hours=48)

        assert exc.evidence_id == evidence_id
        assert exc.max_age_hours == 24
        assert exc.actual_age_hours == 48
        assert exc.regulation == "SOC 2 CC4.1"
        assert "48h old" in exc.message
        assert "max allowed: 24h" in exc.message

    def test_inherits_from_timing_violation(self):
        """Test EvidenceStaleError inherits from TimingViolation."""
        exc = EvidenceStaleError(evidence_id=uuid4(), max_age_hours=24, actual_age_hours=48)

        assert isinstance(exc, TimingViolation)


# =============================================================================
# Authorization Domain Exception Tests
# =============================================================================


class TestSoDViolationError:
    """Tests for SoDViolationError."""

    def test_initialization(self):
        """Test SoDViolationError initialization."""
        identity_id = uuid4()
        exc = SoDViolationError(identity_id=identity_id, role_a="preparer", role_b="approver")

        assert exc.identity_id == identity_id
        assert exc.role_a == "preparer"
        assert exc.role_b == "approver"
        assert exc.regulation == "SOX Section 404"
        assert "preparer" in exc.message
        assert "approver" in exc.message

    def test_inherits_from_authorization_violation(self):
        """Test SoDViolationError inherits from AuthorizationViolation."""
        exc = SoDViolationError(identity_id=uuid4(), role_a="a", role_b="b")

        assert isinstance(exc, AuthorizationViolation)
        assert isinstance(exc, InvariantViolation)


class TestDualApprovalMissingError:
    """Tests for DualApprovalMissingError."""

    def test_initialization(self):
        """Test DualApprovalMissingError initialization."""
        exc = DualApprovalMissingError(
            action_type="high_risk_operation",
            approvals_present=1,
            approvals_required=2,
        )

        assert exc.action_type == "high_risk_operation"
        assert exc.approvals_present == 1
        assert exc.approvals_required == 2
        assert exc.regulation == "SOX Section 302"
        assert "requires 2 approvals" in exc.message
        assert "found: 1" in exc.message

    def test_default_required_approvals(self):
        """Test default approvals_required is 2."""
        exc = DualApprovalMissingError(action_type="test", approvals_present=0)

        assert exc.approvals_required == 2

    def test_inherits_from_authorization_violation(self):
        """Test DualApprovalMissingError inherits from AuthorizationViolation."""
        exc = DualApprovalMissingError(action_type="test", approvals_present=0)

        assert isinstance(exc, AuthorizationViolation)


class TestClearanceInsufficientError:
    """Tests for ClearanceInsufficientError."""

    def test_initialization(self):
        """Test ClearanceInsufficientError initialization."""
        actor_id = uuid4()
        exc = ClearanceInsufficientError(
            actor_id=actor_id,
            required_level="confidential",
            actual_level="internal",
        )

        assert exc.actor_id == actor_id
        assert exc.required_level == "confidential"
        assert exc.actual_level == "internal"
        assert exc.regulation == "PCI DSS 7.1"

    def test_inherits_from_authorization_violation(self):
        """Test ClearanceInsufficientError inherits from AuthorizationViolation."""
        exc = ClearanceInsufficientError(
            actor_id=uuid4(), required_level="high", actual_level="low"
        )

        assert isinstance(exc, AuthorizationViolation)


# =============================================================================
# Evidence Domain Exception Tests
# =============================================================================


class TestEvidenceNotBoundError:
    """Tests for EvidenceNotBoundError."""

    def test_initialization(self):
        """Test EvidenceNotBoundError initialization."""
        decision_id = uuid4()
        exc = EvidenceNotBoundError(decision_id=decision_id, evidence_type="cep")

        assert exc.decision_id == decision_id
        assert exc.evidence_type == "cep"
        assert exc.regulation == "SOX Section 802"
        assert "cep" in exc.message

    def test_inherits_from_evidence_violation(self):
        """Test EvidenceNotBoundError inherits from EvidenceViolation."""
        exc = EvidenceNotBoundError(decision_id=uuid4(), evidence_type="attestation")

        assert isinstance(exc, EvidenceViolation)
        assert isinstance(exc, InvariantViolation)


class TestChainBrokenError:
    """Tests for ChainBrokenError."""

    def test_initialization(self):
        """Test ChainBrokenError initialization."""
        chain_id = uuid4()
        break_point = uuid4()
        exc = ChainBrokenError(
            chain_id=chain_id,
            break_point=break_point,
            expected_hash="abc123def456",
            actual_hash="xyz789uvw012",
        )

        assert exc.chain_id == chain_id
        assert exc.break_point == break_point
        assert exc.expected_hash == "abc123def456"
        assert exc.actual_hash == "xyz789uvw012"
        assert exc.regulation == "FRCP Rule 37(e)"
        assert "hash mismatch" in exc.message

    def test_inherits_from_evidence_violation(self):
        """Test ChainBrokenError inherits from EvidenceViolation."""
        exc = ChainBrokenError(
            chain_id=uuid4(),
            break_point=uuid4(),
            expected_hash="a",
            actual_hash="b",
        )

        assert isinstance(exc, EvidenceViolation)


class TestHashMismatchError:
    """Tests for HashMismatchError."""

    def test_initialization(self):
        """Test HashMismatchError initialization."""
        entity_id = uuid4()
        exc = HashMismatchError(
            entity_id=entity_id,
            entity_type="document",
            expected_hash="abc123",
            actual_hash="def456",
        )

        assert exc.entity_id == entity_id
        assert exc.entity_type == "document"
        assert exc.expected_hash == "abc123"
        assert exc.actual_hash == "def456"
        assert exc.regulation == "ISO 27001 A.12.4.1"

    def test_inherits_from_evidence_violation(self):
        """Test HashMismatchError inherits from EvidenceViolation."""
        exc = HashMismatchError(
            entity_id=uuid4(),
            entity_type="test",
            expected_hash="a",
            actual_hash="b",
        )

        assert isinstance(exc, EvidenceViolation)


class TestCEPNotSealedError:
    """Tests for CEPNotSealedError."""

    def test_initialization(self):
        """Test CEPNotSealedError initialization."""
        cep_id = uuid4()
        exc = CEPNotSealedError(cep_id=cep_id, current_status="DRAFT")

        assert exc.cep_id == cep_id
        assert exc.current_status == "DRAFT"
        assert exc.regulation == "FCRA Section 1681m"
        assert "DRAFT" in exc.message
        assert "must be SEALED" in exc.message

    def test_inherits_from_evidence_violation(self):
        """Test CEPNotSealedError inherits from EvidenceViolation."""
        exc = CEPNotSealedError(cep_id=uuid4(), current_status="DRAFT")

        assert isinstance(exc, EvidenceViolation)


# =============================================================================
# Data Protection Domain Exception Tests
# =============================================================================


class TestPIIPublicExposureError:
    """Tests for PIIPublicExposureError."""

    def test_initialization(self):
        """Test PIIPublicExposureError initialization."""
        exc = PIIPublicExposureError(data_classification="PII", target_audience="public")

        assert exc.data_classification == "PII"
        assert exc.target_audience == "public"
        assert exc.regulation == "GDPR Article 5(1)(f)"

    def test_inherits_from_data_protection_violation(self):
        """Test PIIPublicExposureError inherits from DataProtectionViolation."""
        exc = PIIPublicExposureError(data_classification="PII", target_audience="public")

        assert isinstance(exc, DataProtectionViolation)
        assert isinstance(exc, InvariantViolation)


class TestPIIExposureError:
    """Tests for PIIExposureError."""

    def test_initialization(self):
        """Test PIIExposureError initialization."""
        exc = PIIExposureError(visibility="public", contains_pii=True)

        assert exc.visibility == "public"
        assert exc.contains_pii is True
        assert exc.regulation == "GDPR Article 5"

    def test_inherits_from_data_protection_violation(self):
        """Test PIIExposureError inherits from DataProtectionViolation."""
        exc = PIIExposureError(visibility="public", contains_pii=True)

        assert isinstance(exc, DataProtectionViolation)


class TestEncryptionMissingError:
    """Tests for EncryptionMissingError."""

    def test_initialization_with_actual_standard(self):
        """Test EncryptionMissingError with actual standard provided."""
        exc = EncryptionMissingError(
            channel="api",
            required_standard="TLS 1.3",
            actual_standard="TLS 1.1",
        )

        assert exc.channel == "api"
        assert exc.required_standard == "TLS 1.3"
        assert exc.actual_standard == "TLS 1.1"
        assert exc.regulation == "GDPR Article 32"
        assert "found: TLS 1.1" in exc.message

    def test_initialization_without_actual_standard(self):
        """Test EncryptionMissingError without actual standard."""
        exc = EncryptionMissingError(channel="webhook", required_standard="TLS 1.2")

        assert exc.actual_standard is None
        assert "none found" in exc.message

    def test_inherits_from_data_protection_violation(self):
        """Test EncryptionMissingError inherits from DataProtectionViolation."""
        exc = EncryptionMissingError(channel="test", required_standard="TLS")

        assert isinstance(exc, DataProtectionViolation)


class TestUnencryptedTransmissionError:
    """Tests for UnencryptedTransmissionError."""

    def test_initialization(self):
        """Test UnencryptedTransmissionError initialization."""
        exc = UnencryptedTransmissionError(is_encrypted=False, data_classification="confidential")

        assert exc.is_encrypted is False
        assert exc.data_classification == "confidential"
        assert exc.regulation == "GDPR Article 32"

    def test_inherits_from_data_protection_violation(self):
        """Test UnencryptedTransmissionError inherits from DataProtectionViolation."""
        exc = UnencryptedTransmissionError(is_encrypted=False, data_classification="pii")

        assert isinstance(exc, DataProtectionViolation)


class TestClassificationViolationError:
    """Tests for ClassificationViolationError."""

    def test_initialization(self):
        """Test ClassificationViolationError initialization."""
        allowed_ops = {"read", "write"}
        exc = ClassificationViolationError(
            classification="restricted",
            operation="export",
            allowed_operations=allowed_ops,
        )

        assert exc.classification == "restricted"
        assert exc.operation == "export"
        assert exc.allowed_operations == allowed_ops
        assert exc.regulation == "SOC 2 CC6.1"
        assert "export" in exc.message
        assert "restricted" in exc.message

    def test_inherits_from_data_protection_violation(self):
        """Test ClassificationViolationError inherits from DataProtectionViolation."""
        exc = ClassificationViolationError(
            classification="c", operation="o", allowed_operations=set()
        )

        assert isinstance(exc, DataProtectionViolation)


class TestRetentionExceededError:
    """Tests for RetentionExceededError."""

    def test_initialization(self):
        """Test RetentionExceededError initialization."""
        retention_end = datetime(2024, 1, 1, tzinfo=UTC)
        current_time = datetime(2024, 2, 1, tzinfo=UTC)
        exc = RetentionExceededError(retention_end=retention_end, current_time=current_time)

        assert exc.retention_end == retention_end
        assert exc.current_time == current_time
        assert exc.regulation == "GDPR Article 5(1)(e)"
        assert "exceeded" in exc.message.lower()

    def test_context_contains_exceeded_by_seconds(self):
        """Test context contains exceeded_by_seconds."""
        retention_end = datetime(2024, 1, 1, tzinfo=UTC)
        current_time = datetime(2024, 1, 2, tzinfo=UTC)  # 1 day later
        exc = RetentionExceededError(retention_end=retention_end, current_time=current_time)

        # 1 day = 86400 seconds
        assert exc.context["exceeded_by_seconds"] == 86400

    def test_inherits_from_data_protection_violation(self):
        """Test RetentionExceededError inherits from DataProtectionViolation."""
        exc = RetentionExceededError(
            retention_end=datetime.now(UTC),
            current_time=datetime.now(UTC),
        )

        assert isinstance(exc, DataProtectionViolation)


# =============================================================================
# AI Governance Domain Exception Tests
# =============================================================================


class TestHumanReviewMissingError:
    """Tests for HumanReviewMissingError."""

    def test_initialization(self):
        """Test HumanReviewMissingError initialization."""
        decision_id = uuid4()
        exc = HumanReviewMissingError(decision_id=decision_id, risk_level="high")

        assert exc.decision_id == decision_id
        assert exc.risk_level == "high"
        assert exc.regulation == "EU AI Act Article 14"
        assert "human review" in exc.message.lower()
        assert "high" in exc.message

    def test_inherits_from_ai_governance_violation(self):
        """Test HumanReviewMissingError inherits from AIGovernanceViolation."""
        exc = HumanReviewMissingError(decision_id=uuid4(), risk_level="medium")

        assert isinstance(exc, AIGovernanceViolation)
        assert isinstance(exc, InvariantViolation)


class TestBiasAssessmentMissingError:
    """Tests for BiasAssessmentMissingError."""

    def test_initialization(self):
        """Test BiasAssessmentMissingError initialization."""
        tool_id = uuid4()
        exc = BiasAssessmentMissingError(tool_id=tool_id, assessment_type="disparate_impact")

        assert exc.tool_id == tool_id
        assert exc.assessment_type == "disparate_impact"
        assert exc.regulation == "NYC LL144"
        assert "bias assessment" in exc.message.lower()

    def test_inherits_from_ai_governance_violation(self):
        """Test BiasAssessmentMissingError inherits from AIGovernanceViolation."""
        exc = BiasAssessmentMissingError(tool_id=uuid4(), assessment_type="audit")

        assert isinstance(exc, AIGovernanceViolation)


class TestToolConfigMismatchError:
    """Tests for ToolConfigMismatchError."""

    def test_initialization(self):
        """Test ToolConfigMismatchError initialization."""
        tool_id = uuid4()
        exc = ToolConfigMismatchError(
            tool_id=tool_id,
            expected_config_hash="abc123def456",
            actual_config_hash="xyz789uvw012",
        )

        assert exc.tool_id == tool_id
        assert exc.expected_config_hash == "abc123def456"
        assert exc.actual_config_hash == "xyz789uvw012"
        assert exc.regulation == "NYC LL144"
        assert "configuration changed" in exc.message.lower()

    def test_inherits_from_ai_governance_violation(self):
        """Test ToolConfigMismatchError inherits from AIGovernanceViolation."""
        exc = ToolConfigMismatchError(
            tool_id=uuid4(),
            expected_config_hash="a",
            actual_config_hash="b",
        )

        assert isinstance(exc, AIGovernanceViolation)


class TestDisclosureMissingError:
    """Tests for DisclosureMissingError."""

    def test_initialization(self):
        """Test DisclosureMissingError initialization."""
        exc = DisclosureMissingError(action_type="aedt_screening", disclosure_status="not_provided")

        assert exc.action_type == "aedt_screening"
        assert exc.disclosure_status == "not_provided"
        assert exc.regulation == "NYC LL144 Section 20-871(b)"
        assert "disclosure" in exc.message.lower()

    def test_inherits_from_ai_governance_violation(self):
        """Test DisclosureMissingError inherits from AIGovernanceViolation."""
        exc = DisclosureMissingError(action_type="test", disclosure_status="pending")

        assert isinstance(exc, AIGovernanceViolation)


# =============================================================================
# Comprehensive Inheritance Tests
# =============================================================================


class TestCompleteInheritanceHierarchy:
    """Tests verifying complete inheritance hierarchy."""

    @pytest.mark.parametrize(
        "exc_cls,expected_category",
        [
            # Consent domain
            (ConsentNotValidError, ConsentViolation),
            (ConsentExpiredError, ConsentViolation),
            (ConsentWithdrawnError, ConsentViolation),
            # Timing domain
            (WaitingPeriodNotElapsedError, TimingViolation),
            (NoticePrecedenceError, TimingViolation),
            (EvidenceStaleError, TimingViolation),
            # Authorization domain
            (SoDViolationError, AuthorizationViolation),
            (DualApprovalMissingError, AuthorizationViolation),
            (ClearanceInsufficientError, AuthorizationViolation),
            # Evidence domain
            (EvidenceNotBoundError, EvidenceViolation),
            (ChainBrokenError, EvidenceViolation),
            (HashMismatchError, EvidenceViolation),
            (CEPNotSealedError, EvidenceViolation),
            # Data protection domain
            (PIIPublicExposureError, DataProtectionViolation),
            (PIIExposureError, DataProtectionViolation),
            (EncryptionMissingError, DataProtectionViolation),
            (UnencryptedTransmissionError, DataProtectionViolation),
            (ClassificationViolationError, DataProtectionViolation),
            (RetentionExceededError, DataProtectionViolation),
            # AI governance domain
            (HumanReviewMissingError, AIGovernanceViolation),
            (BiasAssessmentMissingError, AIGovernanceViolation),
            (ToolConfigMismatchError, AIGovernanceViolation),
            (DisclosureMissingError, AIGovernanceViolation),
        ],
    )
    def test_exception_inherits_from_correct_category(self, exc_cls, expected_category):
        """Test each exception inherits from its correct category."""
        assert issubclass(exc_cls, expected_category)
        assert issubclass(exc_cls, InvariantViolation)
        assert issubclass(exc_cls, Exception)
