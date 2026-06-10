"""Tests for jurisdiction loader."""

from datetime import date
from pathlib import Path

import pytest

from canon.utils.loader import JurisdictionRegistry, load_jurisdictions


@pytest.fixture
def registry():
    # Path: libs/canon/tests/test_jurisdiction_loader.py
    # Go up 3 levels to canonsys root, then into hub/policies/jurisdictions
    return load_jurisdictions(Path(__file__).parents[3] / "hub" / "policies" / "jurisdictions")


class TestLoadJurisdictions:
    def test_loads_all_jurisdictions(self, registry):
        codes = registry.codes
        assert "US-FEDERAL" in codes
        assert "US-NYC" in codes
        assert "US-CA" in codes
        assert "EU" in codes

    def test_returns_registry(self, registry):
        assert isinstance(registry, JurisdictionRegistry)


class TestJurisdictionConfig:
    def test_get_federal(self, registry):
        cfg = registry.get("US-FEDERAL")
        assert cfg is not None
        assert cfg.code == "US-FEDERAL"
        assert cfg.name == "United States (Federal)"
        assert cfg.country == "US"
        assert cfg.parent is None

    def test_get_nyc(self, registry):
        cfg = registry.get("US-NYC")
        assert cfg is not None
        assert cfg.parent == "US-NY"

    def test_get_nonexistent(self, registry):
        assert registry.get("NONEXISTENT") is None

    def test_require_raises(self, registry):
        with pytest.raises(KeyError):
            registry.require("NONEXISTENT")

    def test_calendar_config(self, registry):
        federal = registry.get("US-FEDERAL")
        assert federal.calendar.uses_federal_holidays is False
        assert federal.calendar.has_custom_holidays is True

        va = registry.get("US-VA")
        assert va.calendar.uses_federal_holidays is True
        assert va.calendar.has_custom_holidays is False


class TestNormalize:
    def test_normalize_code(self, registry):
        assert registry.normalize("US-NYC") == "US-NYC"
        assert registry.normalize("us-nyc") == "US-NYC"
        assert registry.normalize("US_NYC") == "US-NYC"

    def test_normalize_alias(self, registry):
        assert registry.normalize("nyc") == "US-NYC"
        assert registry.normalize("NYC") == "US-NYC"
        assert registry.normalize("california") == "US-CA"
        assert registry.normalize("federal") == "US-FEDERAL"

    def test_normalize_unknown(self, registry):
        assert registry.normalize("unknown") is None
        assert registry.normalize("") is None

    def test_normalize_required_raises(self, registry):
        with pytest.raises(ValueError):
            registry.normalize_required("unknown")


class TestHierarchy:
    def test_hierarchy_federal(self, registry):
        h = registry.hierarchy("US-FEDERAL")
        assert h == ("US-FEDERAL",)

    def test_hierarchy_state(self, registry):
        h = registry.hierarchy("US-CA")
        assert h == ("US-CA", "US-FEDERAL")

    def test_hierarchy_city(self, registry):
        h = registry.hierarchy("US-NYC")
        assert h == ("US-NYC", "US-NY", "US-FEDERAL")


class TestHolidays:
    def test_federal_holidays_count(self, registry):
        holidays = registry.get_holidays("US-FEDERAL", 2025)
        assert len(holidays) == 11

    def test_federal_holidays_content(self, registry):
        holidays = registry.get_holidays("US-FEDERAL", 2025)
        assert date(2025, 1, 1) in holidays  # New Year
        assert date(2025, 1, 20) in holidays  # MLK Day
        assert date(2025, 7, 4) in holidays  # Independence Day
        assert date(2025, 12, 25) in holidays  # Christmas

    def test_state_inherits_federal(self, registry):
        va_holidays = registry.get_holidays("US-VA", 2025)
        fed_holidays = registry.get_holidays("US-FEDERAL", 2025)
        # VA uses federal holidays
        assert fed_holidays <= va_holidays

    def test_nyc_has_custom_holidays(self, registry):
        nyc = registry.get_holidays("US-NYC", 2025)
        # NYC has Election Day
        assert date(2025, 11, 4) in nyc

    def test_california_has_custom_holidays(self, registry):
        ca = registry.get_holidays("US-CA", 2025)
        # CA has Cesar Chavez Day
        assert date(2025, 3, 31) in ca

    def test_holidays_cached(self, registry):
        h1 = registry.get_holidays("US-FEDERAL", 2025)
        h2 = registry.get_holidays("US-FEDERAL", 2025)
        assert h1 is h2  # Same object (cached)

    def test_observance_saturday(self, registry):
        # July 4, 2026 is Saturday -> observed Friday July 3
        holidays = registry.get_holidays("US-FEDERAL", 2026)
        assert date(2026, 7, 3) in holidays

    def test_observance_sunday(self, registry):
        # Jan 1, 2027 is Friday - no observance shift
        # But Juneteenth 2027 (June 19) is Saturday -> observed Friday June 18
        holidays = registry.get_holidays("US-FEDERAL", 2027)
        assert date(2027, 6, 18) in holidays


class TestStrictMode:
    def test_strict_missing_parent(self, tmp_path):
        # Create a jurisdiction with missing parent
        jdir = tmp_path / "test"
        jdir.mkdir()
        (jdir / "config.toml").write_text("""
[jurisdiction]
code = "TEST"
name = "Test"
country = "US"
parent = "NONEXISTENT"

[calendar]
uses_federal_holidays = false
has_custom_holidays = false

[aliases]
values = ["test"]
""")
        with pytest.raises(ValueError, match="unknown parent"):
            load_jurisdictions(tmp_path, strict=True)

    def test_non_strict_ignores_missing(self, tmp_path):
        jdir = tmp_path / "test"
        jdir.mkdir()
        (jdir / "config.toml").write_text("""
[jurisdiction]
code = "TEST"
name = "Test"
country = "US"

[calendar]
uses_federal_holidays = false
has_custom_holidays = false

[aliases]
values = []
""")
        registry = load_jurisdictions(tmp_path, strict=False)
        # Should not raise, and holidays should return empty
        assert registry.get_holidays("TEST", 2025) == frozenset()
