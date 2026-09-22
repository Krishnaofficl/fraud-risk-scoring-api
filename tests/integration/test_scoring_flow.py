"""
Integration tests for the core fraud risk scoring flow.
Covers applicant evaluation, real ML model inference, database persistence,
pagination, risk decision filtering, single record inspection, owner-only isolation,
soft-deletion lifecycle, and model metadata inspection.
Runs against the live PostgreSQL database container.
"""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.scoring import ScoringRequest
from app.models.user import User


@pytest.fixture
def applicant_payload() -> dict:
    """Provides a realistic 38-feature applicant payload."""
    return {
        "disbursed_amount": 52000.0,
        "asset_cost": 68000.0,
        "ltv": 76.47,
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
        "perform_cns_score": 620,
        "pri_no_of_accts": 3,
        "pri_active_accts": 1,
        "pri_overdue_accts": 0,
        "pri_current_balance": 15000.0,
        "pri_sanctioned_amount": 40000.0,
        "pri_disbursed_amount": 40000.0,
        "sec_no_of_accts": 0,
        "sec_active_accts": 0,
        "sec_overdue_accts": 0,
        "sec_current_balance": 0.0,
        "sec_sanctioned_amount": 0.0,
        "sec_disbursed_amount": 0.0,
        "primary_instal_amt": 3200.0,
        "sec_instal_amt": 0.0,
        "new_accts_in_last_six_months": 1,
        "delinquent_accts_in_last_six_months": 0,
        "average_acct_age": "1yr 4mon",
        "credit_history_length": "2yrs 8mon",
        "no_of_inquiries": 0,
        "date_of_birth": "1989-03-21",
        "disbursal_date": "2018-09-15",
        "employment_type": "Salaried",
        "perform_cns_score_description": "C-Very Low Risk",
    }


