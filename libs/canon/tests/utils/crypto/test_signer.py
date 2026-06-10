"""Tests for RSA signing operations."""

import pytest

from canon.utils.security.signer import (
    generate_key_pair,
    sign_payload,
    verify_signature,
)


class TestGenerateKeyPair:
    """Tests for generate_key_pair."""

    def test_generates_pem_strings(self):
        """Key pair returns PEM-formatted strings."""
        private_pem, public_pem = generate_key_pair()

        assert isinstance(private_pem, str)
        assert isinstance(public_pem, str)
        assert "-----BEGIN RSA PRIVATE KEY-----" in private_pem
        assert "-----BEGIN PUBLIC KEY-----" in public_pem

    def test_keys_are_different(self):
        """Private and public keys are distinct."""
        private_pem, public_pem = generate_key_pair()

        assert private_pem != public_pem

    def test_generates_unique_keys(self):
        """Each call generates different keys."""
        pair1 = generate_key_pair()
        pair2 = generate_key_pair()

        assert pair1[0] != pair2[0]
        assert pair1[1] != pair2[1]


class TestSignPayload:
    """Tests for sign_payload."""

    @pytest.fixture
    def key_pair(self):
        """Generate a key pair for testing."""
        return generate_key_pair()

    def test_signs_payload(self, key_pair):
        """Signs payload and returns bytes."""
        private_pem, _ = key_pair
        payload = b"test payload"

        signature = sign_payload(payload, private_pem)

        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_same_payload_different_signatures_with_different_keys(self):
        """Different keys produce different signatures."""
        payload = b"test payload"
        private1, _ = generate_key_pair()
        private2, _ = generate_key_pair()

        sig1 = sign_payload(payload, private1)
        sig2 = sign_payload(payload, private2)

        assert sig1 != sig2

    def test_deterministic_signature(self, key_pair):
        """Same key and payload produce same signature."""
        private_pem, _ = key_pair
        payload = b"test payload"

        sig1 = sign_payload(payload, private_pem)
        sig2 = sign_payload(payload, private_pem)

        assert sig1 == sig2

    def test_invalid_key_raises(self):
        """Invalid key raises ValueError."""
        with pytest.raises(Exception):
            sign_payload(b"test", "not a valid key")

    def test_empty_payload(self, key_pair):
        """Can sign empty payload."""
        private_pem, _ = key_pair

        signature = sign_payload(b"", private_pem)

        assert isinstance(signature, bytes)


class TestVerifySignature:
    """Tests for verify_signature."""

    @pytest.fixture
    def key_pair(self):
        """Generate a key pair for testing."""
        return generate_key_pair()

    def test_valid_signature(self, key_pair):
        """Valid signature returns True."""
        private_pem, public_pem = key_pair
        payload = b"test payload"
        signature = sign_payload(payload, private_pem)

        result = verify_signature(payload, signature, public_pem)

        assert result is True

    def test_tampered_payload(self, key_pair):
        """Tampered payload returns False."""
        private_pem, public_pem = key_pair
        payload = b"original payload"
        signature = sign_payload(payload, private_pem)

        result = verify_signature(b"tampered payload", signature, public_pem)

        assert result is False

    def test_wrong_public_key(self, key_pair):
        """Wrong public key returns False."""
        private_pem, _ = key_pair
        _, wrong_public = generate_key_pair()
        payload = b"test payload"
        signature = sign_payload(payload, private_pem)

        result = verify_signature(payload, signature, wrong_public)

        assert result is False

    def test_corrupted_signature(self, key_pair):
        """Corrupted signature returns False."""
        private_pem, public_pem = key_pair
        payload = b"test payload"
        signature = sign_payload(payload, private_pem)
        corrupted = bytes([b ^ 0xFF for b in signature[:10]]) + signature[10:]

        result = verify_signature(payload, corrupted, public_pem)

        assert result is False

    def test_invalid_public_key(self):
        """Invalid public key returns False (fail-closed)."""
        result = verify_signature(b"payload", b"sig", "not a key")

        assert result is False

    def test_empty_payload_roundtrip(self, key_pair):
        """Empty payload signs and verifies."""
        private_pem, public_pem = key_pair
        signature = sign_payload(b"", private_pem)

        result = verify_signature(b"", signature, public_pem)

        assert result is True
