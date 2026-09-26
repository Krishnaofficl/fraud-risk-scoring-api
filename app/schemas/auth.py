from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Payload schema for new user registration."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "analyst@riskplatform.com",
                "password": "SecurePassw0rd!",
            }
        }
    )

    email: EmailStr = Field(
        ...,
        description="RFC-compliant user email address",
        examples=["analyst@riskplatform.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters)",
        examples=["SecurePassw0rd!"],
    )


class UserLogin(BaseModel):
    """Payload schema for user authentication / login."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "analyst@riskplatform.com",
                "password": "SecurePassw0rd!",
            }
        }
    )

    email: EmailStr = Field(
        ...,
        description="Registered user email address",
        examples=["analyst@riskplatform.com"],
    )
    password: str = Field(
        ...,
        description="User password",
        examples=["SecurePassw0rd!"],
    )


class TokenResponse(BaseModel):
    """Response schema containing issued Bearer JWT access token."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        }
    )

    access_token: str = Field(
        ...,
        description="Cryptographically signed JWT bearer token",
    )
    token_type: str = Field(
        default="bearer",
        description="Authorization token type",
        examples=["bearer"],
    )
    expires_in: int = Field(
        ...,
        description="Token expiration duration in seconds",
        examples=[3600],
    )


class UserResponse(BaseModel):
    """Public user profile response schema."""
    id: UUID = Field(
        ...,
        description="Unique identifier for the user account",
    )
    email: EmailStr = Field(
        ...,
        description="Registered user email address",
    )
    is_active: bool = Field(
        ...,
        description="Flag indicating if the user account is active",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the user account was created",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "fa94e502-dcfb-4a58-9c6a-493e9ad1cf23",
                "email": "analyst@riskplatform.com",
                "is_active": True,
                "created_at": "2026-09-26T12:00:00Z",
            }
        },
    )
