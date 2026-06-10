"""Authenticator Assurance Level types.

NIST SP 800-63B defines AAL levels for authentication strength.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["AALLevel"]

AALLevel = Literal["aal1", "aal2", "aal3"]
"""NIST SP 800-63B Authenticator Assurance Levels.

- aal1: Single-factor authentication (password)
- aal2: Two-factor authentication (MFA)
- aal3: Hardware-bound authentication (FIDO2/PIV)
"""
