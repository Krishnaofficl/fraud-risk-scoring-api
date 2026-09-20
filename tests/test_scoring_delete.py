import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app, lifespan
from app.db.session import async_session_maker
from app.models.user import User
from app.models.scoring import ScoringRequest


@pytest.mark.asyncio
async def test_soft_delete_lifecycle_and_security():
    user_a_email = f"delete_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"delete_b_{uuid.uuid4().hex[:8]}@example.com"
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

            # 2. Insert test record for User A
            rec_id = uuid.uuid4()
            async with async_session_maker() as session:
                rec = ScoringRequest(
                    id=rec_id,
                    user_id=user_a_id,
                    input_features={"disbursed_amount": 45000},
                    predicted_probability=0.1800,
                    decision="APPROVE",
                    model_version="v1-baseline",
                )
                session.add(rec)
                await session.commit()

            # 3. User B attempts to delete User A's record -> 403 Forbidden
            del_resp_b = await client.delete(f"/v1/scores/{rec_id}", headers=headers_b)
            assert del_resp_b.status_code == 403
            assert "Not authorized" in del_resp_b.json()["detail"]

            # 4. User A deletes own record -> 200 OK
            del_resp_a = await client.delete(f"/v1/scores/{rec_id}", headers=headers_a)
            assert del_resp_a.status_code == 200
            del_data = del_resp_a.json()
            assert del_data["status"] == "deleted"
            assert del_data["request_id"] == str(rec_id)
            assert "deleted_at" in del_data

            # 5. Subsequent GET by ID -> 404 Not Found
            get_resp = await client.get(f"/v1/scores/{rec_id}", headers=headers_a)
            assert get_resp.status_code == 404

            # 6. Subsequent GET history -> record is excluded
            history_resp = await client.get("/v1/scores", headers=headers_a)
            assert history_resp.status_code == 200
            assert history_resp.json()["total"] == 0

            # 7. Repeat DELETE -> 404 Not Found (cannot re-delete)
            repeat_del = await client.delete(f"/v1/scores/{rec_id}", headers=headers_a)
            assert repeat_del.status_code == 404

            # 8. Verify record STILL EXISTS in PostgreSQL with deleted_at set (audit retention)
            async with async_session_maker() as session:
                stmt = select(ScoringRequest).where(ScoringRequest.id == rec_id)
                res = await session.execute(stmt)
                db_record = res.scalar_one_or_none()
                assert db_record is not None
                assert db_record.deleted_at is not None

            # 9. Clean up
            async with async_session_maker() as session:
                await session.execute(delete(ScoringRequest).where(ScoringRequest.user_id.in_([user_a_id, user_b_id])))
                await session.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
                await session.commit()
