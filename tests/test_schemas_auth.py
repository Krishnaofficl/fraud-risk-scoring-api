import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse


def test_user_register_valid():
    data = {"email": "user@example.com", "password": "SecurePassword123"}
    model = UserRegister(**data)
    assert model.email == "user@example.com"
    assert model.password == "SecurePassword123"


def test_user_register_invalid_email():
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(email="not-an-email", password="ValidPassword123")
    assert "email" in str(exc_info.value)


def test_user_register_short_password():
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(email="user@example.com", password="123")
    assert "password" in str(exc_info.value)


def test_user_login_valid():
    model = UserLogin(email="user@example.com", password="anypassword")
    assert model.email == "user@example.com"
    assert model.password == "anypassword"


def test_token_response_defaults():
    token_resp = TokenResponse(access_token="sample.jwt.token", expires_in=3600)
    assert token_resp.token_type == "bearer"
    assert token_resp.access_token == "sample.jwt.token"
    assert token_resp.expires_in == 3600


def test_user_response_from_attributes():
    test_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    class MockUserORM:
        id = test_id
        email = "analyst@bank.com"
        is_active = True
        created_at = now

    user_resp = UserResponse.model_validate(MockUserORM())
    assert user_resp.id == test_id
    assert user_resp.email == "analyst@bank.com"
    assert user_resp.is_active is True
    assert user_resp.created_at == now
