import io
import json
import logging
import sys
import pytest
from asgi_correlation_id import correlation_id
from httpx import ASGITransport, AsyncClient
from fastapi import status

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.main import app


def test_structlog_emits_structured_keys(monkeypatch):
    """Verify structlog captures timestamp, level, event, and correlation ID."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    original_json_flag = settings.LOG_JSON_FORMAT
    settings.LOG_JSON_FORMAT = True
    setup_logging()

    try:
        correlation_id.set("trace-structlog-test-123")
        logger = get_logger("tests.unit")
        logger.info("loan_evaluation_started", applicant_id="appl_test_001", risk_tier="A")

        output = stream.getvalue().strip()
        assert output, "Log output should not be empty"

        log_entry = json.loads(output.splitlines()[-1])
        assert log_entry["event"] == "loan_evaluation_started"
        assert log_entry["applicant_id"] == "appl_test_001"
        assert log_entry["risk_tier"] == "A"
        assert log_entry["level"] == "info"
        assert log_entry["correlation_id"] == "trace-structlog-test-123"
        assert "timestamp" in log_entry
        assert "logger" in log_entry
    finally:
        settings.LOG_JSON_FORMAT = original_json_flag
        setup_logging()


def test_stdlib_logging_interception(monkeypatch):
    """Verify standard Python logging calls (from libraries) are routed through structlog."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    original_json_flag = settings.LOG_JSON_FORMAT
    settings.LOG_JSON_FORMAT = True
    setup_logging()

    try:
        correlation_id.set("trace-stdlib-interception-456")
        stdlib_logger = logging.getLogger("test_external_library")
        stdlib_logger.info("Executed database query statement")

        output = stream.getvalue().strip()
        assert output, "Log output should not be empty"

        log_entry = json.loads(output.splitlines()[-1])
        assert "Executed database query statement" in log_entry["event"]
        assert log_entry["level"] == "info"
        assert log_entry["correlation_id"] == "trace-stdlib-interception-456"
        assert "timestamp" in log_entry
    finally:
        settings.LOG_JSON_FORMAT = original_json_flag
        setup_logging()


@pytest.mark.asyncio
async def test_request_logging_middleware(monkeypatch):
    """Verify RequestLoggingMiddleware captures HTTP method, path, status, latency_ms, and correlation_id."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    original_json_flag = settings.LOG_JSON_FORMAT
    settings.LOG_JSON_FORMAT = True
    setup_logging()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health", headers={"X-Request-ID": "test-req-middleware-999"})
            assert resp.status_code == status.HTTP_200_OK

        output = stream.getvalue().strip()
        assert output, "Log stream should have recorded http_request_finished"

        # Find the http_request_finished log line
        req_lines = [
            json.loads(line) for line in output.splitlines()
            if "http_request_finished" in line
        ]
        assert len(req_lines) > 0, "Expected http_request_finished event in logs"
        req_log = req_lines[-1]

        assert req_log["event"] == "http_request_finished"
        assert req_log["http_method"] == "GET"
        assert req_log["path"] == "/health"
        assert req_log["status_code"] == 200
        assert "latency_ms" in req_log
        assert isinstance(req_log["latency_ms"], (int, float))
        assert req_log["correlation_id"] == "test-req-middleware-999"
    finally:
        settings.LOG_JSON_FORMAT = original_json_flag
        setup_logging()
