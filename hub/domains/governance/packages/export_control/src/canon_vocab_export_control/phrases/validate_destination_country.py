"""ISO-3166-1 country code validation for export control.

Validates and normalizes destination country codes to ensure
consistent handling across all export control operations.

Compliance Context:
    - BIS/EAR requires accurate country identification for license determination
    - OFAC sanctions lists use ISO-3166-1 alpha-2 codes
    - ITAR destination tracking requires standardized country codes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import PROHIBITED_DESTINATIONS

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ValidateDestinationSpecs", "validate_destination_country"]


# ISO-3166-1 alpha-2 country codes (complete list)
# Source: https://www.iso.org/iso-3166-country-codes.html
ISO_3166_1_ALPHA_2: frozenset[str] = frozenset(
    {
        # A
        "AD",
        "AE",
        "AF",
        "AG",
        "AI",
        "AL",
        "AM",
        "AO",
        "AQ",
        "AR",
        "AS",
        "AT",
        "AU",
        "AW",
        "AX",
        "AZ",
        # B
        "BA",
        "BB",
        "BD",
        "BE",
        "BF",
        "BG",
        "BH",
        "BI",
        "BJ",
        "BL",
        "BM",
        "BN",
        "BO",
        "BQ",
        "BR",
        "BS",
        "BT",
        "BV",
        "BW",
        "BY",
        "BZ",
        # C
        "CA",
        "CC",
        "CD",
        "CF",
        "CG",
        "CH",
        "CI",
        "CK",
        "CL",
        "CM",
        "CN",
        "CO",
        "CR",
        "CU",
        "CV",
        "CW",
        "CX",
        "CY",
        "CZ",
        # D
        "DE",
        "DJ",
        "DK",
        "DM",
        "DO",
        "DZ",
        # E
        "EC",
        "EE",
        "EG",
        "EH",
        "ER",
        "ES",
        "ET",
        # F
        "FI",
        "FJ",
        "FK",
        "FM",
        "FO",
        "FR",
        # G
        "GA",
        "GB",
        "GD",
        "GE",
        "GF",
        "GG",
        "GH",
        "GI",
        "GL",
        "GM",
        "GN",
        "GP",
        "GQ",
        "GR",
        "GS",
        "GT",
        "GU",
        "GW",
        "GY",
        # H
        "HK",
        "HM",
        "HN",
        "HR",
        "HT",
        "HU",
        # I
        "ID",
        "IE",
        "IL",
        "IM",
        "IN",
        "IO",
        "IQ",
        "IR",
        "IS",
        "IT",
        # J
        "JE",
        "JM",
        "JO",
        "JP",
        # K
        "KE",
        "KG",
        "KH",
        "KI",
        "KM",
        "KN",
        "KP",
        "KR",
        "KW",
        "KY",
        "KZ",
        # L
        "LA",
        "LB",
        "LC",
        "LI",
        "LK",
        "LR",
        "LS",
        "LT",
        "LU",
        "LV",
        "LY",
        # M
        "MA",
        "MC",
        "MD",
        "ME",
        "MF",
        "MG",
        "MH",
        "MK",
        "ML",
        "MM",
        "MN",
        "MO",
        "MP",
        "MQ",
        "MR",
        "MS",
        "MT",
        "MU",
        "MV",
        "MW",
        "MX",
        "MY",
        "MZ",
        # N
        "NA",
        "NC",
        "NE",
        "NF",
        "NG",
        "NI",
        "NL",
        "NO",
        "NP",
        "NR",
        "NU",
        "NZ",
        # O
        "OM",
        # P
        "PA",
        "PE",
        "PF",
        "PG",
        "PH",
        "PK",
        "PL",
        "PM",
        "PN",
        "PR",
        "PS",
        "PT",
        "PW",
        "PY",
        # Q
        "QA",
        # R
        "RE",
        "RO",
        "RS",
        "RU",
        "RW",
        # S
        "SA",
        "SB",
        "SC",
        "SD",
        "SE",
        "SG",
        "SH",
        "SI",
        "SJ",
        "SK",
        "SL",
        "SM",
        "SN",
        "SO",
        "SR",
        "SS",
        "ST",
        "SV",
        "SX",
        "SY",
        "SZ",
        # T
        "TC",
        "TD",
        "TF",
        "TG",
        "TH",
        "TJ",
        "TK",
        "TL",
        "TM",
        "TN",
        "TO",
        "TR",
        "TT",
        "TV",
        "TW",
        "TZ",
        # U
        "UA",
        "UG",
        "UM",
        "US",
        "UY",
        "UZ",
        # V
        "VA",
        "VC",
        "VE",
        "VG",
        "VI",
        "VN",
        "VU",
        # W
        "WF",
        "WS",
        # Y
        "YE",
        "YT",
        # Z
        "ZA",
        "ZM",
        "ZW",
    }
)

# Common aliases and their ISO codes for normalization
COUNTRY_ALIASES: dict[str, str] = {
    # Common name variations
    "USA": "US",
    "UK": "GB",
    "BRITAIN": "GB",
    "ENGLAND": "GB",  # Note: technically incorrect but common
    "KOREA": "KR",  # Assume South Korea unless specified
    "SOUTH KOREA": "KR",
    "NORTH KOREA": "KP",
    "DPRK": "KP",
    "TAIWAN": "TW",
    "HONG KONG": "HK",
    "MACAU": "MO",
    "MACAO": "MO",
    "VIETNAM": "VN",
    "VIET NAM": "VN",
    "IVORY COAST": "CI",
    "COTE D'IVOIRE": "CI",
    "UAE": "AE",
    "RUSSIA": "RU",
    "RUSSIAN FEDERATION": "RU",
    "IRAN": "IR",
    "SYRIA": "SY",
    "SYRIAN ARAB REPUBLIC": "SY",
    "CUBA": "CU",
    "CHINA": "CN",
    "PRC": "CN",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "JAPAN": "JP",
    "INDIA": "IN",
    "BRAZIL": "BR",
    "CANADA": "CA",
    "AUSTRALIA": "AU",
    "MEXICO": "MX",
    "NETHERLANDS": "NL",
    "HOLLAND": "NL",
    "SWITZERLAND": "CH",
    "SINGAPORE": "SG",
    "ISRAEL": "IL",
    "SAUDI ARABIA": "SA",
    "KSA": "SA",
}


class ValidateDestinationSpecs(BaseModel):
    """Specs for destination country validation phrase."""

    # inputs
    country_code: str
    # outputs
    valid: bool = False
    normalized_code: str | None = None
    prohibited: bool = False
    original_input: str = ""


@canon_phrase(
    Operable.from_structure(ValidateDestinationSpecs),
    inputs={"country_code"},
    outputs={"valid", "normalized_code", "prohibited", "original_input"},
)
async def validate_destination_country(
    options: ValidateDestinationSpecs,
    ctx: RequestContext,
) -> dict:
    """Validate and normalize country code to ISO-3166-1 alpha-2.

    Performs:
    1. Normalization (uppercase, strip whitespace)
    2. Alias resolution (USA -> US, UK -> GB, etc.)
    3. ISO-3166-1 alpha-2 validation
    4. Prohibited destination check

    Args:
        options: Validation options containing country_code
        ctx: Request context

    Returns:
        Dict with valid, normalized_code, prohibited, original_input

    Regulatory:
        - BIS/EAR: Accurate country identification required for license determination
        - OFAC: Sanctions lists use ISO-3166-1 alpha-2 codes
        - ITAR: Destination tracking requires standardized country codes

    Example:
        >>> result = await validate_destination_country(options, ctx)
        >>> result["valid"]
        True
        >>> result["normalized_code"]
        'US'
    """
    original = options.country_code
    normalized = options.country_code.upper().strip()

    # Try alias resolution first
    if normalized in COUNTRY_ALIASES:
        normalized = COUNTRY_ALIASES[normalized]

    # Validate against ISO-3166-1 alpha-2
    if normalized not in ISO_3166_1_ALPHA_2:
        return {
            "valid": False,
            "normalized_code": None,
            "prohibited": False,
            "original_input": original,
        }

    # Check if prohibited destination
    is_prohibited = normalized in PROHIBITED_DESTINATIONS

    return {
        "valid": True,
        "normalized_code": normalized,
        "prohibited": is_prohibited,
        "original_input": original,
    }
