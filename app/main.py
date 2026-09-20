from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.
    Handles startup resources (loading model artifacts, database pools)
    and graceful shutdown teardown.
    """
    # Startup logic
    print(f"Starting {settings.PROJECT_NAME} [{settings.ENVIRONMENT}]...")
    yield
    # Shutdown logic
    print(f"Shutting down {settings.PROJECT_NAME}...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FastAPI service reproducing Amazon FDB vehicle loan risk benchmark",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Mount Routers
app.include_router(health.router)
app.include_router(auth.router)

