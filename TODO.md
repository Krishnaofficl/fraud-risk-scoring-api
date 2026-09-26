# Project Checklist & Master TODO List

Tracking implementation progress for the **Fraud/Risk Scoring API** project across all 10 phases.

---

## Progress Overview

- [x] **Phase 0 — Environment & ML Reproduction** `[9/9]`
- [x] **Phase 1 — Project Skeleton & Configuration** `[7/7]`
- [x] **Phase 2 — Database Layer & Async Migrations** `[10/10]`
- [x] **Phase 3 — Modern Authentication** `[7/7]`
- [x] **Phase 4 — Core Scoring Endpoints** `[9/9]`
- [x] **Phase 5 — Error Handling & Resilience** `[5/5]`
- [x] **Web Portal — Codeforces-Themed Interface** (Interactive Scoring, History, Health)
- [x] **Phase 6 — Structured Logging & Correlation IDs** `[4/4]`
- [x] **Phase 7 — Testing Suite** `[9/9]`
- [ ] **Phase 8 — Containerization** `[0/5]`
- [ ] **Phase 9 — Cloud Deployment** `[0/5]`
- [ ] **Phase 10 — Documentation & Polish** `[0/5]`

---

## Phase 0 — Environment & ML Reproduction
> **Goal:** Acquire dataset, establish reproducible train/test splits, train `ColumnTransformer` + `XGBClassifier` pipeline, evaluate AUC against paper baseline, and serialize artifact.

- [x] **0.0 Git Initialization:** Initialize git repository on `main` branch (`git init -b main`).
- [x] **0.1 Virtual Environment:** Create and activate `.venv` with Python 3.11+ / 3.12 (`python -m venv .venv`).
- [x] **0.2 Install ML Packages:** Install modern ML libraries: `pandas>=2.0`, `scikit-learn>=1.4`, `xgboost>=2.0`, `joblib`, `kaggle`.
- [x] **0.3 Ingest Dataset:** Download Kaggle *Vehicle Loan Default Prediction* `train.csv` (233,154 rows) into `data/raw/` (via `scripts/download_data.py` or manual download).
- [x] **0.4 Standardized Split:** Verify exact 80/20 train/test split matching FDB specification: **186,523 train / 46,631 test**.
- [x] **0.5 Build Preprocessing Pipeline:** Define `ColumnTransformer` handling:
  - Median imputation and scaling for 22 numerical features.
  - Constant/mode imputation and `OneHotEncoder(handle_unknown="ignore")` for 13 categorical features.
  - Duration/date parsing for tenure and dates.
- [x] **0.6 Train Pipeline:** Fit unified `Pipeline([('preprocessor', ColumnTransformer), ('classifier', XGBClassifier)])`.
- [x] **0.7 Evaluate Holdout Test AUC:**
  - Compute ROC-AUC on the 46,631 test set (Achieved: **0.6665**).
  - Compare against paper's raw baselines: LightGBM `0.516`, CatBoost `0.518` (Tier 1 baseline ~0.52–0.55).
- [x] **0.8 Export & Document:**
  - Serialize pipeline to `artifacts/model_pipeline.joblib`.
  - Document exact methodology, split sizes, and AUC in `docs/REPRODUCTION.md`.

*Exit Criteria:* `artifacts/model_pipeline.joblib` exists, test AUC is calculated, and `docs/REPRODUCTION.md` is complete. ( All criteria met!)

---

## Phase 1 — Project Skeleton & Configuration
> **Goal:** Minimal runnable FastAPI application with robust environment configuration and liveness probe.

- [x] **1.1 Git Initialization:** Initialize git repository, configure `main` branch (Completed in 0.0).
- [x] **1.2 Gitignore Verification:** Ensure `.gitignore` correctly ignores `.env`, `data/raw/*.csv`, `artifacts/*.joblib`, and `__pycache__` (Verified).
- [x] **1.3 Settings Configuration:** Implement `app/core/config.py` using `pydantic-settings` (`BaseSettings`).
- [x] **1.4 Database URL Normalizer:** Add `@field_validator` in settings to automatically convert `postgres://` / `postgresql://` to `postgresql+asyncpg://`.
- [x] **1.5 Environment Template:** Create local `.env` from `.env.example` (Verified).
- [x] **1.6 FastAPI Lifespan & App Factory:** Set up `app/main.py` with `@asynccontextmanager` lifespan.
- [x] **1.7 Liveness Probe:** Implement `GET /health` returning `{"status": "ok"}`.

