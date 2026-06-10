"""Tests for business day calendar."""

from datetime import date
from pathlib import Path

import pytest

from canon.utils.calendar import Calendar, DeadlineRecord
from canon.utils.loader import load_jurisdictions


@pytest.fixture
def registry():
    # Path: libs/canon/tests/utils/test_calendar.py
    # Go up 4 levels to canonsys root, then into hub/policies/jurisdictions
    return load_jurisdictions(Path(__file__).parents[4] / "hub" / "policies" / "jurisdictions")


@pytest.fixture
def cal(registry):
    return Calendar(registry)


class TestCalendarAdd:
    def test_add_zero_days(self, cal):
        start = date(2025, 1, 15)
        assert cal.add(start, 0, "US-FEDERAL") == start

    def test_add_skips_weekends(self, cal):
        # Friday Jan 3 + 1 business day = Monday Jan 6
        assert cal.add(date(2025, 1, 3), 1, "US-FEDERAL") == date(2025, 1, 6)

    def test_add_skips_holidays(self, cal):
        # Jan 1 (holiday) + 1 business day = Jan 2
        assert cal.add(date(2024, 12, 31), 1, "US-FEDERAL") == date(2025, 1, 2)

    def test_add_mlk_day(self, cal):
        # Jan 17 (Fri) + 1 = Jan 21 (Tue, skips weekend + MLK Day Jan 20)
        assert cal.add(date(2025, 1, 17), 1, "US-FEDERAL") == date(2025, 1, 21)

    def test_add_negative_days(self, cal):
        # Jan 6 (Mon) - 1 = Jan 3 (Fri)
        assert cal.add(date(2025, 1, 6), -1, "US-FEDERAL") == date(2025, 1, 3)

    def test_add_with_alias(self, cal):
        # Should accept "federal" alias
        result = cal.add(date(2025, 1, 1), 5, "federal")
        assert result == date(2025, 1, 8)

    def test_add_nyc_includes_city_holidays(self, cal):
        # NYC has Election Day (Nov 4, 2025) as holiday
        # Nov 3 (Mon) + 1 = Nov 5 (Wed, skips Election Day)
        assert cal.add(date(2025, 11, 3), 1, "US-NYC") == date(2025, 11, 5)


class TestCalendarCount:
    def test_count_empty_range(self, cal):
        assert cal.count(date(2025, 1, 10), date(2025, 1, 10), "US-FEDERAL") == 0

    def test_count_reversed_range(self, cal):
        assert cal.count(date(2025, 1, 10), date(2025, 1, 5), "US-FEDERAL") == 0

    def test_count_one_week(self, cal):
        # Jan 6-10 (Mon-Fri) = 5 business days
        assert cal.count(date(2025, 1, 6), date(2025, 1, 11), "US-FEDERAL") == 5

    def test_count_with_holiday(self, cal):
        # Jan 2025 has 22 business days (31 days - 8 weekend days - 1 holiday)
        # Jan 1 = holiday, Jan 20 = MLK Day
        # Actually: 31 - 8 weekends - 2 holidays = 21
        assert cal.count(date(2025, 1, 1), date(2025, 2, 1), "US-FEDERAL") == 21


class TestCalendarIsBusinessDay:
    def test_weekday_no_holiday(self, cal):
        assert cal.is_business_day(date(2025, 1, 2), "US-FEDERAL") is True

    def test_saturday(self, cal):
        assert cal.is_business_day(date(2025, 1, 4), "US-FEDERAL") is False

    def test_sunday(self, cal):
        assert cal.is_business_day(date(2025, 1, 5), "US-FEDERAL") is False

    def test_holiday(self, cal):
        # MLK Day 2025
        assert cal.is_business_day(date(2025, 1, 20), "US-FEDERAL") is False


class TestCalendarHolidays:
    def test_federal_holidays_2025(self, cal):
        holidays = cal.holidays(2025, "US-FEDERAL")
        assert date(2025, 1, 1) in holidays  # New Year
        assert date(2025, 1, 20) in holidays  # MLK Day
        assert date(2025, 12, 25) in holidays  # Christmas
        assert len(holidays) == 11

    def test_nyc_has_more_holidays(self, cal):
        federal = cal.holidays(2025, "US-FEDERAL")
        nyc = cal.holidays(2025, "US-NYC")
        assert len(nyc) > len(federal)


class TestDeadlineRecord:
    def test_add_audited_returns_record(self, cal):
        result, record = cal.add_audited(date(2025, 1, 1), 15, "US-FEDERAL", rule_id="test.rule")

        assert isinstance(record, DeadlineRecord)
        assert record.start == date(2025, 1, 1)
        assert record.days == 15
        assert record.result == result
        assert record.jurisdiction == "US-FEDERAL"
        assert record.rule_id == "test.rule"
        assert record.calculated_at is not None

    def test_add_audited_captures_skipped_holidays(self, cal):
        # 15 business days from Jan 1 should skip MLK Day (Jan 20)
        _, record = cal.add_audited(date(2025, 1, 1), 15, "US-FEDERAL")
        assert date(2025, 1, 20) in record.holidays_skipped

    def test_deadline_record_to_dict(self, cal):
        _, record = cal.add_audited(date(2025, 1, 1), 5, "US-FEDERAL")
        d = record.to_dict()

        assert d["start"] == "2025-01-01"
        assert isinstance(d["holidays_skipped"], list)
        assert "calculated_at" in d
