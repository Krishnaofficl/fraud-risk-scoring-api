# Fraud & Risk Scoring API (FraudScope)

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-95%20passed-success.svg)](https://github.com/Krishnaofficl/fraud-risk-scoring-api)
[![Live Demo](https://img.shields.io/badge/Render-Live%20Demo-46E3B7.svg?logo=render&logoColor=white)](https://fraud-risk-scoring-api-196d.onrender.com/)

An enterprise-grade, asynchronous FastAPI service reproducing Amazon's published **Fraud Dataset Benchmark (FDB)** `vehicleloan` sub-task ([arXiv:2208.14417](https://arxiv.org/abs/2208.14417)).

Demonstrates production backend engineering principles: async PostgreSQL persistence with connection pooling, versioned migrations, OWASP-standard Argon2id password hashing, PyJWT authentication, non-blocking ML pipeline inference, structured JSON logging with correlation IDs, comprehensive unit and transaction-rollback integration tests, multi-stage containerization, and public HTTPS cloud deployment.

---

## Live Cloud Deployment

| Service | Public URL | Description |
|---|---|---|
| **FraudScope Web Portal** | [https://fraud-risk-scoring-api-196d.onrender.com/](https://fraud-risk-scoring-api-196d.onrender.com/) | Interactive Codeforces-inspired competitive risk evaluation portal |
| **Interactive OpenAPI Docs** | [https://fraud-risk-scoring-api-196d.onrender.com/docs](https://fraud-risk-scoring-api-196d.onrender.com/docs) | Swagger UI for executing live interactive requests |
| **Dual-Readiness Health Probe** | [https://fraud-risk-scoring-api-196d.onrender.com/health/ready](https://fraud-risk-scoring-api-196d.onrender.com/health/ready) | Deep dependency check (PostgreSQL + ML Model Pipeline in memory) |
| **Liveness Health Probe** | [https://fraud-risk-scoring-api-196d.onrender.com/health](https://fraud-risk-scoring-api-196d.onrender.com/health) | Lightweight Kubernetes/Render ping probe |

---

## Machine Learning Benchmark Reproduction

* **Dataset:** Amazon Fraud Dataset Benchmark (`vehicleloan` task, 233,154 records, 41 features).
* **Train / Holdout Test Split:** Exact 80/20 chronological split (186,523 training records / 46,631 test records).
* **Architecture:** Unified Scikit-Learn `ColumnTransformer` (median/most-frequent imputation, OneHotEncoder) + `XGBClassifier` pipeline serialized with `joblib`.

### Benchmark Results Comparison

| Model Architecture | Source | Test ROC-AUC | Notes |
|---|---|---|---|
| **Random Forest Baseline** | Amazon FDB Paper (Table 4) | `0.5180` | Paper benchmark baseline |
| **XGBoost Pipeline (Ours)** | **This Service** | **`0.6665`** | **+28.7% relative improvement** over paper baseline |

*Detailed experimental splits, cross-validation metrics, and preprocessing rationale are documented in [docs/REPRODUCTION.md](docs/REPRODUCTION.md).*

---

## System Architecture

```
                             ┌──────────────────────────────────┐
                             │    Client Browser / API Client   │
                             │  (FraudScope Portal, Swagger, curl)│
                             └────────────────┬─────────────────┘
                                              │ HTTPS (Port 443)
                                              ▼
                             ┌──────────────────────────────────┐
                             │       FastAPI ASGI Server        │
                             │  ┌────────────────────────────┐  │
                             │  │      Middleware Pipeline   │  │
                             │  │  - asgi-correlation-id     │  │
                             │  │  - structlog request logger│  │
                             │  └─────────────┬──────────────┘  │
                             │                │                 │
                             │  ┌─────────────▼──────────────┐  │
                             │  │      Routing Controllers   │  │
                             │  │  - /auth (Argon2id + JWT)  │  │
                             │  │  - /v1/score (Inference)   │  │
                             │  │  - /v1/scores (Audit Query)│  │
                             │  │  - /v1/model (Metadata)    │  │
                             │  │  - /health (Dual Probes)   │  │
                             │  └─────────────┬──────────────┘  │
                             └────────────────┼─────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
                    ▼                                                   ▼
       ┌───────────────────────────┐                       ┌───────────────────────────┐
       │   In-Memory ML Pipeline   │                       │  PostgreSQL 16 Database   │
       │   (Loaded during startup) │                       │  (Neon Cloud / Local DB)  │
       │  - ColumnTransformer      │                       │  - users (Argon2id auth)  │
       │  - XGBClassifier          │                       │  - scoring_requests       │
       │  - asyncio.to_thread exec │                       │  - model_versions         │
       └───────────────────────────┘                       │  - alembic_version        │
                                                           └───────────────────────────┘
```

---

## Key Backend Features

1. **Non-Blocking Inference:** CPU-bound ML predictions run inside `await asyncio.to_thread(pipeline.predict_proba, df)` to ensure the asynchronous event loop is never blocked under concurrent traffic.
2. **Resilient Data Persistence:** All applicant features are validated across 38 typed attributes using Pydantic v2, normalized, and saved to PostgreSQL as queryable JSONB payloads.
3. **Transaction Rollback Safety:** Explicit database savepoints and session exception handling guarantee zero orphan records or partial writes if a query fails mid-request.
4. **Structured Correlation Logging:** Every HTTP request is tagged with an `X-Request-ID` correlation ID. Machine-readable JSON logs capture latency, status codes, and audit events (with zero PII).
5. **Dual-Readiness Probes:** `/health/ready` actively pings PostgreSQL and verifies the serialized pipeline is loaded in memory, gracefully returning HTTP 503 if any downstream component is degraded.
6. **Multi-Stage Containerization:** Optimized `python:3.12-slim` builder and runtime stages running as non-root `appuser` (`UID 1000`) with OpenMP support.

---

## API Reference

### 1. Authentication
* `POST /auth/register` — Register a new user account with unique email validation and Argon2id password hashing.
* `POST /auth/login` — Authenticate credentials and receive an HS256 signed JWT Bearer access token.
* `GET /v1/users/me` — Retrieve the currently authenticated user profile.

### 2. Risk Scoring & Historical Auditing
* `POST /v1/score` — Validate 38 applicant features, run XGBoost risk prediction, apply business decision thresholds (`APPROVE` < 0.20, `REVIEW` 0.20–0.40, `DENY` > 0.40), and persist audit record.
* `GET /v1/scores` — Paginated history of applicant risk scores with optional filters for `decision` (`APPROVE`, `REVIEW`, `DENY`), date ranges, and probability thresholds.
* `GET /v1/scores/{score_id}` — Retrieve detailed input features and inference decision for a specific scoring evaluation.
* `DELETE /v1/scores/{score_id}` — Soft-delete a historical scoring evaluation (tenant-isolated).

### 3. Model Information & System Health
* `GET /v1/model/info` — Active ML pipeline metadata, version name, training date, and benchmark metrics.
* `GET /health` — Liveness probe (HTTP 200 OK without dependencies).
* `GET /health/ready` — Dual readiness probe (HTTP 200 if DB is connected and ML model is loaded; HTTP 503 on degradation).

---

## Quickstart & Running Locally

### Option 1: Docker Compose (Recommended)

Boot the entire stack (FastAPI server + PostgreSQL + health checks + automated migrations) with a single command:

```bash
docker compose up --build
```

- API Server: `http://localhost:8000`
- Swagger Documentation: `http://localhost:8000/docs`
- FraudScope Web Portal: `http://localhost:8000/`

---

### Option 2: Native Virtual Environment

```bash
# 1. Clone repository
git clone https://github.com/Krishnaofficl/fraud-risk-scoring-api.git
cd fraud-risk-scoring-api

# 2. Create and activate virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install production dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env

# 5. Apply database migrations
alembic upgrade head

# 6. Start Uvicorn development server
uvicorn app.main:app --reload --port 8000
```

---

## Automated Testing Suite

The project includes 95 automated unit and integration tests covering security, schemas, scoring boundaries, real database transactions, and health checks.

```bash
# Run unit tests only (<2s, isolated in-memory)
pytest tests/unit -v

# Run full test suite (unit + integration tests)
pytest -v

# Run full test suite inside an isolated Docker container with tmpfs database:
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test_runner
```

### Test Suite Summary
- **51 Unit Tests (`tests/unit/`):** Password hashing, JWT claims, 38-feature boundary validation, PascalCase/CSV alias parsing, decision thresholds.
- **44 Integration Tests (`tests/integration/`):** PostgreSQL persistence, duplicate user rejection, tenant-isolated pagination, transaction rollbacks on simulated mid-request failure, graceful 503 degradation.

---

## Project Structure

```
fraud-risk-scoring-api/
├── alembic/                    # Async database migration versions
├── app/                        # Core application package
│   ├── core/                   # Settings, security (Argon2id/JWT), structured logging
│   ├── db/                     # Asyncpg connection pool & Base models
│   ├── models/                 # SQLAlchemy 2.0 ORM models (User, ScoringRequest, ModelVersion)
│   ├── routers/                # FastAPI endpoint routers (auth, score, model, health)
│   ├── schemas/                # Pydantic v2 request/response validation schemas
│   ├── services/               # Inference engine & async threadpool executor
│   ├── static/                 # FraudScope Web Portal (HTML/CSS/JS)
│   └── main.py                 # ASGI factory, lifespan event handler, middleware
├── artifacts/                  # Serialized ML model pipeline (ColumnTransformer + XGBoost)
├── data/                       # Dataset directories (.gitkeep)
├── docs/                       # Comprehensive documentation & research reports
│   ├── REPRODUCTION.md         # FDB paper baseline reproduction & methodology
│   ├── INTERVIEW_GUIDE.md      # Senior engineering interview defense guide & architecture deep-dive
│   └── RESUME_POINTS.md        # ATS-optimized resume bullet points, metrics, and STAR stories
├── scripts/                    # Ingestion & training scripts (train.py, download_data.py)
├── tests/                      # Pytest automated test suite
│   ├── unit/                   # In-memory unit tests
│   ├── integration/            # Real database integration tests
│   └── conftest.py             # Global AsyncClient fixtures & session isolation
├── docker-compose.yml          # Production container stack
├── docker-compose.test.yml     # Isolated container test profile
├── Dockerfile                  # Multi-stage container build (builder, test, runtime)
├── render.yaml                 # Render cloud blueprint (Infrastructure as Code)
├── requirements.txt            # Production dependencies
└── TODO.md                     # Micro-step execution log across all 10 phases
```

---

## License

This project is open-source under the MIT License.
