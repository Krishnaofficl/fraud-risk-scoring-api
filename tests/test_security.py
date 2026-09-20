import pytest
from app.core.security import hash_password, verify_password


def test_password_hashing_and_verification():
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


def test_password_hash_uniqueness():
    raw_password = "SamePasswordAcrossUsers123"
    hash1 = hash_password(raw_password)
    hash2 = hash_password(raw_password)

    # Salt ensures different hashes for the same password
    assert hash1 != hash2
    assert verify_password(raw_password, hash1) is True
    assert verify_password(raw_password, hash2) is True


def test_jwt_token_creation_and_decoding():
    from datetime import timedelta
    import jwt
    from app.core.security import create_access_token, decode_access_token

    payload_data = {"sub": "user-12345", "role": "admin"}
    token = create_access_token(data=payload_data, expires_delta=timedelta(minutes=15))

    assert isinstance(token, str)
    decoded = decode_access_token(token)

    assert decoded["sub"] == "user-12345"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_token_tampered_signature_rejected():
    import jwt
    from app.core.security import create_access_token, decode_access_token

    token = create_access_token(data={"sub": "legitimate_user"})
    tampered_token = token[:-5] + "XXXXX"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_jwt_expired_token_rejected():
    from datetime import timedelta
    import jwt
    from app.core.security import create_access_token, decode_access_token

    # Token with negative delta (expired in the past)
    expired_token = create_access_token(
        data={"sub": "expired_user"},
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)

