"""Tests for opaque token and room-code security helpers."""

import string

from app.core.security import (
    ROOM_CODE_ALPHABET,
    generate_opaque_token,
    generate_room_code,
    hash_token,
    verify_token,
)


def test_opaque_tokens_are_high_entropy_url_safe_and_unique() -> None:
    tokens = {generate_opaque_token() for _ in range(50)}

    assert len(tokens) == 50
    assert all(len(token) >= 43 for token in tokens)
    assert all("=" not in token for token in tokens)


def test_token_hashes_are_deterministic_and_constant_time_comparable() -> None:
    token = generate_opaque_token()
    token_hash = hash_token(token)

    assert len(token_hash) == 64
    assert set(token_hash) <= set(string.hexdigits.lower())
    assert token not in token_hash
    assert verify_token(token, token_hash) is True
    assert verify_token(generate_opaque_token(), token_hash) is False


def test_room_codes_are_readable_uppercase_and_unambiguous() -> None:
    codes = {generate_room_code() for _ in range(50)}

    assert len(codes) == 50
    assert all(len(code) == 6 for code in codes)
    assert all(set(code) <= set(ROOM_CODE_ALPHABET) for code in codes)
    assert all(code == code.upper() for code in codes)
    assert not ({"0", "O", "1", "I"} & set(ROOM_CODE_ALPHABET))
