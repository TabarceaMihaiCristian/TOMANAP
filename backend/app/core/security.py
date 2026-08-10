"""Opaque-token and readable room-code security primitives."""

import hmac
import secrets
from hashlib import sha256

TOKEN_BYTES = 32
ROOM_CODE_LENGTH = 6
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_opaque_token(*, byte_count: int = TOKEN_BYTES) -> str:
    """Return a URL-safe token with at least 256 bits of entropy by default."""
    if isinstance(byte_count, bool) or not isinstance(byte_count, int):
        raise ValueError("byte_count must be an integer")
    if byte_count < TOKEN_BYTES:
        raise ValueError(f"byte_count must be at least {TOKEN_BYTES}")
    return secrets.token_urlsafe(byte_count)


def hash_token(token: str) -> str:
    """Return a stable SHA-256 digest for a high-entropy opaque token."""
    if not isinstance(token, str) or not token:
        raise ValueError("token must be a non-empty string")
    return sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, expected_hash: str) -> bool:
    """Compare an opaque token to a stored digest in constant time."""
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return False
    try:
        actual_hash = hash_token(token)
    except ValueError:
        actual_hash = "0" * 64
    return hmac.compare_digest(actual_hash, expected_hash)


def generate_room_code(*, length: int = ROOM_CODE_LENGTH) -> str:
    """Return a readable code without visually ambiguous characters."""
    if isinstance(length, bool) or not isinstance(length, int):
        raise ValueError("length must be an integer")
    if not 4 <= length <= 8:
        raise ValueError("length must be between 4 and 8")
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))
