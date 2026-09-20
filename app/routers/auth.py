from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a new user with a validated email and password. Passwords are encrypted using Argon2id.",
)
async def register(
    payload: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.
    - Checks for duplicate email to ensure uniqueness (409 Conflict if duplicate).
    - Encrypts password using Argon2id.
    - Stores the record in PostgreSQL.
    - Returns sanitized public user profile (201 Created).
    """
    # 1. Check if user with this email already exists
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    # 2. Hash plaintext password using Argon2id
    hashed_pwd = hash_password(payload.password)

    # 3. Create and persist user entity
    new_user = User(
        email=payload.email,
        hashed_password=hashed_pwd,
        is_active=True,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user
