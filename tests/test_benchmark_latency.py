import time
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete

from app.main import app, lifespan
from app.db.session import async_session_maker
from app.models.user import User
from app.models.scoring import ScoringRequest


@pytest.mark.asyncio
async def test_scoring_latency_benchmark():
    unique_email = f"bench_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperPassword123!"

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

    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            reg = await client.post("/auth/register", json={"email": unique_email, "password": password})
            user_id = uuid.UUID(reg.json()["id"])
            login = await client.post("/auth/login", json={"email": unique_email, "password": password})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            # Warmup call
            await client.post("/v1/score", json=applicant_payload, headers=headers)

            # Benchmark 20 iterations
            latencies = []
            for _ in range(20):
                start = time.perf_counter()
                resp = await client.post("/v1/score", json=applicant_payload, headers=headers)
                duration_ms = (time.perf_counter() - start) * 1000
                assert resp.status_code == 201
                latencies.append(duration_ms)

            avg_latency = sum(latencies) / len(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            print(f"\nBenchmark Results: Avg = {avg_latency:.2f} ms | P95 = {p95_latency:.2f} ms")

            # Clean up
            async with async_session_maker() as session:
                await session.execute(delete(ScoringRequest).where(ScoringRequest.user_id == user_id))
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
