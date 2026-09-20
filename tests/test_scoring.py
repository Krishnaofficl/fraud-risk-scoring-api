import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app, lifespan
from app.db.session import async_session_maker
from app.models.user import User
from app.models.scoring import ScoringRequest
from app.schemas.scoring import RiskDecision


@pytest.mark.asyncio
async def test_score_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"disbursed_amount": 50000, "asset_cost": 65000, "ltv": 76.9}
        resp = await client.post("/v1/score", json=payload)
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_score_endpoint_success_and_persistence():
    unique_email = f"scorer_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperPassword123!"

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register & login
            reg_resp = await client.post(
                "/auth/register",
                json={"email": unique_email, "password": password},
            )
            assert reg_resp.status_code == 201
            user_id = uuid.UUID(reg_resp.json()["id"])

            login_resp = await client.post(
                "/auth/login",
                json={"email": unique_email, "password": password},
            )
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 2. Score applicant
            applicant_payload = {
                "disbursed_amount": 50000.0,
                "asset_cost": 65000.0,
                "ltv": 76.9,
                "branch_id": 67,
                "supplier_id": 22807,
                "manufacturer_id": 45,
                "current_pincode_id": 1441,
                "state_id": 6,
                "employee_code_id": 1998,
                "aadhar_flag": 1,
                "pan_flag": 0,
                "voterid_flag": 0,
                "driving_flag": 0,
                "passport_flag": 0,
                "perform_cns_score": 0,
                "pri_no_of_accts": 0,
                "pri_active_accts": 0,
                "pri_overdue_accts": 0,
                "pri_current_balance": 0.0,
                "pri_sanctioned_amount": 0.0,
                "pri_disbursed_amount": 0.0,
                "sec_no_of_accts": 0,
                "sec_active_accts": 0,
                "sec_overdue_accts": 0,
                "sec_current_balance": 0.0,
                "sec_sanctioned_amount": 0.0,
                "sec_disbursed_amount": 0.0,
                "primary_instal_amt": 0.0,
                "sec_instal_amt": 0.0,
                "new_accts_in_last_six_months": 0,
                "delinquent_accts_in_last_six_months": 0,
                "average_acct_age": "1yr 2mon",
                "credit_history_length": "2yrs 6mon",
                "no_of_inquiries": 0,
                "date_of_birth": "1987-01-01",
                "disbursal_date": "2018-08-01",
                "employment_type": "Salaried",
                "perform_cns_score_description": "No Bureau History Available",
            }

            score_resp = await client.post("/v1/score", json=applicant_payload, headers=headers)
            assert score_resp.status_code == 201, f"Expected 201, got {score_resp.status_code}: {score_resp.text}"
            data = score_resp.json()

            # Verify response schema fields
            assert "request_id" in data
            assert "probability" in data
            assert 0.0 <= data["probability"] <= 1.0
            assert data["decision"] in ("APPROVE", "REVIEW", "DENY")
            assert data["model_version"] == "v1-baseline"
            assert "created_at" in data

            req_uuid = uuid.UUID(data["request_id"])

            # 3. Verify Database Persistence in PostgreSQL
            async with async_session_maker() as session:
                stmt = select(ScoringRequest).where(ScoringRequest.id == req_uuid)
                result = await session.execute(stmt)
                db_record = result.scalar_one_or_none()
                assert db_record is not None
                assert db_record.user_id == user_id
                assert db_record.predicted_probability == data["probability"]
                assert db_record.decision == data["decision"]
                assert db_record.deleted_at is None
                assert db_record.input_features["DisbursedAmount"] == 50000.0 or db_record.input_features.get("disbursed_amount") == 50000.0

            # 4. Cleanup
            async with async_session_maker() as session:
                await session.execute(delete(ScoringRequest).where(ScoringRequest.id == req_uuid))
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
