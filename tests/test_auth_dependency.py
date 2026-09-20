import uuid
from datetime import timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from app.db.session import async_session_maker
from app.models.user import User
from app.core.security import create_access_token, get_current_user, hash_password


@pytest.mark.asyncio
async def test_get_current_user_valid():
    unique_email = f"dep_user_{uuid.uuid4().hex[:8]}@example.com"
    raw_password = "SecretPassword123!"

    async with async_session_maker() as session:
        user = User(
            email=unique_email,
            hashed_password=hash_password(raw_password),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id), "email": unique_email})

    async with async_session_maker() as session:
        resolved_user = await get_current_user(token=token, db=session)
        assert resolved_user.id == user_id
        assert resolved_user.email == unique_email
        assert resolved_user.is_active is True

    # Cleanup
    async with async_session_maker() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


@pytest.mark.asyncio
async def test_get_current_user_expired_token():
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        data={"sub": str(user_id)},
        expires_delta=timedelta(seconds=-10),
    )

    async with async_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=expired_token, db=session)
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_tampered_token():
    token = create_access_token(data={"sub": str(uuid.uuid4())})
    tampered_token = token[:-4] + "fake"

    async with async_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=tampered_token, db=session)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_nonexistent_id():
    non_existent_id = uuid.uuid4()
    token = create_access_token(data={"sub": str(non_existent_id)})

    async with async_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=session)
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_inactive_account():
    unique_email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"

    async with async_session_maker() as session:
        user = User(
            email=unique_email,
            hashed_password=hash_password("AnyPassword123!"),
            is_active=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id)})

    async with async_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=session)
        assert exc_info.value.status_code == 403
        assert "Inactive user account" in exc_info.value.detail

    # Cleanup
    async with async_session_maker() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
