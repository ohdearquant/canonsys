"""Justification domain phrases.

All justification operations in one place:
- Classification: classify_justification
- Mapping: map_reason_code_to_evidence, map_waiver_reason_to_evidence, require_type_specific_evidence
- Validation: validate_business_justification
- Gate: require_justification_documented
"""

from .classify_justification import ClassifyJustificationSpecs, classify_justification
from .map_reason_code_to_evidence import MapReasonCodeSpecs, map_reason_code_to_evidence
from .map_waiver_reason_to_evidence import (
    MapWaiverReasonSpecs,
    map_waiver_reason_to_evidence,
)
from .require_justification_documented import (
    RequireJustificationDocumentedSpecs,
    require_justification_documented,
)
from .require_type_specific_evidence import (
    RequireTypeSpecificEvidenceSpecs,
    require_type_specific_evidence,
)
from .validate_business_justification import (
    ValidateBusinessJustificationSpecs,
    validate_business_justification,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "ClassifyJustificationSpecs",
    "MapReasonCodeSpecs",
    "MapWaiverReasonSpecs",
    "RequireJustificationDocumentedSpecs",
    "RequireTypeSpecificEvidenceSpecs",
    "ValidateBusinessJustificationSpecs",
    # Phrase functions
    "classify_justification",
    "map_reason_code_to_evidence",
    "map_waiver_reason_to_evidence",
    "require_justification_documented",
    "require_type_specific_evidence",
    "validate_business_justification",
]
