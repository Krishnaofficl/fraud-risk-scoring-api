from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import joblib
from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import ROOT_DIR, settings
from app.core.error_handlers import register_exception_handlers
from app.db.session import async_session_maker
from app.models.model_version import ModelVersion
from app.routers import auth, health, scoring, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.
    Loads the trained model artifact into application state during startup,
    seeds the active model version metadata into PostgreSQL,
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

    # 2. Ensure model version metadata is registered in DB (satisfying foreign key constraints)
    try:
        async with async_session_maker() as session:
            stmt = select(ModelVersion).where(ModelVersion.version == settings.MODEL_VERSION)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                mv = ModelVersion(
                    version=settings.MODEL_VERSION,
                    trained_at=datetime.now(timezone.utc),
                    reported_auc=0.6665,
                    paper_baseline_auc=0.5180,
                    artifact_path=str(settings.MODEL_PATH),
                )
                session.add(mv)
                await session.commit()
                print(f"Registered model version '{settings.MODEL_VERSION}' in database.")
    except Exception as exc:
        print(f"Notice: Model version DB sync skipped or deferred ({exc}).")

    yield

    # 3. Shutdown logic
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

# Register Global Exception Handlers
register_exception_handlers(app)

# Mount Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(scoring.router)

# Mount Frontend Static Assets & Dashboard Route
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(static_dir / "index.html")

    @app.get("/dashboard", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(static_dir / "index.html")