@pytest.mark.integration
class TestScoringFlow:
    """End-to-end integration tests for loan evaluation, history, and record management."""

    async def test_score_unauthorized(self, client: AsyncClient, applicant_payload: dict):
        """Unauthenticated requests to /v1/score must receive 401."""
        resp = await client.post("/v1/score", json=applicant_payload)
        assert resp.status_code == 401

    async def test_score_submission_and_db_persistence(
        self,
        authenticated_client: dict,
        applicant_payload: dict,
        rollback_session,
    ):
        """Submitting valid applicant yields real ML prediction and persists record to DB."""
        client = authenticated_client["client"]
        headers = authenticated_client["headers"]
        user_id = uuid.UUID(authenticated_client["user"]["id"])

        score_resp = await client.post("/v1/score", json=applicant_payload, headers=headers)
        assert score_resp.status_code == 201, f"Expected 201, got {score_resp.status_code}: {score_resp.text}"

        data = score_resp.json()
        assert "request_id" in data
        assert "probability" in data
        assert 0.0 <= data["probability"] <= 1.0
        assert data["decision"] in ("APPROVE", "REVIEW", "DENY")
        assert data["model_version"] == "v1-baseline"
        assert "created_at" in data

        req_uuid = uuid.UUID(data["request_id"])

        # Verify record in DB
        stmt = select(ScoringRequest).where(ScoringRequest.id == req_uuid)
        result = await rollback_session.execute(stmt)
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.user_id == user_id
        assert record.predicted_probability == data["probability"]
        assert record.decision == data["decision"]
        assert record.deleted_at is None
        assert record.input_features is not None

    async def test_scoring_history_pagination_and_isolation(
        self,
        client: AsyncClient,
        rollback_session,
    ):
        """Users only see their own non-deleted scoring history with pagination."""
        # Create User A and User B
        email_a = f"history_a_{uuid.uuid4().hex[:8]}@example.com"
        email_b = f"history_b_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123!"

        reg_a = await client.post("/auth/register", json={"email": email_a, "password": password})
        user_a_id = uuid.UUID(reg_a.json()["id"])
        login_a = await client.post("/auth/login", json={"email": email_a, "password": password})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        reg_b = await client.post("/auth/register", json={"email": email_b, "password": password})
        login_b = await client.post("/auth/login", json={"email": email_b, "password": password})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # Seed 3 records for User A (one soft-deleted)
        rec1 = ScoringRequest(
            id=uuid.uuid4(),
            user_id=user_a_id,
            input_features={"amount": 40000},
            predicted_probability=0.1200,
            decision="APPROVE",
            model_version="v1-baseline",
        )
        rec2 = ScoringRequest(
            id=uuid.uuid4(),
            user_id=user_a_id,
            input_features={"amount": 60000},
            predicted_probability=0.3500,
            decision="REVIEW",
            model_version="v1-baseline",
        )
        rec_deleted = ScoringRequest(
            id=uuid.uuid4(),
            user_id=user_a_id,
            input_features={"amount": 80000},
            predicted_probability=0.5500,
            decision="DENY",
            model_version="v1-baseline",
            deleted_at=datetime.now(timezone.utc),
        )
        rollback_session.add_all([rec1, rec2, rec_deleted])
        await rollback_session.commit()

        # User B sees 0 records (tenant isolation)
        resp_b = await client.get("/v1/scores", headers=headers_b)
        assert resp_b.status_code == 200
        assert resp_b.json()["total"] == 0

        # User A sees exactly 2 active records
        resp_a = await client.get("/v1/scores", headers=headers_a)
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["total"] == 2
        assert len(data_a["items"]) == 2

        # Filter by decision
        resp_filter = await client.get("/v1/scores?decision=APPROVE", headers=headers_a)
        assert resp_filter.status_code == 200
        assert resp_filter.json()["total"] == 1
        assert resp_filter.json()["items"][0]["decision"] == "APPROVE"

    async def test_single_scoring_record_and_ownership(
        self,
        client: AsyncClient,
        rollback_session,
    ):
        """Users can fetch their own score by ID, but unauthorized users receive 403."""
        # Create Owner and Stranger
        email_owner = f"owner_{uuid.uuid4().hex[:8]}@example.com"
        email_stranger = f"stranger_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123!"

        reg_owner = await client.post("/auth/register", json={"email": email_owner, "password": password})
        owner_id = uuid.UUID(reg_owner.json()["id"])
        login_owner = await client.post("/auth/login", json={"email": email_owner, "password": password})
        headers_owner = {"Authorization": f"Bearer {login_owner.json()['access_token']}"}

        login_stranger = await client.post("/auth/register", json={"email": email_stranger, "password": password})
        login_stranger_token = (await client.post("/auth/login", json={"email": email_stranger, "password": password})).json()["access_token"]
        headers_stranger = {"Authorization": f"Bearer {login_stranger_token}"}

        score_id = uuid.uuid4()
        record = ScoringRequest(
            id=score_id,
            user_id=owner_id,
            input_features={"disbursed_amount": 55000},
            predicted_probability=0.1900,
            decision="APPROVE",
            model_version="v1-baseline",
        )
        rollback_session.add(record)
        await rollback_session.commit()

        # Owner fetches record -> 200 with input features
        resp_owner = await client.get(f"/v1/scores/{score_id}", headers=headers_owner)
        assert resp_owner.status_code == 200
        assert resp_owner.json()["request_id"] == str(score_id)
        assert "input_features" in resp_owner.json()

        # Stranger fetches record -> 403 Forbidden
        resp_stranger = await client.get(f"/v1/scores/{score_id}", headers=headers_stranger)
        assert resp_stranger.status_code == 403

        # Non-existent UUID -> 404
        resp_404 = await client.get(f"/v1/scores/{uuid.uuid4()}", headers=headers_owner)
        assert resp_404.status_code == 404

    async def test_soft_delete_lifecycle(
        self,
        client: AsyncClient,
        rollback_session,
    ):
        """Soft-deleting a record sets deleted_at, hides from history, and denies access."""
        email = f"delete_flow_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123!"

        reg = await client.post("/auth/register", json={"email": email, "password": password})
        user_id = uuid.UUID(reg.json()["id"])
        token = (await client.post("/auth/login", json={"email": email, "password": password})).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        score_id = uuid.uuid4()
        record = ScoringRequest(
            id=score_id,
            user_id=user_id,
            input_features={"disbursed_amount": 65000},
            predicted_probability=0.2500,
            decision="REVIEW",
            model_version="v1-baseline",
        )
        rollback_session.add(record)
        await rollback_session.commit()

        # Delete record
        del_resp = await client.delete(f"/v1/scores/{score_id}", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify DB deleted_at is populated
        stmt = select(ScoringRequest).where(ScoringRequest.id == score_id)
        result = await rollback_session.execute(stmt)
        db_rec = result.scalar_one()
        assert db_rec.deleted_at is not None

        # Fetching soft-deleted record returns 404
        get_resp = await client.get(f"/v1/scores/{score_id}", headers=headers)
        assert get_resp.status_code == 404

    async def test_model_info_endpoint(self, client: AsyncClient):
        """Public model info returns benchmark reproduction metadata."""
        resp = await client.get("/v1/model/info")
        assert resp.status_code == 200
        info = resp.json()
        assert info["version"] == "v1-baseline"
        assert info["reported_auc"] > 0.65
        assert info["paper_baseline_auc"] == 0.5180
        assert "artifacts/model_pipeline.joblib" in info["artifact_path"]