*Exit Criteria:* `uvicorn app.main:app --reload` runs cleanly and `GET /health` returns `200 OK`. ( All criteria met!)

---

## Phase 2 — Database Layer & Async Migrations
> **Goal:** Async PostgreSQL database connectivity, SQLAlchemy 2.0 models, and versioned Alembic migrations.

- [x] **2.1 Async Engine & Session:** Configure `create_async_engine` and `async_sessionmaker` with `asyncpg` in `app/db/session.py`.
- [x] **2.2 Declarative Base:** Create `Base` class inheriting `DeclarativeBase` in `app/db/base.py`.
- [x] **2.3 User ORM Model:** Define `User` model in `app/models/user.py` (`id`, `email`, `hashed_password`, `is_active`, `created_at`).
- [x] **2.4 Scoring Request ORM Model:** Define `ScoringRequest` model in `app/models/scoring.py` (`id`, `user_id`, `input_features` JSONB, `predicted_probability`, `decision`, `model_version`, `created_at`, `deleted_at`).
- [x] **2.5 Model Version ORM Model:** Define `ModelVersion` model in `app/models/model_version.py` (`version`, `trained_at`, `reported_auc`, `paper_baseline_auc`, `artifact_path`).
- [x] **2.6 Initialize Async Alembic:** Run `alembic init -t async alembic`.
- [x] **2.7 Configure Alembic `env.py`:** Import `Base.metadata` and configure `run_migrations_online` for async engine execution.
- [x] **2.8 Generate Initial Migration:** Run `alembic revision --autogenerate -m "initial schema"`.
- [x] **2.9 Apply Migration:** Apply migration to local PostgreSQL (`alembic upgrade head`) and verify tables in DB.
- [x] **2.10 Readiness Probe DB Ping:** Add database connectivity check (`SELECT 1`) to `GET /health/ready`.

*Exit Criteria:* Migrations apply cleanly to Postgres; `GET /health/ready` reports real database connection health. ( All criteria met!)

---

## Phase 3 — Modern Authentication
> **Goal:** Secure user registration, password hashing with bcrypt, JWT token generation with pyjwt, and route guarding.

- [x] **3.1 Password Security:** Implement `hash_password` and `verify_password` using `pwdlib` (Argon2id) in `app/core/security.py`.
- [x] **3.2 JWT Token Utilities:** Implement `create_access_token` and `decode_access_token` using `pyjwt[crypto]`.
- [x] **3.3 Auth Schemas:** Define `UserRegister`, `UserLogin`, `TokenResponse`, and `UserResponse` Pydantic schemas in `app/schemas/auth.py`.
- [x] **3.4 Registration Endpoint:** Implement `POST /auth/register` (hashes password, handles email uniqueness, stores user).
- [x] **3.5 Login Endpoint:** Implement `POST /auth/login` (verifies credentials, returns Bearer JWT).
- [x] **3.6 Auth Dependency:** Create `get_current_user` FastAPI dependency extracting and validating the Bearer token.
- [x] **3.7 User Profile Endpoint:** Implement protected `GET /v1/users/me` returning current user profile.

*Exit Criteria:* Can register, log in, receive a valid JWT, and authenticate against `/v1/users/me`; invalid/expired tokens return 401 Unauthorized. ( All criteria met!)

---

## Phase 4 — Core Scoring Endpoints
> **Goal:** High-throughput scoring endpoint with non-blocking model execution, Pydantic validation, and paginated query history.

