"""Export control domain exceptions.

WARNING: Export control violations carry CRIMINAL penalties up to
$1M fine and 20 years imprisonment. These exceptions represent
serious regulatory violations.

These exceptions are raised by export control phrases when invariants
are violated. All inherit from ExportControlViolation.

Regulatory context:
    - OFAC (Office of Foreign Assets Control) - Treasury Department
    - BIS (Bureau of Industry and Security) - Commerce Department
    - DDTC (Directorate of Defense Trade Controls) - State Department
    - EAR (Export Administration Regulations) - 15 CFR Parts 730-774
    - ITAR (International Traffic in Arms Regulations) - 22 CFR Parts 120-130
"""

from __future__ import annotations

from typing import Any

from canon.enforcement.exceptions import InvariantViolation

__all__ = [
    "BISLicenseRequiredError",
    "ExportControlViolation",
    "ITARAuthorizationRequiredError",
    "OFACSanctionsMatchError",
    "ProhibitedDestinationError",
]


class ExportControlViolation(InvariantViolation):
    """Export control invariant violations.

    Covers violations of export control requirements under:
    - OFAC sanctions programs (31 CFR Parts 500-599)
    - EAR (15 CFR Parts 730-774)
    - ITAR (22 CFR Parts 120-130)

    WARNING: Export control violations may result in:
    - Criminal penalties up to $1M and 20 years imprisonment
    - Civil penalties up to $330,000 per violation
    - Debarment from government contracting
    """

    default_regulation = "OFAC/EAR/ITAR"
    default_message = "Export control violation"


