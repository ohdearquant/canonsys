"""Redaction domain exceptions.

These exceptions are raised when PII-related invariants are violated.
All inherit from DataProtectionViolation (from enforcement.exceptions).
"""

from __future__ import annotations

from typing import Any

from canon.enforcement.exceptions import DataProtectionViolation

from .types import PIICategory

__all__ = [
    "BlockingPIIDetectedError",
    "InvalidCategoryError",
    "PIIDetectionError",
    "RedactionError",
    "RedactionModelError",
    "SegmentationError",
]


class RedactionError(DataProtectionViolation):
    """Base exception for all redaction domain errors.

    Represents failures during PII detection, redaction, or segmentation
    operations.
    """

    default_regulation = "GDPR Article 5(1)(f)"
    default_message = "Redaction operation failed"


class PIIDetectionError(RedactionError):
    """PII detection operation failed.

    Raised when: The PII detection system cannot complete its analysis,
    either due to model failures or invalid input.

    Note: This is NOT raised when PII is detected (that's expected behavior).
    This is raised when the detection PROCESS fails.
    """

    default_message = "PII detection failed"

    __slots__ = ("reason",)

    def __init__(
        self,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """Initialize PII detection error.

        Args:
            reason: Why detection failed.
            **kwargs: Additional arguments passed to parent.
        """
        self.reason = reason
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"reason": reason}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"PII detection failed: {reason}",
            context=merged_context,
            **kwargs,
        )


class SegmentationError(RedactionError):
    """Text segmentation operation failed.

    Raised when: The LLM-based segmentation cannot identify speaker
    boundaries in the input text.
    """

    default_message = "Text segmentation failed"

    __slots__ = ("reason",)

    def __init__(
        self,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """Initialize segmentation error.

        Args:
            reason: Why segmentation failed.
            **kwargs: Additional arguments passed to parent.
        """
        self.reason = reason
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"reason": reason}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Text segmentation failed: {reason}",
            context=merged_context,
            **kwargs,
        )


class InvalidCategoryError(RedactionError):
    """Invalid PII category specified.

    Raised when: A PII category string does not match any known category.
    """

    default_message = "Invalid PII category"

    __slots__ = ("category_value",)

    def __init__(
        self,
        category_value: str,
        **kwargs: Any,
    ) -> None:
        """Initialize invalid category error.

        Args:
            category_value: The invalid category string.
            **kwargs: Additional arguments passed to parent.
        """
        self.category_value = category_value
        valid_categories = [c.value for c in PIICategory]
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "category_value": category_value,
            "valid_categories": valid_categories,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Invalid PII category: '{category_value}'. Valid categories: {valid_categories}",
            context=merged_context,
            **kwargs,
        )


class BlockingPIIDetectedError(RedactionError):
    """Highly sensitive PII detected - blocks persistence.

    Raised when: The regex-based safety gate detects highly sensitive
    PII (SSN, credit card, passport) that must NEVER be persisted.

    This is a HARD BLOCK - the operation cannot proceed until the
    PII is removed or redacted.

    Regulatory basis:
    - NIST SP 800-122: PII handling requirements
    - PCI DSS: Cardholder data protection
    - State data breach laws: SSN protection
    """

    default_regulation = "NIST SP 800-122"
    default_message = "Blocking PII detected - cannot persist"

    __slots__ = ("categories_detected", "detection_count")

    def __init__(
        self,
        categories_detected: list[PIICategory],
        detection_count: int,
        **kwargs: Any,
    ) -> None:
        """Initialize blocking PII detected error.

        Args:
            categories_detected: List of highly sensitive PII categories found.
            detection_count: Total number of detections.
            **kwargs: Additional arguments passed to parent.
        """
        self.categories_detected = categories_detected
        self.detection_count = detection_count
        cat_names = [c.value for c in categories_detected]
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "categories_detected": cat_names,
            "detection_count": detection_count,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Blocking PII detected: {', '.join(set(cat_names))} "
            f"({detection_count} occurrences). Cannot persist data.",
            context=merged_context,
            **kwargs,
        )


class RedactionModelError(RedactionError):
    """LLM model invocation failed during redaction.

    Raised when: The LLM used for semantic PII detection fails to respond
    or returns invalid output after all retry attempts.
    """

    default_message = "Redaction model invocation failed"

    __slots__ = ("attempts", "last_error", "model_name")

    def __init__(
        self,
        model_name: str,
        attempts: int,
        last_error: str,
        **kwargs: Any,
    ) -> None:
        """Initialize redaction model error.

        Args:
            model_name: Name of the model that failed.
            attempts: Number of retry attempts made.
            last_error: The last error message received.
            **kwargs: Additional arguments passed to parent.
        """
        self.model_name = model_name
        self.attempts = attempts
        self.last_error = last_error
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "model_name": model_name,
            "attempts": attempts,
            "last_error": last_error,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Model '{model_name}' failed after {attempts} attempts: {last_error}",
            context=merged_context,
            **kwargs,
        )
