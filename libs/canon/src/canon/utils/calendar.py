"""Business day calculations for regulatory compliance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from kron.utils import now_utc

if TYPE_CHECKING:
    from .loader import JurisdictionRegistry

__all__ = (
    "Calendar",
    "DeadlineRecord",
)


@dataclass(frozen=True, slots=True)
class DeadlineRecord:
    """Audit record for deadline calculations."""

    start: date
    days: int
    result: date
    jurisdiction: str
    holidays_skipped: tuple[date, ...]
    calculated_at: datetime
    rule_id: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["result"] = self.result.isoformat()
        d["holidays_skipped"] = [h.isoformat() for h in self.holidays_skipped]
        d["calculated_at"] = self.calculated_at.isoformat()
        return d


class Calendar:
    """Business day calculator with jurisdiction-specific holidays."""

    def __init__(self, registry: JurisdictionRegistry) -> None:
        self._registry = registry

    def add(self, start: date, days: int, jurisdiction: str) -> date:
        """Add N business days. Supports negative days for backward."""
        if days == 0:
            return start

        code = self._registry.normalize_required(jurisdiction)
        current = start
        remaining = abs(days)
        step = timedelta(days=1) if days > 0 else timedelta(days=-1)

        while remaining > 0:
            current += step
            if current.weekday() < 5 and current not in self._registry.get_holidays(
                code, current.year
            ):
                remaining -= 1

        return current

    def add_audited(
        self,
        start: date,
        days: int,
        jurisdiction: str,
        rule_id: str | None = None,
    ) -> tuple[date, DeadlineRecord]:
        """Add business days with audit record."""
        code = self._registry.normalize_required(jurisdiction)
        result = self.add(start, days, code)

        holidays_in_range = []
        lo, hi = (
            (start + timedelta(days=1), result)
            if days >= 0
            else (result, start - timedelta(days=1))
        )
        current = lo
        while current <= hi:
            if current in self._registry.get_holidays(code, current.year):
                holidays_in_range.append(current)
            current += timedelta(days=1)

        return result, DeadlineRecord(
            start=start,
            days=days,
            result=result,
            jurisdiction=code,
            holidays_skipped=tuple(sorted(holidays_in_range)),
            calculated_at=now_utc(),
            rule_id=rule_id,
        )

    def count(self, start: date, end: date, jurisdiction: str) -> int:
        """Count business days in [start, end)."""
        if start >= end:
            return 0

        code = self._registry.normalize_required(jurisdiction)
        count = 0
        current = start

        while current < end:
            if current.weekday() < 5 and current not in self._registry.get_holidays(
                code, current.year
            ):
                count += 1
            current += timedelta(days=1)

        return count

    def is_business_day(self, d: date, jurisdiction: str) -> bool:
        """Check if date is a business day."""
        code = self._registry.normalize_required(jurisdiction)
        return d.weekday() < 5 and d not in self._registry.get_holidays(code, d.year)

    def holidays(self, year: int, jurisdiction: str) -> frozenset[date]:
        """Get holidays for a year."""
        code = self._registry.normalize_required(jurisdiction)
        return self._registry.get_holidays(code, year)
