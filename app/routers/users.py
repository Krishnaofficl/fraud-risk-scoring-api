from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/v1/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the authenticated user's profile. Requires a valid Bearer JWT token in the Authorization header.",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the currently authenticated user's public profile.
    Guarded by the get_current_user dependency.
    """
    return current_user
