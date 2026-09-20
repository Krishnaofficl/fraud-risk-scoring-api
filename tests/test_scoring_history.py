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
async def test_scoring_history_pagination_and_isolation():
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
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

            # 2. Insert test records directly for User A
            rec_approve_id = uuid.uuid4()
            rec_review_id = uuid.uuid4()
            rec_deleted_id = uuid.uuid4()

            async with async_session_maker() as session:
                rec_approve = ScoringRequest(
                    id=rec_approve_id,
                    user_id=user_a_id,
                    input_features={"amount": 30000},
                    predicted_probability=0.1500,
                    decision="APPROVE",
                    model_version="v1-baseline",
                )
                rec_review = ScoringRequest(
                    id=rec_review_id,
                    user_id=user_a_id,
                    input_features={"amount": 50000},
                    predicted_probability=0.3200,
                    decision="REVIEW",
                    model_version="v1-baseline",
                )
                rec_deleted = ScoringRequest(
                    id=rec_deleted_id,
                    user_id=user_a_id,
                    input_features={"amount": 70000},
                    predicted_probability=0.5500,
                    decision="DENY",
                    model_version="v1-baseline",
                    deleted_at=datetime.now(timezone.utc),  # Soft-deleted
                )
                session.add_all([rec_approve, rec_review, rec_deleted])
                await session.commit()

            # 3. Test Tenant Isolation: User B sees empty history
            history_b = await client.get("/v1/scores", headers=headers_b)
            assert history_b.status_code == 200
            assert history_b.json()["total"] == 0
            assert len(history_b.json()["items"]) == 0

            # 4. Test User A History: Sees active records, excludes soft-deleted
            history_a = await client.get("/v1/scores", headers=headers_a)
            assert history_a.status_code == 200
            res_a = history_a.json()
            assert res_a["total"] == 2  # Only active records
            assert len(res_a["items"]) == 2

            # 5. Test Pagination
            page_1 = await client.get("/v1/scores?limit=1&offset=0", headers=headers_a)
            assert page_1.status_code == 200
            assert len(page_1.json()["items"]) == 1
            assert page_1.json()["total"] == 2

            page_2 = await client.get("/v1/scores?limit=1&offset=1", headers=headers_a)
            assert page_2.status_code == 200
            assert len(page_2.json()["items"]) == 1
            # Ensure items on page 1 and page 2 are different
            assert page_1.json()["items"][0]["request_id"] != page_2.json()["items"][0]["request_id"]

            # 6. Test Decision Filter
            filtered_decision = await client.get("/v1/scores?decision=APPROVE", headers=headers_a)
            assert filtered_decision.status_code == 200
            assert filtered_decision.json()["total"] == 1
            assert filtered_decision.json()["items"][0]["decision"] == "APPROVE"

            # 7. Test Probability Range Filter
            filtered_range = await client.get("/v1/scores?min_score=0.20&max_score=0.40", headers=headers_a)
            assert filtered_range.status_code == 200
            assert filtered_range.json()["total"] == 1
            assert filtered_range.json()["items"][0]["decision"] == "REVIEW"

            # 8. Clean up
            async with async_session_maker() as session:
                await session.execute(delete(ScoringRequest).where(ScoringRequest.user_id.in_([user_a_id, user_b_id])))
                await session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
                await session.commit()
