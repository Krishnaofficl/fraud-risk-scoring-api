# Fraud/Risk Scoring API — Implementation Plan (Updated & Corrected)

**Project:** Reproduce Amazon's Fraud Dataset Benchmark (FDB) `vehicleloan` sub-task, wrap it as a production-shaped FastAPI service.

**Core goal:** Prove you can build ordinary, reliable backend software correctly — auth, persistence, migrations, validation, testing, containerization, deployment — using a legitimate published benchmark as the anchor for the ML piece.

---

## 1. Tech Stack

| Layer | Tool | Purpose | Notes / Feasibility Fixes |
|---|---|---|---|
| Language/runtime | Python 3.11+ / 3.12 | Base environment | Windows & Linux compatible |
| Web framework | FastAPI | API layer | Modern async framework with automatic OpenAPI docs |
| ASGI server | Uvicorn | Runs the app | Standard async server |
| Database | PostgreSQL | Persistence | Relational store with JSONB support |
| Database Driver | `asyncpg` | Async DB driver | Native async driver for SQLAlchemy 2.0 |
| ORM | SQLAlchemy 2.0 (async) | DB access layer | Async engine and DeclarativeBase models |
| Migrations | Alembic (async) | Versioned schema changes | Initialized with `alembic init -t async` |
| Validation | Pydantic v2 | Request/response schemas | Fast, strongly-typed schemas with field examples |
| Auth | `bcrypt` + `pyjwt[crypto]` | Password hashing & JWT auth | Replaces deprecated `passlib` & `python-jose` |
| Rate limiting (optional) | `slowapi` | Basic API security | Rate limits public auth endpoints |
| ML — dataset source | Kaggle / LTFS Vehicle Loan | Standardized benchmark data | 233,154 records, 80/20 train/test split |
| ML — model & pipeline | `xgboost` + `scikit-learn` | End-to-end classification pipeline | `ColumnTransformer` + `XGBClassifier` in single Pipeline |
| ML — serialization | `joblib` | Save/load pipeline artifact | Serializes preprocessing + estimator into `artifacts/` |
| Testing | `pytest`, `pytest-asyncio`, `httpx` | Unit + integration tests | Split into `tests/unit/` (mocked) & `tests/integration/` (DB) |
| Logging & Tracing | `structlog` + `asgi-correlation-id` | Structured JSON logs + tracing | Propagates `X-Request-ID` across request lifecycles |
| Containerization | Docker, Docker Compose | API + Postgres | Multi-stage Dockerfile, reproducible runtime |
| Deployment | Railway / Render / Fly.io | Public hosting | Low memory footprint (<200MB, fits in 512MB tier) |
| Config | Pydantic `BaseSettings` (`pydantic-settings`) | Env-var driven config | Normalizes `postgres://` to `postgresql+asyncpg://` |
| VCS | Git | Version control | Structured feature branches and PRs |
| CI | GitHub Actions | CI/CD | Runs linting and tests automatically |

---

## 2. Architecture

```
                          ┌─────────────────────┐
                          │   Client / Swagger   │
                          │   (docs, curl, UI)   │
                          └──────────┬───────────┘
                                     │ HTTPS
                                     ▼
                          ┌─────────────────────┐
                          │   FastAPI app        │
                          │  ┌────────────────┐ │
                          │  │ Routers:        │ │
                          │  │ - /auth         │ │
                          │  │ - /v1/score     │ │
                          │  │ - /v1/scores    │ │
                          │  │ - /v1/model     │ │
                          │  │ - /health       │ │
                          │  └────────────────┘ │
                          │  ┌────────────────┐ │
                          │  │ Middleware:     │ │
                          │  │ - correlation_id│ │
                          │  │ - structlog     │ │
                          │  │ - rate limit    │ │
                          │  └────────────────┘ │
                          └──────────┬───────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                                       ▼
      ┌─────────────────────┐                 ┌─────────────────────┐
      │  Model Artifact     │                 │  PostgreSQL         │
      │  (joblib pipeline   │                 │  - users            │
      │   loaded at startup)│                 │  - scoring_requests │
      │  - ColumnTransformer│                 │  - model_versions   │
      │  - XGBClassifier    │                 └─────────────────────┘
      └─────────────────────┘
```

