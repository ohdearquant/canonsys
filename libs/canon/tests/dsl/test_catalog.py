"""Tests for Charter DSL schema catalog."""

from __future__ import annotations

from dataclasses import dataclass

from canon.dsl.catalog import CatalogEntry, SchemaCatalog


@dataclass(frozen=True)
class MockType:
    pass


@dataclass(frozen=True)
class AnotherType:
    pass


class TestSchemaCatalog:
    def test_register_and_get(self):
        cat = SchemaCatalog()
        cat.register("ns", "1.0", "MyType", MockType)
        assert cat.get("ns", "1.0", "MyType") is MockType

    def test_get_unknown(self):
        cat = SchemaCatalog()
        assert cat.get("ns", "1.0", "Unknown") is None

    def test_get_entry(self):
        cat = SchemaCatalog()
        cat.register("ns", "1.0", "MyType", MockType)
        entry = cat.get_entry("ns", "1.0", "MyType")
        assert isinstance(entry, CatalogEntry)
        assert entry.name == "MyType"
        assert entry.schema_type is MockType
        assert entry.version == "1.0"
        assert entry.namespace == "ns"

    def test_has_version(self):
        cat = SchemaCatalog()
        assert not cat.has_version("ns", "1.0")
        cat.register("ns", "1.0", "T", MockType)
        assert cat.has_version("ns", "1.0")
        assert not cat.has_version("ns", "2.0")

    def test_list_types(self):
        cat = SchemaCatalog()
        cat.register("ns", "1.0", "Beta", MockType)
        cat.register("ns", "1.0", "Alpha", AnotherType)
        cat.register("ns", "2.0", "Gamma", MockType)
        assert cat.list_types("ns", "1.0") == ["Alpha", "Beta"]
        assert cat.list_types("ns", "2.0") == ["Gamma"]

    def test_list_versions(self):
        cat = SchemaCatalog()
        cat.register("ns", "2026.01", "A", MockType)
        cat.register("ns", "2025.06", "B", MockType)
        cat.register("other", "1.0", "C", MockType)
        assert cat.list_versions("ns") == ["2025.06", "2026.01"]
        assert cat.list_versions("other") == ["1.0"]
        assert cat.list_versions("empty") == []

    def test_multiple_namespaces(self):
        cat = SchemaCatalog()
        cat.register("canon.hr", "1.0", "T", MockType)
        cat.register("canon.finance", "1.0", "T", AnotherType)
        assert cat.get("canon.hr", "1.0", "T") is MockType
        assert cat.get("canon.finance", "1.0", "T") is AnotherType
