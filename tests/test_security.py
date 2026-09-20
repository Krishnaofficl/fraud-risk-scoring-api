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
