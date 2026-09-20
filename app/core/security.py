from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Initialize modern recommended password hasher (Argon2id)
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using the modern Argon2id algorithm
    (OWASP recommended standard, immune to GPU/ASIC attacks).
    """
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against an existing hash in constant time.
    Returns True if valid, False otherwise.
    """
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed JSON Web Token (JWT) containing provided claims,
    an issue timestamp (iat), and an expiration timestamp (exp).
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and cryptographically validates a signed JWT token.
    Raises jwt.ExpiredSignatureError if token has expired.
    Raises jwt.InvalidTokenError if token is tampered, malformed, or invalid.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )

