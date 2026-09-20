import asyncio
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import ASGITransport, AsyncClient

from app.main import app, lifespan
from app.db.session import engine
from app.schemas.error import ErrorResponse


def run_cmd(cmd: str) -> str:
    """Helper to run a shell command and return its output."""
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command '{cmd}' failed: {res.stderr.strip()}")
    return res.stdout.strip()


async def main():
    print("=================================================================")
    print("  PHASE 5 LIVE RESILIENCE VERIFICATION SCRIPT")
    print("=================================================================")

    container_name = "fraud_db_dev"

    async with lifespan(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:

            # -------------------------------------------------------------
            # STEP A: Verify baseline health with PostgreSQL running
            # -------------------------------------------------------------
            print("\n[Step A] Checking /health/ready with PostgreSQL RUNNING...")
            resp_healthy = await client.get("/health/ready")
            print(f"  --> Status Code: {resp_healthy.status_code}")
            print(f"  --> Response Body: {json.dumps(resp_healthy.json(), indent=2)}")
            assert resp_healthy.status_code == 200, f"Expected 200, got {resp_healthy.status_code}"
            assert resp_healthy.json()["status"] == "ready"
            assert resp_healthy.json()["database"] == "connected"
            assert resp_healthy.json()["model_loaded"] is True
            print("  --> [PASS] Baseline check passed (200 OK).")

            try:
                # -------------------------------------------------------------
                # STEP B: Stop PostgreSQL container
                # -------------------------------------------------------------
                print(f"\n[Step B] Stopping Docker container '{container_name}'...")
                run_cmd(f"docker stop {container_name}")
                print(f"  --> Container '{container_name}' stopped successfully.")

                # Dispose active connections so pool does not reuse open sockets
                await engine.dispose()
                time.sleep(1.0)

                # -------------------------------------------------------------
                # STEP C: Verify degraded response returns 503 JSON without tracebacks
                # -------------------------------------------------------------
                print("\n[Step C] Checking /health/ready while PostgreSQL is STOPPED...")
                resp_down = await client.get("/health/ready")
                print(f"  --> Status Code: {resp_down.status_code}")
                data_down = resp_down.json()
                print(f"  --> Response Body: {json.dumps(data_down, indent=2)}")

                assert resp_down.status_code == 503, f"Expected 503, got {resp_down.status_code}"
                assert data_down["error_code"] == "DATABASE_UNAVAILABLE"
                assert "unreachable or degraded" in data_down["message"]
                assert "Traceback (most recent call last)" not in str(data_down)
                # Ensure it validates against the standardized ErrorResponse schema
                ErrorResponse.model_validate(data_down)
                print("  --> [PASS] Clean 503 Service Unavailable returned without leaking tracebacks.")

            finally:
                # -------------------------------------------------------------
                # STEP D: Restart PostgreSQL container
                # -------------------------------------------------------------
                print(f"\n[Step D] Restarting Docker container '{container_name}'...")
                run_cmd(f"docker start {container_name}")
                print(f"  --> Container '{container_name}' restarted.")

                # Dispose pool to discard stale broken connections
                await engine.dispose()

            # -------------------------------------------------------------
            # STEP E: Wait for PostgreSQL readiness and verify self-healing recovery
            # -------------------------------------------------------------
            print("\n[Step E] Verifying automatic self-healing recovery...")
            recovered = False
            for attempt in range(1, 15):
                time.sleep(1.0)
                try:
                    await engine.dispose()
                    resp_recovery = await client.get("/health/ready")
                    if resp_recovery.status_code == 200 and resp_recovery.json().get("status") == "ready":
                        print(f"  --> Attempt {attempt}: Recovered! Status: {resp_recovery.status_code}")
                        print(f"  --> Response: {resp_recovery.json()}")
                        recovered = True
                        break
                    else:
                        print(f"  --> Attempt {attempt}: Status {resp_recovery.status_code}, waiting...")
                except Exception as e:
                    print(f"  --> Attempt {attempt}: Retrying ({e})...")

            assert recovered, "PostgreSQL failed to recover within expected window."
            print("  --> [PASS] Self-healing recovery verified! (200 OK).")

    print("\n=================================================================")
    print("  LIVE RESILIENCE VERIFICATION SUCCESSFUL (100% PASS)")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())
