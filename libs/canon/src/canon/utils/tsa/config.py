# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""TSA provider presets."""

from __future__ import annotations

from .types import TSAConfig

__all__ = ["TSA_PRESETS", "TSAConfig"]


TSA_PRESETS: dict[str, TSAConfig] = {
    "digicert": TSAConfig(
        url="http://timestamp.digicert.com",
        name="DigiCert Timestamp",
        auth_type="none",
        timeout_seconds=30.0,
        retry_count=3,
    ),
    "entrust": TSAConfig(
        url="http://timestamp.entrust.net/TSS/RFC3161sha2TS",
        name="Entrust Timestamp",
        auth_type="none",
        timeout_seconds=30.0,
        retry_count=3,
    ),
    "sectigo": TSAConfig(
        url="http://timestamp.sectigo.com",
        name="Sectigo Timestamp",
        auth_type="none",
        timeout_seconds=30.0,
        retry_count=3,
    ),
    "globalsign": TSAConfig(
        url="http://timestamp.globalsign.com/tsa/r6advanced1",
        name="GlobalSign Timestamp",
        auth_type="none",
        timeout_seconds=30.0,
        retry_count=3,
    ),
    "freetsa": TSAConfig(
        url="https://freetsa.org/tsr",
        name="FreeTSA (Testing Only)",
        auth_type="none",
        timeout_seconds=60.0,  # FreeTSA can be slow
        retry_count=5,
    ),
}
