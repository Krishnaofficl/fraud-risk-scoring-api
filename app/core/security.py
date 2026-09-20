from pwdlib import PasswordHash

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
