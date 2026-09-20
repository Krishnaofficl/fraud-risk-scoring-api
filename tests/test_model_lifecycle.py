from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from sklearn.pipeline import Pipeline

from app.main import app, lifespan
from app.core.config import settings


@pytest.mark.asyncio
async def test_startup_model_loading_and_state():
    """
    Verifies that the ML model pipeline is loaded into app.state
    during the FastAPI lifespan context manager.
    """
    async with lifespan(app):
        # Inside the lifespan context, app.state must contain the loaded model
        assert hasattr(app.state, "model_pipeline")
        assert isinstance(app.state.model_pipeline, Pipeline)
        assert hasattr(app.state, "model_version")
        assert app.state.model_version == settings.MODEL_VERSION

    # After lifespan exits, pipeline is cleanly set to None
    assert app.state.model_pipeline is None



@pytest.mark.asyncio
async def test_startup_missing_model_raises_error(monkeypatch):
    """
    Verifies that missing model artifact causes a clean, fast failure.
    """
    monkeypatch.setattr(settings, "MODEL_PATH", "artifacts/non_existent_model.joblib")
    
    with pytest.raises(FileNotFoundError) as exc_info:
        async with lifespan(app):
            pass
    assert "Model artifact not found" in str(exc_info.value)
