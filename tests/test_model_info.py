import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app, lifespan


@pytest.mark.asyncio
async def test_get_model_info():
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/model/info")
            assert resp.status_code == 200
            data = resp.json()

            assert data["version"] == "v1-baseline"
            assert data["reported_auc"] == 0.6665
            assert data["paper_baseline_auc"] == 0.5180
            assert "model_pipeline.joblib" in data["artifact_path"]
            assert "trained_at" in data
