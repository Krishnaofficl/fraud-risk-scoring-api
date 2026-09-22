"""
Unit tests for core cryptographic and security utilities.
Covers Argon2id password hashing, verification, salt uniqueness,
JWT generation, expiration, tamper detection, and validation error handling.
These tests run strictly in memory without database dependencies (<0.5s).
"""

from datetime import datetime, timedelta, timezone
import pytest
import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.unit
def test_password_hashing_and_verification():
    """Verify that Argon2id generates valid hashes and correctly matches passwords."""
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)

    # Hash must not match plaintext
    assert hashed != raw_password
    # Hash should use Argon2id format
    assert hashed.startswith("$argon2id$")

    # Verification must succeed with correct password
    assert verify_password(raw_password, hashed) is True

    # Verification must fail with wrong password
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


@pytest.mark.unit
def test_password_hash_uniqueness_with_salt():
    """Verify that each hash has a unique salt even for identical passwords."""
    raw_password = "SamePasswordAcrossUsers123"
    hash1 = hash_password(raw_password)
    hash2 = hash_password(raw_password)

    # Salt ensures different hashes for the same password
    assert hash1 != hash2
    assert verify_password(raw_password, hash1) is True
    assert verify_password(raw_password, hash2) is True


@pytest.mark.unit
def test_password_unicode_and_special_chars():
    """Verify that complex Unicode, punctuation, and non-ASCII passwords hash properly."""
    raw_password = "🔒Pässwørd_with_€mojis!#*&^%$"
    hashed = hash_password(raw_password)

    assert verify_password(raw_password, hashed) is True
    assert verify_password("🔒Pässwørd_with_€mojis!#*&^%@", hashed) is False


@pytest.mark.unit
def test_jwt_token_creation_and_decoding():
    """Verify that access tokens contain the expected claims and can be decoded."""
    payload_data = {"sub": "user-12345", "role": "risk_analyst", "tenant": "corp"}
    token = create_access_token(data=payload_data, expires_delta=timedelta(minutes=15))

    assert isinstance(token, str)
    decoded = decode_access_token(token)

    assert decoded["sub"] == "user-12345"
    assert decoded["role"] == "risk_analyst"
    assert decoded["tenant"] == "corp"
    assert "exp" in decoded
    assert "iat" in decoded


@pytest.mark.unit
def test_jwt_default_expiration():
    """Verify that the default expiration duration aligns with ACCESS_TOKEN_EXPIRE_MINUTES."""
    token = create_access_token(data={"sub": "test-user"})
    decoded = decode_access_token(token)

    exp_timestamp = decoded["exp"]
    iat_timestamp = decoded["iat"]
    duration_minutes = (exp_timestamp - iat_timestamp) / 60

    assert round(duration_minutes) == settings.ACCESS_TOKEN_EXPIRE_MINUTES


@pytest.mark.unit
def test_jwt_token_tampered_signature_rejected():
    """Verify that modifying the payload or signature causes InvalidTokenError."""
    token = create_access_token(data={"sub": "legitimate_user"})
    # Tamper with the last characters of the signature
    tampered_token = token[:-5] + "XXXXX"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


@pytest.mark.unit
def test_jwt_expired_token_rejected():
    """Verify that expired JWTs raise ExpiredSignatureError."""
    expired_token = create_access_token(
        data={"sub": "expired_user"},
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


@pytest.mark.unit
def test_jwt_wrong_secret_rejected():
    """Verify that decoding with a mismatched secret key fails validation."""
    token = create_access_token(data={"sub": "legitimate_user"})

    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "completely-wrong-secret-key-1234567890", algorithms=["HS256"])


@pytest.mark.unit
def test_jwt_malformed_string_rejected():
    """Verify that non-JWT or malformed strings raise InvalidTokenError."""
    malformed_tokens = [
        "not.a.jwt",
        "header.payload",
        "random_garbage_string",
        "",
    ]
    for bad_token in malformed_tokens:
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(bad_token)
