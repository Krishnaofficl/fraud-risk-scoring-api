from contextlib import asynccontextmanager
from pathlib import Path
import joblib
from fastapi import FastAPI
from app.core.config import ROOT_DIR, settings
from app.routers import auth, health, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.
    Loads the trained model artifact into application state during startup
    and handles graceful teardown upon shutdown.
    """
    # 1. Startup logic: Load ML Model Pipeline
    model_path = Path(settings.MODEL_PATH)
    if not model_path.is_absolute():
        model_path = ROOT_DIR / model_path

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at '{model_path}'. Ensure train.py has been run."
        )

    print(f"Loading ML model artifact from {model_path}...")
    app.state.model_pipeline = joblib.load(model_path)
    app.state.model_version = settings.MODEL_VERSION
    print(f"ML Model pipeline '{settings.MODEL_VERSION}' loaded successfully.")

    yield

    # 2. Shutdown logic
    print(f"Shutting down {settings.PROJECT_NAME}...")
    app.state.model_pipeline = None


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
app.include_router(users.router)


