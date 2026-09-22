"""
Integration tests for database transaction atomicity and rollback safety.
Verifies that simulated mid-request database exceptions, crashes, or commit failures
trigger complete rollbacks and leave zero partial or orphan writes in PostgreSQL.
"""

import uuid
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.session import async_session_maker, get_db
from app.models.scoring import ScoringRequest
from app.models.user import User


@pytest.mark.integration
class TestTransactionRollback:
    """Validates transactional integrity and zero orphan record persistence under failure."""

    async def test_registration_commit_failure_leaves_no_orphan_user(self, client: AsyncClient):
        """If database commit fails during registration, no orphan user is persisted in DB."""
        unique_email = f"fail_reg_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"

        # Create session override that fails on commit
        async def failing_get_db():
            async with async_session_maker() as session:
                original_commit = session.commit

                async def mock_commit():
                    await session.rollback()
                    raise OperationalError("Simulated write failure to PostgreSQL", params=None, orig=Exception("Disk full"))

                session.commit = mock_commit
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        from app.main import app, lifespan
        app.dependency_overrides[get_db] = failing_get_db

        try:
            async with lifespan(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app, raise_app_exceptions=False),
                    base_url="http://test",
                ) as failing_client:
                    resp = await failing_client.post(
                        "/auth/register",
                        json={"email": unique_email, "password": password},
                    )
                    assert resp.status_code == 500
        finally:
            app.dependency_overrides.pop(get_db, None)

        # Inspect database with fresh, uncompromised session: no orphan record must exist
        async with async_session_maker() as verify_session:
            stmt = select(User).where(User.email == unique_email)
            result = await verify_session.execute(stmt)
            orphan_user = result.scalar_one_or_none()
            assert orphan_user is None, "Transaction rollback failed: orphan user record was persisted!"

    async def test_scoring_commit_failure_leaves_no_orphan_scoring_request(
        self,
        authenticated_client: dict,
    ):
        """If database commit fails during scoring persistence, no orphan scoring record remains."""
        client = authenticated_client["client"]
        headers = authenticated_client["headers"]
        user_id = uuid.UUID(authenticated_client["user"]["id"])

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
            "date_of_birth": "1987-01-01",
            "disbursal_date": "2018-08-01",
            "employment_type": "Salaried",
        }

        # Count existing scoring records for this user
        async with async_session_maker() as count_session:
            stmt = select(ScoringRequest).where(ScoringRequest.user_id == user_id)
            initial_count = len((await count_session.execute(stmt)).scalars().all())

        # Inject commit failure into get_db
        async def failing_scoring_get_db():
            async with async_session_maker() as session:
                async def mock_commit():
                    await session.rollback()
                    raise OperationalError("Simulated lock contention timeout", params=None, orig=Exception("Lock wait timeout"))

                session.commit = mock_commit
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        from app.main import app, lifespan
        app.dependency_overrides[get_db] = failing_scoring_get_db

        try:
            async with lifespan(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app, raise_app_exceptions=False),
                    base_url="http://test",
                ) as failing_client:
                    resp = await failing_client.post("/v1/score", json=applicant_payload, headers=headers)
                    assert resp.status_code == 500
        finally:
            app.dependency_overrides.pop(get_db, None)

        # Confirm no orphan row was persisted
        async with async_session_maker() as verify_session:
            stmt = select(ScoringRequest).where(ScoringRequest.user_id == user_id)
            final_count = len((await verify_session.execute(stmt)).scalars().all())
            assert final_count == initial_count, "Transaction rollback failed: orphan scoring record was persisted!"
