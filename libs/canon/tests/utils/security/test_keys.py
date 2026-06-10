"""Tests for signing key management."""

from datetime import UTC, datetime, timedelta

import pytest

from canon.utils.security.keys import KeyRegistry, SigningKey


class TestSigningKey:
    """Tests for SigningKey dataclass."""

    @pytest.fixture
    def sample_key(self):
        """Create a sample signing key."""
        now = datetime.now(UTC)
        return SigningKey(
            key_id="key-001",
            version=1,
            valid_from=now - timedelta(days=30),
            valid_until=now + timedelta(days=335),
            public_key_pem="-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----",
        )

    def test_frozen(self, sample_key):
        """SigningKey is immutable."""
        with pytest.raises(Exception):
            sample_key.key_id = "changed"

    def test_to_dict(self, sample_key):
        """to_dict returns serializable dict."""
        result = sample_key.to_dict()

        assert result["key_id"] == "key-001"
        assert result["version"] == 1
        assert isinstance(result["valid_from"], str)
        assert isinstance(result["valid_until"], str)
        assert result["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")
        assert result["revoked_at"] is None

    def test_to_dict_with_revocation(self):
        """to_dict includes revoked_at when set."""
        now = datetime.now(UTC)
        key = SigningKey(
            key_id="key-001",
            version=1,
            valid_from=now - timedelta(days=30),
            valid_until=now + timedelta(days=335),
            public_key_pem="test",
            revoked_at=now,
        )

        result = key.to_dict()

        assert result["revoked_at"] is not None
        assert isinstance(result["revoked_at"], str)


class TestKeyRegistry:
    """Tests for KeyRegistry."""

    @pytest.fixture
    def keys(self):
        """Create sample keys for registry."""
        now = datetime.now(UTC)
        return [
            SigningKey(
                key_id="primary",
                version=1,
                valid_from=now - timedelta(days=365),
                valid_until=now - timedelta(days=30),
                public_key_pem="primary-v1",
            ),
            SigningKey(
                key_id="primary",
                version=2,
                valid_from=now - timedelta(days=30),
                valid_until=now + timedelta(days=335),
                public_key_pem="primary-v2",
            ),
            SigningKey(
                key_id="backup",
                version=1,
                valid_from=now - timedelta(days=100),
                valid_until=now + timedelta(days=265),
                public_key_pem="backup-v1",
            ),
        ]

    def test_get_key_with_version(self, keys):
        """Get specific key version."""
        registry = KeyRegistry(keys)

        key = registry.get_key("primary", version=1)

        assert key is not None
        assert key.public_key_pem == "primary-v1"

    def test_get_key_latest_version(self, keys):
        """Get latest version when version not specified."""
        registry = KeyRegistry(keys)

        key = registry.get_key("primary")

        assert key is not None
        assert key.version == 2
        assert key.public_key_pem == "primary-v2"

    def test_get_key_not_found(self, keys):
        """Returns None for unknown key."""
        registry = KeyRegistry(keys)

        key = registry.get_key("nonexistent")

        assert key is None

    def test_get_key_version_not_found(self, keys):
        """Returns None for unknown version."""
        registry = KeyRegistry(keys)

        key = registry.get_key("primary", version=99)

        assert key is None

    def test_get_current_key(self, keys):
        """Get current key for new signatures."""
        registry = KeyRegistry(keys, current_key_id="primary")

        key = registry.get_current_key()

        assert key is not None
        assert key.key_id == "primary"
        assert key.version == 2

    def test_get_current_key_none(self, keys):
        """Returns None when no current key set."""
        registry = KeyRegistry(keys)

        key = registry.get_current_key()

        assert key is None

    def test_is_key_valid_at_within_window(self, keys):
        """Key valid within validity window."""
        registry = KeyRegistry(keys)
        key = registry.get_key("primary", version=2)
        now = datetime.now(UTC)

        assert registry.is_key_valid_at(key, now) is True

    def test_is_key_valid_at_before_valid_from(self, keys):
        """Key invalid before valid_from."""
        registry = KeyRegistry(keys)
        key = registry.get_key("primary", version=2)
        before = key.valid_from - timedelta(days=1)

        assert registry.is_key_valid_at(key, before) is False

    def test_is_key_valid_at_after_valid_until(self, keys):
        """Key invalid after valid_until."""
        registry = KeyRegistry(keys)
        key = registry.get_key("primary", version=2)
        after = key.valid_until + timedelta(days=1)

        assert registry.is_key_valid_at(key, after) is False

    def test_is_key_valid_at_prospective_revocation(self):
        """Revocation is prospective - before revocation is valid."""
        now = datetime.now(UTC)
        key = SigningKey(
            key_id="revoked",
            version=1,
            valid_from=now - timedelta(days=100),
            valid_until=now + timedelta(days=265),
            public_key_pem="test",
            revoked_at=now,  # Revoked now
        )
        registry = KeyRegistry([key])

        # Before revocation: valid
        before = now - timedelta(days=1)
        assert registry.is_key_valid_at(key, before) is True

        # At revocation: invalid
        assert registry.is_key_valid_at(key, now) is False

        # After revocation: invalid
        after = now + timedelta(days=1)
        assert registry.is_key_valid_at(key, after) is False

    def test_empty_registry(self):
        """Empty registry returns None for all lookups."""
        registry = KeyRegistry([])

        assert registry.get_key("any") is None
        assert registry.get_current_key() is None
