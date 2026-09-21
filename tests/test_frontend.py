import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import status

from app.main import app


@pytest.mark.asyncio
async def test_frontend_root_serves_html():
    """Verify GET / returns 200 OK with FraudScope Codeforces-themed HTML dashboard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")
        content = response.text
        assert "FraudScope" in content
        assert "cf-logo-bars" in content
        assert "cf-bar-green" in content
        assert "cf-bar-blue" in content
        assert "cf-bar-red" in content
        # Verify no "//" in front of captions
        assert "<span>// Submit" not in content
        assert "<span>// Session" not in content
        assert "<span>// Risk" not in content
        assert "<span>// System" not in content
        assert "verdictBanner" in content
        assert "submissionsTableBody" in content


@pytest.mark.asyncio
async def test_frontend_dashboard_alias():
    """Verify GET /dashboard also serves the dashboard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/dashboard")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers.get("content-type", "")
        assert "FraudScope" in response.text


@pytest.mark.asyncio
async def test_frontend_login_and_register_pages():
    """Verify GET /login and GET /register serve standalone auth pages."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check /login
        res_login = await client.get("/login")
        assert res_login.status_code == status.HTTP_200_OK
        assert "text/html" in res_login.headers.get("content-type", "")
        assert "Sign In to FraudScope" in res_login.text
        assert "cf-bar-green" in res_login.text

        # Check /register
        res_reg = await client.get("/register")
        assert res_reg.status_code == status.HTTP_200_OK
        assert "text/html" in res_reg.headers.get("content-type", "")
        assert "Register Account on FraudScope" in res_reg.text
        assert "cf-bar-green" in res_reg.text


@pytest.mark.asyncio
async def test_frontend_static_assets():
    """Verify static assets are served properly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Check style.css
        res_css = await client.get("/static/style.css")
        assert res_css.status_code == status.HTTP_200_OK
        assert "text/css" in res_css.headers.get("content-type", "")
        assert ".cf-bar-green" in res_css.text
        assert ".cf-bar-blue" in res_css.text
        assert ".cf-bar-red" in res_css.text
        assert "#3B5998" in res_css.text

        # Check app.js
        res_js = await client.get("/static/app.js")
        assert res_js.status_code == status.HTTP_200_OK
        assert "PRESETS" in res_js.text
        assert "handleScoreSubmit" in res_js.text