- [x] **4.1 Startup Model Loading:** Load `artifacts/model_pipeline.joblib` into `app.state.model_pipeline` during FastAPI lifespan startup.
- [x] **4.2 38-Feature Pydantic Schema:** Define `LoanApplicantInput` schema in `app/schemas/scoring.py` with typed fields, descriptions, and OpenAPI examples.
- [x] **4.3 Scoring Response Schema:** Define `ScoringResultResponse` schema (`request_id`, `probability`, `decision`, `model_version`, `created_at`).
- [x] **4.4 POST `/v1/score` Endpoint:**
  - Validate 38 applicant features via Pydantic.
  - Convert input to a single-row DataFrame.
  - Execute non-blocking inference via `await asyncio.to_thread(pipeline.predict_proba, input_df)`.
  - Apply risk decision threshold (`< 0.20`: APPROVE, `0.20–0.40`: REVIEW, `> 0.40`: DENY).
  - Persist request, features JSONB, probability, decision, and model version to `scoring_requests`.
- [x] **4.5 GET `/v1/scores` Endpoint:** Paginated history list (`limit`, `offset`) with filters for date range, decision, and score threshold (owner-only, excludes soft-deleted).
- [x] **4.6 GET `/v1/scores/{id}` Endpoint:** Fetch single scoring request with owner-only authorization check.
- [x] **4.7 DELETE `/v1/scores/{id}` Endpoint:** Soft-delete scoring record (updates `deleted_at`) with owner-only authorization check.
- [x] **4.8 GET `/v1/model/info` Endpoint:** Return active model version, trained timestamp, and reproduced vs. paper baseline AUC.
- [x] **4.9 Seed Initial Model Version:** Seed `v1-baseline` record into `model_versions` table on startup or via migration.

*Exit Criteria:* Can submit applicant JSON, receive prediction in <10ms, and retrieve paginated user history. ( All criteria met!)

---

## Phase 5 — Error Handling & Resilience
> **Goal:** Graceful failure modes, standardized JSON error envelopes, and automated readiness health checking.

- [x] **5.1 Standardized Error Envelope:** Define uniform error schema (`detail`, `error_code`, `request_id`, `timestamp`).
- [x] **5.2 Custom Exceptions:** Define domain exceptions (`DatabaseUnavailableException`, `ModelNotLoadedException`, `EntityNotFoundException`).
- [x] **5.3 Global Exception Handlers:** Register handlers for `RequestValidationError`, `HTTPException`, and uncaught exceptions.
- [x] **5.4 Readiness Degradation Check:** Ensure `GET /health/ready` returns `HTTP 503 Service Unavailable` if database is down or model pipeline is missing from memory.
- [x] **5.5 Live Resilience Verification:** Stop PostgreSQL mid-session and verify the API returns clean 503 JSON without leaking stack traces.

*Exit Criteria:* Dependency disruptions result in clean, structured JSON errors rather than unhandled server crashes.

---

## Phase 6 — Structured Logging & Correlation IDs
> **Goal:** Distributed request tracing and machine-parseable JSON logs.

- [x] **6.1 Correlation ID Middleware:** Add `asgi-correlation-id` to capture or generate `X-Request-ID` on incoming requests.
- [x] **6.2 Structlog Configuration:** Set up `structlog` in `app/core/logging.py` emitting structured JSON logs with timestamp, level, event, and correlation ID.
- [x] **6.3 Contextual Request Logging:** Log HTTP request method, path, status code, latency, and client IP.
- [x] **6.4 Audit Events:** Add structured log events for authentication attempts, scoring decisions (excluding PII), and system exceptions.

*Exit Criteria:* Machine-readable JSON logs where individual requests can be traced end-to-end via `X-Request-ID`. ( All criteria met!)

---

## Phase 7 — Testing Suite
> **Goal:** Comprehensive unit and integration test coverage separating fast mocked tests from containerized database tests.

