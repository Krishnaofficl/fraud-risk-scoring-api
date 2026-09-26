from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger("app.audit.auth")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a new user with a validated email and password. Passwords are encrypted using Argon2id.",
    responses={
        status.HTTP_201_CREATED: {
            "description": "User account created successfully.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "A user with this email address already exists.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Registration payload validation failed (e.g. password < 8 chars).",
        },
    },
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
        logger.warning("auth_register_conflict", email=payload.email)
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

    logger.info("auth_register_success", user_id=str(new_user.id), email=new_user.email)
    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain JWT token",
    description="Authenticates user credentials against the database and returns a signed Bearer JWT.",
    responses={
        status.HTTP_200_OK: {
            "description": "Authentication successful; Bearer JWT access token issued.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Invalid email or password credentials.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "User account is inactive or disabled.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Login payload validation failed.",
        },
    },
)
async def login(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user.
    - Looks up user by email.
    - Verifies password using Argon2id constant-time comparison.
    - Checks account active status.
    - Issues and returns a signed Bearer JWT token.
    """
    # 1. Fetch user by email
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # 2. Verify existence and password
    if user is None or not verify_password(payload.password, user.hashed_password):
        logger.warning("auth_login_failed", email=payload.email, reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check if user is active
    if not user.is_active:
        logger.warning("auth_login_failed", email=payload.email, user_id=str(user.id), reason="inactive_account")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    # 4. Generate signed JWT token
    token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    logger.info("auth_login_success", user_id=str(user.id), email=user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

