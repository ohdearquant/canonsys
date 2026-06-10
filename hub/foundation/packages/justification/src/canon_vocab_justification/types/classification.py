"""Justification classification types."""

from __future__ import annotations

from typing import Literal

__all__ = ("JustificationClass",)


JustificationClass = Literal[
    "legal_requirement",
    "regulatory",
    "business_convenience",
    "cosmetic",
]