- [x] **7.1 Pytest Configuration:** Configure `pyproject.toml` / `pytest.ini` with `asyncio_mode = "auto"`.
- [x] **7.2 Unit Test — Security:** `tests/unit/test_security.py` (password hashing, bcrypt verify, JWT encode/decode, expired token rejection).
- [x] **7.3 Unit Test — Schemas:** `tests/unit/test_schemas.py` (38-feature validation, missing fields, type coercion, boundary checks).
- [x] **7.4 Unit Test — Scoring Logic:** `tests/unit/test_scoring.py` (decision threshold logic and probability bins with a mocked ML pipeline).
- [x] **7.5 Test Fixtures:** Set up `tests/conftest.py` with `httpx.AsyncClient`, event loop management, and test DB session overrides.
- [x] **7.6 Integration Test — Auth Routes:** `tests/integration/test_auth.py` (register, duplicate email rejection, login, `/v1/users/me`).
- [x] **7.7 Integration Test — Scoring Flow:** `tests/integration/test_scoring_flow.py` (score submission, DB persistence, pagination, filtering, soft-delete).
- [x] **7.8 Integration Test — Transaction Rollback:** Verify that a simulated database failure mid-request leaves no partial orphan writes.
- [x] **7.9 Integration Test — Health Probes:** Verify `/health` returns 200 and `/health/ready` returns 503 when the test DB is stopped.

*Exit Criteria:* Fast unit tests run in <2 seconds; integration tests pass 100% against real PostgreSQL. ( All criteria met!)

---

## Phase 8 — Containerization
> **Goal:** Reproducible, multi-stage Docker environment running the API and PostgreSQL with health checks.

- [x] **8.1 Multi-Stage Dockerfile:** Write `Dockerfile` with `python:3.12-slim` builder stage (compiling wheels) and a slim runtime stage.
- [x] **8.2 Docker Compose Stack:** Write `docker-compose.yml` defining `api` and `postgres` services with named volumes and environment variables.
- [x] **8.3 Healthchecks in Compose:** Add healthcheck conditions (`pg_isready` on postgres, curl `/health` on api) to ensure correct startup order.
- [x] **8.4 Test Compose Profile:** Create `docker-compose.test.yml` for running integration test suites inside isolated containers.
- [x] **8.5 Cold Boot Verification:** Test `docker compose up --build` from a clean terminal and verify Swagger UI at `http://localhost:8000/docs`.

*Exit Criteria:* A single `docker compose up` spins up a fully functioning, connected API and database. ( All criteria met!)

---

## Phase 9 — Cloud Deployment
> **Goal:** Public HTTPS deployment on Render, Railway, or Fly.io with managed PostgreSQL and automated migrations.

- [x] **9.1 Provision Cloud Database:** Create managed PostgreSQL instance on Render, Railway, or Fly.io (provisioned on Neon Serverless PostgreSQL with verified connectivity).
- [ ] **9.2 Cloud Environment Variables:** Configure `DATABASE_URL`, `JWT_SECRET`, `ENVIRONMENT=production`, and `DEBUG=false` in the cloud console.
- [ ] **9.3 Deploy API Service:** Deploy container or Git repository service hooked to the cloud PostgreSQL database.
- [ ] **9.4 Automated Migrations:** Configure build/release command to run `alembic upgrade head` before booting Uvicorn.
- [ ] **9.5 Verification:** Verify public endpoints (`/health`, `/health/ready`, `/docs`) and submit a live scoring test request over HTTPS.

*Exit Criteria:* A public HTTPS URL that interviewers and recruiters can interact with directly.

---

## Phase 10 — Documentation & Polish
> **Goal:** High-impact documentation and demonstration material for technical interviews.

- [ ] **10.1 Root README:** Complete `README.md` with system architecture diagram, quickstart commands, API reference, and live deployment link.
- [ ] **10.2 Finalize REPRODUCTION.md:** Document the exact train/test split numbers, reproduced AUC vs. paper baselines, and feature engineering stretch notes.
- [ ] **10.3 Swagger UI Docstrings:** Refine endpoint descriptions, summary tags, and request examples so Swagger `/docs` works seamlessly as a live interactive demo.
- [ ] **10.4 Git History Polish:** Ensure Git commit history is organized with clear, conventional commit messages reflecting incremental work.
- [ ] **10.5 Interview Talking Points:** Review knowledge check items (unit vs. integration tests, transaction rollback, correlation IDs, async event loop safety).

*Exit Criteria:* Anyone landing on the repository can understand, clone, run, and evaluate the project in under 5 minutes.
