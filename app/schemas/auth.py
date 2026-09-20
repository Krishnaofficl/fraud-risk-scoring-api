from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Payload schema for new user registration."""
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

    model_config = ConfigDict(from_attributes=True)
