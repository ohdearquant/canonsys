"""Authentication posture types.

NIST SP 800-63B defines authentication posture levels.
"""

from __future__ import annotations

from typing import Literal

__all__ = ["AuthPosture"]

AuthPosture = Literal["none", "basic", "strong", "hardware"]
"""Authentication posture levels per NIST SP 800-63B.

- none: No authentication
- basic: Single factor (password only) - AAL1
- strong: Multi-factor (password + OTP/push) - AAL2
- hardware: Hardware-bound (FIDO2/PIV) - AAL3
"""
