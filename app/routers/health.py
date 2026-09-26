from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailableException, ModelNotLoadedException
from app.db.session import get_db
from app.schemas.error import ErrorResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Liveness check",
    responses={
        status.HTTP_200_OK: {
            "description": "API process is running and able to handle HTTP requests.",
        },
    },
)
async def liveness_check():
    """Returns 200 OK if the API process is alive and receiving traffic."""
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get(
    "/health/ready",
    summary="Readiness check",
    responses={
        status.HTTP_200_OK: {
            "description": "Service dependencies (PostgreSQL database and ML pipeline) are fully ready.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Service is unavailable: database ping failed or ML model is not in memory.",
        },
    },
)
async def readiness_check(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Returns 200 OK if the API, database, and ML pipeline are ready to serve traffic.
    Returns 503 Service Unavailable if database ping fails or model pipeline is not in memory.
    """
    # 1. Verify Model Pipeline in memory
    model_pipeline = getattr(request.app.state, "model_pipeline", None)
    if model_pipeline is None:
        raise ModelNotLoadedException(
            message="Machine learning risk scoring pipeline is not loaded in memory.",
            detail="Model pipeline not found in application state.",
        )

    # 2. Verify Database connectivity
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise DatabaseUnavailableException(
            message="Database service is currently unreachable or degraded.",
            detail=str(exc),
        )

    return {
        "status": "ready",
        "database": "connected",
        "model_loaded": True,
        "model_version": getattr(request.app.state, "model_version", settings.MODEL_VERSION),
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }

