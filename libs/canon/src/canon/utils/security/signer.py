"""RSA-4096 signing for evidence seals.

RSA-4096 + PKCS1v15 + SHA-256. Fail-closed verification.
Private keys from KMS/env at runtime, never stored.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

__all__ = [
    "generate_key_pair",
    "sign_payload",
    "verify_signature",
]


def generate_key_pair() -> tuple[str, str]:
    """Generate RSA-4096 key pair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    return private_pem, public_pem


def sign_payload(payload: bytes, private_key_pem: str) -> bytes:
    """Sign payload bytes. Raises ValueError if key invalid."""
    loaded_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )

    if not isinstance(loaded_key, RSAPrivateKey):
        raise ValueError("Expected RSA private key")

    signature = loaded_key.sign(
        payload,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return signature


def verify_signature(payload: bytes, signature: bytes, public_key_pem: str) -> bool:
    """Verify signature. Returns False on any error (fail-closed)."""
    try:
        loaded_key = serialization.load_pem_public_key(
            public_key_pem.encode("utf-8"),
        )

        if not isinstance(loaded_key, RSAPublicKey):
            return False

        loaded_key.verify(
            signature,
            payload,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True

    except Exception:
        # Fail-closed: any error means verification failed
        return False
