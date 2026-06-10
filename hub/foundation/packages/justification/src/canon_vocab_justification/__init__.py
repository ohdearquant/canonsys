"""Justification feature - vertical slice for justification management.

This module provides the complete justification domain implementation:
- Types: JustificationClass, EvidenceRequirement, ReasonEvidenceMapping, WaiverEvidenceMapping
- Phrases: classify_justification, map_reason_code_to_evidence,
           map_waiver_reason_to_evidence, require_type_specific_evidence,
           validate_business_justification
- Exceptions: JustificationNotValidError, JustificationIncompleteError,
              EvidenceRequirementNotMetError

Usage:
    from canon_vocab_justification import (
        # Types
        JustificationClass,
        EvidenceRequirement,
        # Phrases
        classify_justification,
        ClassifyJustificationSpecs,
        map_reason_code_to_evidence,
        MapReasonCodeSpecs,
        validate_business_justification,
        ValidateBusinessJustificationSpecs,
        # Package metadata
        JUSTIFICATION,
    )

Regulatory context:
    - SOX Section 404 (Documentation requirements)
    - Employment law (Termination documentation)
    - Financial regulations (Transaction justification)
    - Transfer pricing regulations (Intercompany documentation)
"""

# Exceptions
from .exceptions import (
    EvidenceRequirementNotMetError,
    JustificationIncompleteError,
    JustificationNotValidError,
)

# Package metadata
from .package import JUSTIFICATION

# Phrases (includes Specs classes and phrase functions)
from .phrases import (  # Specs classes; Phrase functions
    ClassifyJustificationSpecs,
    MapReasonCodeSpecs,
    MapWaiverReasonSpecs,
    RequireTypeSpecificEvidenceSpecs,
    ValidateBusinessJustificationSpecs,
    classify_justification,
    map_reason_code_to_evidence,
    map_waiver_reason_to_evidence,
    require_type_specific_evidence,
    validate_business_justification,
)

# Service
from .service import JustificationService

# Types
from .types import (
    EvidenceRequirement,
    JustificationClass,
    ReasonEvidenceMapping,
    WaiverEvidenceMapping,
)

__all__ = [
    # Package metadata
    "JUSTIFICATION",
    # Specs classes
    "ClassifyJustificationSpecs",
    "MapReasonCodeSpecs",
    "MapWaiverReasonSpecs",
    "RequireTypeSpecificEvidenceSpecs",
    "ValidateBusinessJustificationSpecs",
    # Types
    "EvidenceRequirement",
    "JustificationClass",
    "ReasonEvidenceMapping",
    "WaiverEvidenceMapping",
    # Exceptions
    "EvidenceRequirementNotMetError",
    "JustificationIncompleteError",
    "JustificationNotValidError",
    # Service
    "JustificationService",
    # Phrase functions - Classification
    "classify_justification",
    # Phrase functions - Mapping
    "map_reason_code_to_evidence",
    "map_waiver_reason_to_evidence",
    "require_type_specific_evidence",
    # Phrase functions - Validation
    "validate_business_justification",
]
