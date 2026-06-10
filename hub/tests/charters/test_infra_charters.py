"""Test parsing of all Infrastructure domain charters."""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.dsl.lexer import Lexer
from canon.dsl.parser import Parser

# Path to infra charters
INFRA_DIR = (
    Path(__file__).parent.parent.parent / "charters" / "surfaces" / "infra"
)


def get_infra_charter_files() -> list[tuple[str, Path]]:
    """Get all .canon files in the infra directory."""
    return [(f.stem, f) for f in INFRA_DIR.glob("*.canon")]


class TestInfraCharterParsing:
    """Test that all Infrastructure charters parse without errors."""

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_parses(self, name: str, path: Path):
        """Each charter should parse without syntax errors."""
        source = path.read_text()

        # Parse - this will raise if there are syntax errors
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        # Basic assertions
        assert ast.name, f"Charter {name} should have a name"
        assert ast.version, f"Charter {name} should have a version"

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_has_packages(self, name: str, path: Path):
        """Each infra charter should have packages section."""
        source = path.read_text()
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        assert ast.packages is not None, f"Charter {name} should have packages"
        package_names = [p.name for p in ast.packages]
        assert "infra" in package_names, f"Charter {name} should include infra package"

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_has_triggers(self, name: str, path: Path):
        """Each infra charter should have triggers section."""
        source = path.read_text()
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        assert ast.triggers is not None, f"Charter {name} should have triggers"
        assert len(ast.triggers) > 0, f"Charter {name} should have at least one trigger"

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_has_certification_phase(self, name: str, path: Path):
        """Each infra charter should have immutable certification."""
        source = path.read_text()
        assert "certify immutable" in source, f"Charter {name} should have immutable certification"


class TestInfraSpecificPatterns:
    """Test infrastructure-specific patterns in charters."""

    def test_destructive_migration_has_backup_verification(self):
        """Destructive migration charter should have backup verification."""
        source = (INFRA_DIR / "destructive_migration.canon").read_text()

        assert "verify_backup_complete()" in source
        assert "require_backup_verified()" in source
        assert "derive_data_loss_risk()" in source

    def test_forced_failover_has_traffic_drain(self):
        """Forced failover charter should have traffic drain verification."""
        source = (INFRA_DIR / "forced_failover.canon").read_text()

        assert "verify_traffic_drained()" in source
        assert "check_dr_test_cooldown()" in source
        assert "derive_write_acceptance_mode()" in source

    def test_production_database_access_has_lifecycle_controls(self):
        """Production database access should have lifecycle controls."""
        source = (INFRA_DIR / "production_database_access.canon").read_text()

        assert "schedule_auto_revert()" in source
        assert "enforce_expiry()" in source
        assert "trigger_recertification()" in source

    def test_firewall_bypass_has_auto_expire(self):
        """Firewall bypass should have auto-expire lifecycle."""
        source = (INFRA_DIR / "firewall_rule_bypass.canon").read_text()

        assert "schedule_auto_revert()" in source
        assert "verify_rule_expired()" in source
        assert "enforce_expiry()" in source

    def test_dr_test_has_cooldown_check(self):
        """DR test charter should have cooldown check."""
        source = (INFRA_DIR / "disaster_recovery_test.canon").read_text()

        assert "check_dr_test_cooldown()" in source
        assert "verify_rollback_plan_present()" in source

    def test_load_balancer_override_has_traffic_drain(self):
        """Load balancer override should have traffic drain."""
        source = (INFRA_DIR / "load_balancer_override.canon").read_text()

        assert "verify_traffic_drained()" in source
        assert "verify_connection_teardown()" in source
        assert "await traffic_completely_drained" in source


class TestInfraEnvironmentConditions:
    """Test environment-specific conditional logic in infra charters."""

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_production_environment_has_elevated_controls(self, name: str, path: Path):
        """Infra charters should have elevated controls for production."""
        source = path.read_text()

        # Most infra charters should have production-specific controls
        if "environment ==" in source:
            assert (
                'when environment == "PROD"' in source
                or "require_production_environment()" in source
                or "require_deployment_approval()" in source
            ), f"Charter {name} should have production-specific controls"


class TestInfraRoles:
    """Test role definitions in infrastructure charters."""

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_has_roles(self, name: str, path: Path):
        """Each infra charter should define roles."""
        source = path.read_text()
        assert "roles:" in source, f"Charter {name} should have roles section"
        assert "requires_mfa: true" in source, f"Charter {name} should require MFA for roles"

    @pytest.mark.parametrize(
        "name,path",
        get_infra_charter_files(),
        ids=lambda x: x if isinstance(x, str) else x.stem,
    )
    def test_charter_has_break_glass(self, name: str, path: Path):
        """Each infra charter should have a break glass role."""
        source = path.read_text()
        assert "break_glass: true" in source, f"Charter {name} should have break glass capability"
