"""Optional payload encryption for the telemetry buffer.

Uses ECIES (Elliptic Curve Integrated Encryption Scheme):
  1. Generate ephemeral EC P-256 key
  2. Derive shared secret via ECDH with server's public key
  3. Derive AES-256 key via HKDF
  4. Encrypt with AES-256-GCM (provides authentication = tamper rejection)

Output format: ephemeral_pubkey (65 bytes) || nonce (12 bytes) || ciphertext || tag (16 bytes)

Gracefully falls back to plaintext if ``cryptography`` is unavailable or
server public key is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

PUBLIC_KEY_PATH = Path.home() / ".observal" / "keys" / "server_public.pem"


def can_encrypt() -> bool:
    """Return True if encryption is available (key + library)."""
    if not PUBLIC_KEY_PATH.exists():
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401

        return True
    except ImportError:
        return False


def encrypt_payload(plaintext: str) -> tuple[bytes, bool]:
    """Encrypt plaintext JSON. Returns (data, was_encrypted).

    If encryption unavailable, returns (plaintext.encode(), False).
    """
    if not can_encrypt():
        return plaintext.encode("utf-8"), False

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    # Load server public key
    pem_data = PUBLIC_KEY_PATH.read_bytes()
    server_pub = serialization.load_pem_public_key(pem_data)

    # Generate ephemeral key pair
    ephemeral_private = ec.generate_private_key(ec.SECP256R1())
    ephemeral_public = ephemeral_private.public_key()

    # ECDH shared secret
    shared_secret = ephemeral_private.exchange(ec.ECDH(), server_pub)

    # Derive AES key via HKDF
    aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"observal-buffer-v1",
    ).derive(shared_secret)

    # Encrypt with AES-256-GCM
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Serialize: ephemeral pubkey (uncompressed, 65 bytes) || nonce (12) || ciphertext+tag
    ephemeral_bytes = ephemeral_public.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )

    return ephemeral_bytes + nonce + ciphertext, True
