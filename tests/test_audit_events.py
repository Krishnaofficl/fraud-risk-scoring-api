import io
import json
import sys
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import status

from app.core.config import settings
from app.core.logging import setup_logging
from app.main import app, lifespan


@pytest.mark.asyncio
async def test_auth_audit_events(monkeypatch):
    """Verify auth attempts emit structured audit events (register, login success/fail)."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    original_json_flag = settings.LOG_JSON_FORMAT
    settings.LOG_JSON_FORMAT = True
    setup_logging()

    test_email = f"audit_user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "AuditSuperSecretPassword123!"

    try:
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # 1. Register Success
                reg_resp = await client.post("/auth/register", json={"email": test_email, "password": test_password})
                assert reg_resp.status_code == status.HTTP_201_CREATED

                # 2. Register Duplicate (Conflict)
                dup_resp = await client.post("/auth/register", json={"email": test_email, "password": test_password})
                assert dup_resp.status_code == status.HTTP_409_CONFLICT

                # 3. Login Bad Password
                bad_resp = await client.post("/auth/login", json={"email": test_email, "password": "WrongPassword!"})
                assert bad_resp.status_code == status.HTTP_401_UNAUTHORIZED

                # 4. Login Success
                login_resp = await client.post("/auth/login", json={"email": test_email, "password": test_password})
                assert login_resp.status_code == status.HTTP_200_OK

        output = stream.getvalue()
        lines = [json.loads(line) for line in output.splitlines() if line.strip().startswith("{")]

        events = [entry.get("event") for entry in lines]
        assert "auth_register_success" in events
        assert "auth_register_conflict" in events
        assert "auth_login_failed" in events
        assert "auth_login_success" in events

        # Verify failure reason logged
        failed_log = next(e for e in lines if e.get("event") == "auth_login_failed")
        assert failed_log["reason"] == "invalid_credentials"
        assert failed_log["email"] == test_email
    finally:
        settings.LOG_JSON_FORMAT = original_json_flag
        setup_logging()


@pytest.mark.asyncio
async def test_scoring_audit_event_no_pii(monkeypatch):
    """Verify scoring decisions emit audit logs without leaking applicant PII."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    original_json_flag = settings.LOG_JSON_FORMAT
    settings.LOG_JSON_FORMAT = True
    setup_logging()

    user_email = f"audit_scorer_{uuid.uuid4().hex[:8]}@example.com"
    user_password = "AuditPassword123!"

    payload = {
        "disbursed_amount": 50000,
        "asset_cost": 65000,
        "ltv": 76.92,
        "branch_id": 67,
        "supplier_id": 22807,
        "manufacturer_id": 45,
        "current_pincode_id": 1441,
        "date_of_birth": "15-06-1988",
        "employment_type": "Salaried",
        "disbursal_date": "10-10-2018",
        "state_id": 6,
        "employee_code_id": 1998,
        "mobileno_avl_flag": 1,
        "aadhar_flag": 1,
        "pan_flag": 0,
        "voterid_flag": 0,
        "driving_flag": 0,
        "passport_flag": 0,
        "perform_cns_score": 750,
        "perform_cns_score_description": "C-Very Low Risk",
        "pri_no_of_accts": 3,
        "pri_active_accts": 2,
        "pri_overdue_accts": 0,
        "pri_current_balance": 12000,
        "pri_sanctioned_amount": 50000,
        "pri_disbursed_amount": 50000,
        "sec_no_of_accts": 0,
        "sec_active_accts": 0,
        "sec_overdue_accts": 0,
        "sec_current_balance": 0,
        "sec_sanctioned_amount": 0,
        "sec_disbursed_amount": 0,
        "primary_instal_amt": 2500,
        "sec_instal_amt": 0,
        "new_accts_in_last_six_months": 1,
        "delinquent_accts_in_last_six_months": 0,
        "average_acct_age": "2yrs 1mon",
        "credit_history_length": "2yrs 6mon",
        "no_of_inquiries": 0
    }

    try:
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Register and login
                await client.post("/auth/register", json={"email": user_email, "password": user_password})
                login_resp = await client.post("/auth/login", json={"email": user_email, "password": user_password})
                token = login_resp.json()["access_token"]

                score_resp = await client.post(
                    "/v1/score",
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert score_resp.status_code == status.HTTP_201_CREATED
                score_id = score_resp.json()["request_id"]

                # Soft delete
                del_resp = await client.delete(
                    f"/v1/scores/{score_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert del_resp.status_code == status.HTTP_200_OK

        output = stream.getvalue()
        lines = [json.loads(line) for line in output.splitlines() if line.strip().startswith("{")]

        # Verify scoring audit log
        score_logs = [e for e in lines if e.get("event") == "scoring_decision_rendered"]
        assert len(score_logs) > 0
        score_log = score_logs[-1]

        assert "decision" in score_log
        assert "predicted_probability" in score_log
        assert "model_version" in score_log
        assert score_log["disbursed_amount"] == 50000

        # STRICT PII CHECK: Ensure no sensitive personal identifiers leaked into audit logs
        assert "date_of_birth" not in score_log
        assert "15-06-1988" not in str(score_log)
        assert "employee_code_id" not in score_log

        # Verify delete audit log
        delete_logs = [e for e in lines if e.get("event") == "scoring_evaluation_deleted"]
        assert len(delete_logs) > 0
        assert delete_logs[-1]["score_id"] == score_id
    finally:
        settings.LOG_JSON_FORMAT = original_json_flag
        setup_logging()
