import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.db.session import async_session_maker, engine
from app.main import app
from app.models.user import User
from app.models.model_version import ModelVersion
from app.models.scoring import ScoringRequest


async def run_checks():
    print("=" * 60)
    print("PHASE 2 COMPREHENSIVE LIVE VERIFICATION")
    print("=" * 60)
    print(f"Target Database URL: {engine.url.render_as_string(hide_password=True)}")

    # 1. Direct Engine Connection
    print("\n[1/5] Testing Direct Async Engine Connection...")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT version();"))
        db_ver = res.scalar()
        print(f"  --> Connected successfully!")
        print(f"  --> PostgreSQL version: {db_ver}")

    # 2. Database Tables Verification
    print("\n[2/5] Testing Schema & Tables Created by Alembic...")
    async with async_session_maker() as session:
        res = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
        )
        tables = [row[0] for row in res.fetchall()]
        print(f"  --> Found tables in public schema: {tables}")
        required_tables = {"alembic_version", "model_versions", "scoring_requests", "users"}
        for t in required_tables:
            assert t in tables, f"Missing table: {t}"
            print(f"      [OK] Table '{t}' verified.")

    # 3. GET /health/ready (Live DB Ping)
    print("\n[3/5] Testing GET /health/ready (Live Endpoint)...")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health/ready")
        print(f"  --> HTTP Status Code: {resp.status_code}")
        print(f"  --> Response JSON: {resp.json()}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.json()["status"] == "ready"
        assert resp.json()["database"] == "connected"
        print("      [OK] Live readiness probe returned 200 OK and database is connected.")

    # 4. GET /health (Liveness)
    print("\n[4/5] Testing GET /health (Liveness Probe)...")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        print(f"  --> HTTP Status Code: {resp.status_code}")
        print(f"  --> Response JSON: {resp.json()}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        print("      [OK] Liveness probe returned 200 OK.")

    # 5. Full ORM Roundtrip CRUD (Insert, Read, Foreign Keys, Cascade Delete)
    print("\n[5/5] Testing ORM CRUD & Foreign Keys against Live Database...")
    test_id = uuid.uuid4().hex[:8]
    version_id = f"v_test_{test_id}"
    user_email = f"user_{test_id}@example.com"

    async with async_session_maker() as session:
        async with session.begin():
            # Create ModelVersion
            mv = ModelVersion(
                version=version_id,
                trained_at=datetime.now(timezone.utc),
                reported_auc=0.6665,
                paper_baseline_auc=0.5180,
                artifact_path="artifacts/model_pipeline.joblib",
            )
            session.add(mv)

            # Create User
            user = User(
                email=user_email,
                hashed_password="test_secure_hash_12345",
                is_active=True,
            )
            session.add(user)
            await session.flush()

            # Create ScoringRequest linked to both
            scoring = ScoringRequest(
                user_id=user.id,
                input_features={"feature_sample": 42.0, "ApplicantIncome": 50000},
                predicted_probability=0.185,
                decision="LOW_RISK",
                model_version=mv.version,
            )
            session.add(scoring)
            await session.flush()
            print(f"  --> Inserted User ID: {user.id}")
            print(f"  --> Inserted ModelVersion: {mv.version}")
            print(f"  --> Inserted ScoringRequest ID: {scoring.id}")

            # Verify Query
            res = await session.execute(
                text("SELECT count(*) FROM scoring_requests WHERE id = :id"),
                {"id": scoring.id}
            )
            count = res.scalar()
            assert count == 1, "Scoring request not found in database!"
            print(f"      [OK] Successfully queried inserted record (count={count}).")

            # Clean up
            await session.delete(scoring)
            await session.delete(user)
            await session.delete(mv)
            print("      [OK] Cleaned up test data cleanly.")

    print("\n" + "=" * 60)
    print("ALL PHASE 2 CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_checks())
