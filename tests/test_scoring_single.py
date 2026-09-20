import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete

from app.main import app, lifespan
from app.db.session import async_session_maker
from app.models.user import User
from app.models.scoring import ScoringRequest


@pytest.mark.asyncio
async def test_get_single_score_and_ownership_guard():
    user_a_email = f"single_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"single_b_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperPassword123!"

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register User A and User B
            reg_a = await client.post("/auth/register", json={"email": user_a_email, "password": password})
            assert reg_a.status_code == 201
            user_a_id = uuid.UUID(reg_a.json()["id"])

            reg_b = await client.post("/auth/register", json={"email": user_b_email, "password": password})
            assert reg_b.status_code == 201
            user_b_id = uuid.UUID(reg_b.json()["id"])

            # Login both
            login_a = await client.post("/auth/login", json={"email": user_a_email, "password": password})
            token_a = login_a.json()["access_token"]
            headers_a = {"Authorization": f"Bearer {token_a}"}

            login_b = await client.post("/auth/login", json={"email": user_b_email, "password": password})
            token_b = login_b.json()["access_token"]
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # 2. Insert test records for User A
            rec_id = uuid.uuid4()
            deleted_rec_id = uuid.uuid4()

            async with async_session_maker() as session:
                rec = ScoringRequest(
                    id=rec_id,
                    user_id=user_a_id,
                    input_features={"disbursed_amount": 55000, "ltv": 78.5},
                    predicted_probability=0.2150,
                    decision="REVIEW",
                    model_version="v1-baseline",
                )
                deleted_rec = ScoringRequest(
                    id=deleted_rec_id,
                    user_id=user_a_id,
                    input_features={"disbursed_amount": 60000},
                    predicted_probability=0.4500,
                    decision="DENY",
                    model_version="v1-baseline",
                    deleted_at=datetime.now(timezone.utc),
                )
                session.add_all([rec, deleted_rec])
                await session.commit()

            # 3. User A retrieves own score -> 200 OK with full details
            resp_a = await client.get(f"/v1/scores/{rec_id}", headers=headers_a)
            assert resp_a.status_code == 200
            data_a = resp_a.json()
            assert data_a["request_id"] == str(rec_id)
            assert data_a["probability"] == 0.2150
            assert data_a["decision"] == "REVIEW"
            assert data_a["user_id"] == str(user_a_id)
            assert data_a["input_features"]["disbursed_amount"] == 55000

            # 4. User B attempts to access User A's score -> 403 Forbidden
            resp_b = await client.get(f"/v1/scores/{rec_id}", headers=headers_b)
            assert resp_b.status_code == 403
            assert "Not authorized" in resp_b.json()["detail"]

            # 5. Non-existent UUID -> 404 Not Found
            non_existent_id = uuid.uuid4()
            resp_404 = await client.get(f"/v1/scores/{non_existent_id}", headers=headers_a)
            assert resp_404.status_code == 404

            # 6. Soft-deleted record -> 404 Not Found
            resp_deleted = await client.get(f"/v1/scores/{deleted_rec_id}", headers=headers_a)
            assert resp_deleted.status_code == 404

            # 7. Unauthenticated request -> 401 Unauthorized
            resp_unauth = await client.get(f"/v1/scores/{rec_id}")
            assert resp_unauth.status_code == 401

            # 8. Clean up
            async with async_session_maker() as session:
                await session.execute(delete(ScoringRequest).where(ScoringRequest.user_id.in_([user_a_id, user_b_id])))
                await session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
                await session.commit()