**Offline path (`scripts/train.py`):**
`Raw Kaggle/LTFS CSV → pandas DataFrame → ColumnTransformer (impute median/mode + OneHotEncoder) + XGBClassifier Pipeline → evaluate AUC on 46,631 test split → save artifacts/model_pipeline.joblib`

**Online path (the API):**
`Request JSON → Pydantic validation (38 features) → Auth check (JWT) → asyncio.to_thread(pipeline.predict_proba) → Persist to Postgres JSONB → Return response`

---

## 3. Database Schema

**`users`**
| column | type | notes |
|---|---|---|
| `id` | UUID PK | `uuid4` default |
| `email` | string, unique, indexed | Applicant/client email |
| `hashed_password` | string | bcrypt hash |
| `is_active` | boolean | default `True` |
| `created_at` | timestamp (UTC) | server default `now()` |

**`scoring_requests`**
| column | type | notes |
|---|---|---|
| `id` | UUID PK | `uuid4` default |
| `user_id` | UUID FK → `users.id` | Request owner |
| `input_features` | JSONB (or JSON) | 38 applicant attributes submitted |
| `predicted_probability` | float | Model output risk probability [0.0, 1.0] |
| `decision` | string | "APPROVE", "REVIEW", or "DENY" based on business thresholds |
| `model_version` | string FK → `model_versions.version` | Audit trail linking score to model version |
| `created_at` | timestamp (UTC), indexed | Submission timestamp |
| `deleted_at` | timestamp (UTC), nullable | Soft-delete support |

**`model_versions`**
| column | type | notes |
|---|---|---|
| `version` | string PK | e.g. "v1-baseline" |
| `trained_at` | timestamp (UTC) | Training timestamp |
| `reported_auc` | float | Evaluated ROC-AUC on holdout test set |
| `paper_baseline_auc` | float | FDB paper published baseline (e.g. 0.516) |
| `artifact_path` | string | Relative path to `.joblib` artifact |

---

## 4. API Endpoints

### Auth
- `POST /auth/register` — Create user account with bcrypt hashed password
- `POST /auth/login` — Verify credentials, issue signed JWT access token

### Core Scoring & History
- `POST /v1/score` — Score applicant with 38 features; non-blocking inference via `asyncio.to_thread`; persist result
- `GET /v1/scores` — Paginated and filterable list of scoring requests (owner-only, excludes soft-deleted)
- `GET /v1/scores/{id}` — Fetch single scoring record (owner-only)
- `DELETE /v1/scores/{id}` — Soft-delete scoring record (sets `deleted_at`)

### Model Transparency
- `GET /v1/model/info` — Active model metadata, version, trained timestamp, reproduced vs. baseline AUC

### Health & Readiness
- `GET /health` — Liveness probe (returns 200 OK)
- `GET /health/ready` — Readiness probe (checks DB ping + in-memory model loaded; returns 503 if unavailable)

### User
- `GET /v1/users/me` — Current authenticated user profile

---

## 5. Phased Build Plan

### Phase 0 — Environment & ML Reproduction
**Prerequisites:** Python 3.11+ / 3.12, Git, virtualenv.
**Todo:**
- [ ] Set up virtualenv and install modern ML stack: `pandas>=2.0`, `scikit-learn>=1.4`, `xgboost>=2.0`, `joblib`, `kaggle`
- [ ] Ingest *Vehicle Loan Default Prediction* dataset (233,154 rows) into `data/raw/` via Kaggle API or direct CSV download
- [ ] Verify standard 80/20 train/test split matching FDB specification: **186,523 train / 46,631 test**
- [ ] Build end-to-end `scikit-learn.pipeline.Pipeline`:
  - `ColumnTransformer` with `SimpleImputer` (median for numeric, most_frequent for categorical) + `OneHotEncoder(handle_unknown="ignore")`
  - `XGBClassifier` with `eval_metric="logloss"`
