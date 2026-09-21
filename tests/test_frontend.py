import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import status

from app.main import app


@pytest.mark.asyncio
async def test_frontend_root_serves_html():
    """Verify GET / returns 200 OK with Codeforces-themed HTML dashboard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")
        content = response.text
        assert "FraudForces" in content
        assert "cf-logo-bars" in content
        assert "verdictBanner" in content
        assert "submissionsTableBody" in content


@pytest.mark.asyncio
async def test_frontend_dashboard_alias():
    """Verify GET /dashboard also serves the dashboard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")
        assert "FraudForces" in response.text


@pytest.mark.asyncio
async def test_frontend_static_assets():
    """Verify static assets are served properly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check style.css
        res_css = await client.get("/static/style.css")
        assert res_css.status_code == status.HTTP_200_OK
        assert "text/css" in res_css.headers.get("content-type", "")
        assert ".cf-bar" in res_css.text
        assert "#3B5998" in res_css.text

        # Check app.js
        res_js = await client.get("/static/app.js")
        assert res_js.status_code == status.HTTP_200_OK
        assert "PRESETS" in res_js.text
        assert "handleScoreSubmit" in res_js.text