class ProhibitedDestinationError(ExportControlViolation):
    """Export to comprehensively sanctioned destination is prohibited.

    Raised when: require_allowed_destination finds destination is
    under comprehensive US sanctions (Cuba, Iran, North Korea, Syria).

    This is a HARD DENIAL - NO exports permitted regardless of
    licenses or exemptions.

    Regulatory basis:
    - OFAC Comprehensive Sanctions Programs
    - 31 CFR Parts 510 (DPRK), 515 (Cuba), 542 (Syria), 560 (Iran)

    Phrase: destination_must_not_be_prohibited
    """

    default_regulation = "OFAC Comprehensive Sanctions"
    default_message = "Export to prohibited destination denied"

    __slots__ = ("country_code", "country_name", "prohibition_basis")

    def __init__(
        self,
        country_code: str,
        country_name: str | None = None,
        prohibition_basis: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize prohibited destination error.

        Args:
            country_code: ISO-3166-1 alpha-2 country code.
            country_name: Human-readable country name.
            prohibition_basis: Legal basis (CFR reference).
            **kwargs: Additional arguments passed to parent.
        """
        self.country_code = country_code
        self.country_name = country_name
        self.prohibition_basis = prohibition_basis

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "country_code": country_code,
            "country_name": country_name,
            "prohibition_basis": prohibition_basis,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(
            f"Export to {country_name or country_code} prohibited under {prohibition_basis or 'OFAC sanctions'}",
            context=merged_context,
            regulation=prohibition_basis or self.default_regulation,
            **kwargs,
        )


class OFACSanctionsMatchError(ExportControlViolation):
    """Entity matched against OFAC sanctions list.

    Raised when: verify_ofac_clearance finds a match against
    SDN (Specially Designated Nationals) or other sanctions lists.

    Regulatory basis:
    - OFAC SDN List (50 U.S.C. 1702)
    - Sectoral Sanctions Identifications List
    - Criminal penalties: Up to $1M and 20 years imprisonment

    Phrase: ofac_must_be_cleared
    """

    default_regulation = "OFAC SDN List (50 U.S.C. 1702)"
    default_message = "OFAC sanctions match detected"

    __slots__ = (
        "entity_name",
        "entity_type",
        "match_score",
        "matched_program",
        "matched_sdn_id",
    )

    def __init__(
        self,
        entity_name: str,
        entity_type: str,
        matched_program: str | None = None,
        matched_sdn_id: str | None = None,
        match_score: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize OFAC sanctions match error.

        Args:
            entity_name: Name of entity that matched.
            entity_type: Type of entity (INDIVIDUAL, ENTITY, etc.).
            matched_program: Sanctions program (e.g., "IRAN", "CUBA").
            matched_sdn_id: SDN entry ID if matched.
            match_score: Fuzzy match score (0-100).
            **kwargs: Additional arguments passed to parent.
        """
        self.entity_name = entity_name
        self.entity_type = entity_type
        self.matched_program = matched_program
        self.matched_sdn_id = matched_sdn_id
        self.match_score = match_score

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "matched_program": matched_program,
            "matched_sdn_id": matched_sdn_id,
            "match_score": match_score,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(
            f"OFAC sanctions match: {entity_name} ({entity_type}) - program: {matched_program or 'unknown'}",
            context=merged_context,
            **kwargs,
        )


class BISLicenseRequiredError(ExportControlViolation):
    """BIS export license required but not present.

    Raised when: verify_bis_approval finds controlled ECCN item
    requires license for destination but no valid license exists.

    Regulatory basis:
    - Export Administration Regulations (15 CFR Parts 730-774)
    - Commerce Control List (CCL)
    - License exceptions (Part 740)

    Phrase: bis_license_must_be_valid
    """

    default_regulation = "EAR (15 CFR Parts 730-774)"
    default_message = "BIS export license required"

    __slots__ = ("destination_country", "eccn", "end_use", "end_user")

    def __init__(
        self,
        eccn: str,
        destination_country: str,
        end_use: str | None = None,
        end_user: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize BIS license required error.

        Args:
            eccn: Export Control Classification Number.
            destination_country: Destination country code.
            end_use: Intended end use.
            end_user: End user name.
            **kwargs: Additional arguments passed to parent.
        """
        self.eccn = eccn
        self.destination_country = destination_country
        self.end_use = end_use
        self.end_user = end_user

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "eccn": eccn,
            "destination_country": destination_country,
            "end_use": end_use,
            "end_user": end_user,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(
            f"BIS license required for ECCN {eccn} to {destination_country}",
            context=merged_context,
            **kwargs,
        )


class ITARAuthorizationRequiredError(ExportControlViolation):
    """ITAR authorization required but not present.

    Raised when: verify_itar_authorization finds USML-controlled
    item requires State Department authorization but none exists.

    Regulatory basis:
    - ITAR (22 CFR Parts 120-130)
    - US Munitions List (USML)
    - Criminal penalties for unauthorized defense exports

    Phrase: itar_must_be_authorized
    """

    default_regulation = "ITAR (22 CFR Parts 120-130)"
    default_message = "ITAR authorization required"

    __slots__ = (
        "defense_service",
        "destination_country",
        "technical_data",
        "usml_category",
    )

    def __init__(
        self,
        usml_category: str,
        destination_country: str,
        defense_service: bool = False,
        technical_data: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize ITAR authorization required error.

        Args:
            usml_category: USML category (I-XXI).
            destination_country: Destination country code.
            defense_service: True if defense service export.
            technical_data: True if technical data export.
            **kwargs: Additional arguments passed to parent.
        """
        self.usml_category = usml_category
        self.destination_country = destination_country
        self.defense_service = defense_service
        self.technical_data = technical_data

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "usml_category": usml_category,
            "destination_country": destination_country,
            "defense_service": defense_service,
            "technical_data": technical_data,
        }
        merged_context = {**base_context, **extra_context}

        export_type = []
        if defense_service:
            export_type.append("defense service")
        if technical_data:
            export_type.append("technical data")
        type_desc = " and ".join(export_type) if export_type else "defense article"

        super().__init__(
            f"ITAR authorization required for USML {usml_category} {type_desc} to {destination_country}",
            context=merged_context,
            **kwargs,
        )