- [ ] Evaluate holdout test AUC:
  - **Tier 1 (Baseline):** Expect ~0.51–0.54 AUC (matches paper's raw LightGBM/CatBoost baselines: 0.516/0.518).
  - **Tier 2 (Feature Engineering Stretch):** Derive credit ratios, age, inquiry buckets to reach ~0.65 AUC.
- [ ] Export fitted pipeline using `joblib.dump(pipeline, "artifacts/model_pipeline.joblib")`
- [ ] Write `docs/REPRODUCTION.md` detailing methodology, split sizes, and AUC comparison against the FDB paper

**Exit criteria:** A working `artifacts/model_pipeline.joblib` file and documented `docs/REPRODUCTION.md`.

---

### Phase 1 — Project Skeleton & Configuration
**Prerequisites:** Phase 0 complete, Git initialized.
**Todo:**
- [ ] Initialize Git repo, create `.gitignore` (ignoring `.env`, `data/raw/*.csv`, `artifacts/*.joblib`, `__pycache__`)
- [ ] Set up modular directory structure:
  ```
  app/
  ├── core/          # config, security, logging
  ├── db/            # session, base
  ├── models/        # SQLAlchemy ORM models
  ├── schemas/       # Pydantic validation schemas
  ├── routers/       # API route controllers
  └── services/      # business logic & scoring
  scripts/           # training & ingestion scripts
  docs/              # plans, reproduction, analysis
  tests/             # unit & integration tests
  ```
- [ ] Create `app/core/config.py` using `pydantic-settings` with automatic `DATABASE_URL` normalization (`postgres://` → `postgresql+asyncpg://`)
- [ ] Provide `.env.example` with template values
- [ ] Implement `app/main.py` with FastAPI lifespan context manager and `/health` route

**Exit criteria:** `uvicorn app.main:app` runs cleanly, and `/health` returns `{"status": "ok"}`.

---

### Phase 2 — Database Layer & Async Migrations
**Prerequisites:** Phase 1 complete, local PostgreSQL instance (or Docker container).
**Todo:**
- [ ] Configure async SQLAlchemy 2.0 engine and session factory with `asyncpg` in `app/db/session.py`
- [ ] Define ORM models: `User`, `ScoringRequest`, and `ModelVersion` in `app/models/`
- [ ] Initialize Alembic with async template: `alembic init -t async alembic`
- [ ] Configure `alembic/env.py` to import `Base.metadata` and run migrations asynchronously
- [ ] Generate and apply initial migration (`0001_initial_schema.py`)
- [ ] Implement DB connectivity check inside `/health/ready`

**Exit criteria:** Migrations apply cleanly to Postgres; `/health/ready` reports real DB status.

---

### Phase 3 — Modern Authentication
**Prerequisites:** Phase 2 complete.
**Todo:**
- [ ] Implement secure password hashing and verification using `bcrypt` in `app/core/security.py`
- [ ] Implement JWT token generation and decoding using `pyjwt[crypto]`
- [ ] Create `POST /auth/register` (hashes password, inserts user)
- [ ] Create `POST /auth/login` (verifies credentials, returns Bearer JWT)
- [ ] Create reusable `get_current_user` FastAPI dependency
- [ ] Create protected `GET /v1/users/me` endpoint

**Exit criteria:** Can register, log in, receive a valid JWT, and authenticate against `/v1/users/me`; invalid tokens return 401 Unauthorized.

---

### Phase 4 — Core Scoring Endpoints
**Prerequisites:** Phase 0 (model pipeline) + Phase 3 (auth) complete.
**Todo:**
- [ ] Load `model_pipeline.joblib` into memory once during application startup (in `lifespan` handler)
- [ ] Implement comprehensive Pydantic schema for applicant input (38 fields with realistic examples)
- [ ] Implement `POST /v1/score`:
  - Validate applicant features via Pydantic
  - Convert payload to 1-row DataFrame
  - Execute inference via `await asyncio.to_thread(pipeline.predict_proba, input_df)` to prevent event loop blocking
  - Apply risk decision threshold (e.g. `< 0.20`: APPROVE, `0.20–0.40`: REVIEW, `> 0.40`: DENY)
  - Persist request, features, probability, decision, and model version to `scoring_requests` table
- [ ] Implement `GET /v1/scores`: paginated (`limit`, `offset`), filterable by `decision`, date range, and threshold
- [ ] Implement `GET /v1/scores/{id}` and `DELETE /v1/scores/{id}` (with owner-only access check and soft-delete)
- [ ] Implement `GET /v1/model/info`: returns current active model metadata from `model_versions`

**Exit criteria:** Can send applicant JSON payload, receive prediction in <10ms, and query paginated history.

---

### Phase 5 — Error Handling & Resilience
**Prerequisites:** Phase 4 complete.
**Todo:**
- [ ] Implement global exception handlers returning consistent JSON error envelopes (`detail`, `error_code`, `request_id`)
- [ ] Implement graceful handling for DB disconnections, missing model artifacts, invalid payloads, 404s, and 403s
- [ ] Ensure `/health/ready` returns HTTP 503 if the database is unreachable or the model is not loaded
- [ ] Validate resilience: shut down Postgres mid-flight and ensure API fails gracefully without stack traces

**Exit criteria:** Live demo showing clean JSON error responses under dependency failure.

---

### Phase 6 — Structured Logging & Correlation IDs
**Prerequisites:** Phase 5 complete.
**Todo:**
- [ ] Add `asgi-correlation-id` middleware to capture or assign `X-Request-ID`
- [ ] Configure `structlog` to output machine-readable JSON logs including timestamp, log level, event, and correlation ID
- [ ] Log auth events, scoring requests (excluding PII), model inference latency, and errors

**Exit criteria:** Every log entry is valid JSON containing the request's unique correlation ID.

---

### Phase 7 — Testing Strategy
**Prerequisites:** Phases 1–6 complete.
**Todo:**
- [ ] Configure `pytest.ini` with `asyncio_mode = auto`
- [ ] **Unit Tests (`tests/unit/`):**
  - Password hashing and verification
  - JWT creation, expiration, and invalid signature rejection
  - Pydantic schema validation boundary and type edge cases
  - Scoring decision threshold logic with a mocked pipeline
- [ ] **Integration Tests (`tests/integration/`):**
  - Test real HTTP calls against endpoints using `httpx.AsyncClient`
  - Spin up test database container via Docker Compose
  - Verify transaction rollback on error (no orphan records)
  - Verify `/health/ready` returns 503 when DB is offline

**Exit criteria:** `pytest tests/unit` runs in <2 seconds locally; `pytest tests/integration` passes against real Postgres.

---

### Phase 8 — Containerization
**Prerequisites:** Phase 7 complete.
**Todo:**
- [ ] Write multi-stage `Dockerfile` (`python:3.12-slim` builder + slim runtime)
- [ ] Write `docker-compose.yml` defining `api` and `postgres` services with healthchecks and volume persistence
- [ ] Write `docker-compose.test.yml` for isolated integration test runs
- [ ] Test clean boot: `docker compose up --build` and verify Swagger docs at `http://localhost:8000/docs`

**Exit criteria:** A single `docker compose up` spins up a fully functional, seeded API and database.

---

### Phase 9 — Cloud Deployment
**Prerequisites:** Phase 8 complete.
**Todo:**
- [ ] Deploy API and managed PostgreSQL on Render, Railway, or Fly.io
- [ ] Configure environment variables in cloud dashboard (`DATABASE_URL`, `JWT_SECRET`, `MODEL_PATH`)
- [ ] Run Alembic migrations automatically on deployment
- [ ] Validate live `/health`, `/health/ready`, and `/docs` endpoints over public HTTPS

**Exit criteria:** Publicly accessible API URL that recruiters and interviewers can test directly.

---

### Phase 10 — Documentation & Polish
**Prerequisites:** Phases 1–9 complete.
**Todo:**
- [ ] Write root `README.md` with architecture diagram, feature overview, setup instructions, and live URL
- [ ] Finalize `docs/REPRODUCTION.md` detailing the FDB paper baseline comparison
- [ ] Polish OpenAPI schema docstrings so Swagger `/docs` is an intuitive demo interface

**Exit criteria:** Anyone landing on the repo can understand, run, and test the project in under 5 minutes.
