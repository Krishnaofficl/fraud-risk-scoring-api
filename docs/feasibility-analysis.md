# Feasibility Analysis: Fraud/Risk Scoring API

**Evaluated Plan:** [fraud-risk-api-implementation-plan.md](file:///e:/Projects/fraud-risk-scoring-api/fraud-risk-api-implementation-plan.md)  
**Evaluation Date:** 2026-09-19  
**System Environment:** Windows 10/11, Python 3.12.10, Docker 29.6.2  
**Overall Feasibility Score:** **8.5 / 10** (Strong, well-scoped architecture; requires critical fixes in Phase 0 & auth dependencies)

---

## Executive Summary

The implementation plan is **conceptually sound, pragmatic, and well-tailored** for demonstrating production-grade backend engineering anchored around a real-world ML benchmark. The progression from offline modeling (Phase 0) to a fully containerized, authenticated, tested FastAPI service (Phases 1–10) follows best practices.

However, **there are 3 critical blockers and several technical discrepancies** that will cause immediate failure if executed strictly as written:
1. **Phase 0 Dependency Blocker:** `pip install fraud-dataset-benchmark` fails (the package is not on PyPI). The source repository relies on legacy pinned packages (`numpy 1.19.5`, `pandas 1.1.2`, `auto-sklearn 0.14.7`) that **cannot** be installed on Python 3.11/3.12 or Windows.
2. **Model Serialization Gap:** Saving only the raw classifier (`xgb.pkl`) is insufficient for the `vehicleloan` dataset (38 features with 13 categoricals and missing values). A unified scikit-learn `Pipeline` (preprocessing + estimator) must be serialized.
3. **Outdated Auth Stack:** `passlib[bcrypt]` and `python-jose` are deprecated/unmaintained, failing on `bcrypt >= 4.0.0` and Python 3.12.

---

## Phase-by-Phase Feasibility Breakdown

### Phase 0: Environment & ML Reproduction
> **Feasibility Rating:** ⚠️ **Moderate (Requires Immediate Revision)**

| Item in Plan | Reality / Analysis | Risk Level | Recommended Adjustment |
|---|---|---|---|
| `pip install fraud-dataset-benchmark` | Does not exist on PyPI (`404 Not Found`). FDB GitHub repo pins ancient packages (`numpy 1.19`, `auto-sklearn` which is Linux-only). | **HIGH** (Hard Blocker) | Download the underlying Kaggle dataset (*Vehicle Loan Default Prediction*) directly or copy only FDB's clean loader script logic. Train with modern `pandas 2.x`, `scikit-learn 1.4+`, and `xgboost 2.x`. |
| Kaggle API access | The dataset origin is Kaggle; requires a Kaggle account & `kaggle.json` token. | **MEDIUM** | Add Kaggle API credentials / manual CSV download instructions to prerequisites. |
| Split sizes: `186,523 train / 11,658 test` | FDB repo records `186,523 train / 46,631 test` (total 233,154, an exact 80/20 split). `11,658` is 25% of the test set (or 5% of total). | **LOW** (Discrepancy) | Use the standard 80/20 split (`186,523` / `46,631`) or clarify if `11,658` was a specific paper validation split. |
| Target AUC: `~0.65–0.67` | In the published FDB paper (arXiv:2208.14417, Table on vehicleloan), raw baselines without feature engineering are: Random Forest: `0.491`, LightGBM: `0.516`, CatBoost: `0.518`. The `~0.65–0.67` range comes from Kaggle competition feature-engineered models or AutoGluon/Amazon Fraud Detector. | **MEDIUM** (Expectation Mismatch) | Explicitly document that a raw tabular baseline will yield ~0.52–0.55 AUC unless temporal/credit feature engineering is applied, which aligns with the paper's findings. |
| Model Serialization | Saving only `joblib.dump(model)` will fail at runtime because the API cannot parse raw categorical strings and nulls without the transformer. | **HIGH** | Build a `scikit-learn.pipeline.Pipeline(steps=[('preprocessor', preprocessor), ('classifier', xgb_model)])` and serialize the pipeline. |

---

### Phases 1 & 2: Project Skeleton & Database Layer
> **Feasibility Rating:**  **High (Ready with minor config tweaks)**

- **Framework:** FastAPI + Uvicorn is the gold standard for asynchronous Python microservices.
- **SQLAlchemy 2.0 (Async) + Alembic:**
  - Standard Alembic migration templates default to synchronous drivers. Ensure `alembic init -t async alembic` is executed so `env.py` contains `run_sync` and handles async engines.
  - Driver must be `asyncpg` (`postgresql+asyncpg://...`), while Alembic migrations or psycopg2 may be used for sync fallback.
- **Data Types (`JSONB` in `scoring_requests`):**
  - Using PostgreSQL `JSONB` for `input_features` is optimal for query performance and flexible schema storage.
  - *Tip for testing:* Use `sqlalchemy.types.JSON` in ORM definitions to ensure test compatibility if SQLite in-memory is ever used alongside Postgres.

---

### Phase 3: Authentication & Security
> **Feasibility Rating:** ⚠️ **Moderate (Outdated libraries need swap)**

| Plan Recommendation | Issue | Modern Alternative |
|---|---|---|
| `passlib[bcrypt]` | Unmaintained since 2020. Breaks with `bcrypt >= 4.0.0`, throws deprecation warnings on Python 3.12 (`crypt` module removal). | Use `pwdlib[argon2]` or direct `bcrypt` / `argon2-cffi`. |
| `python-jose` | Stale maintenance and outdated cryptographic primitives. | Use `PyJWT` with `cryptography`. |

- **Design:** Using FastAPI's `OAuth2PasswordBearer` and a `get_current_user` dependency is battle-tested, clean, and straightforward.

---

### Phase 4: Core Scoring Endpoints
> **Feasibility Rating:**  **High**

- **Input Schema:** The `vehicleloan` dataset contains 38 attributes:
  - 13 categorical (e.g., employment type, disbursed amount tier, credit bureau score description)
  - 22 numeric (e.g., loan amount, asset cost, LTV, delinquency counts, active accounts)
  - 3 date/text (e.g., date of birth, disbursal date)
- **Pydantic Validation:** Writing a clean 38-field Pydantic schema with `Field(..., examples=[...])` makes the Swagger UI instantly usable for interviewers.
- **Concurrency & CPU-bound Inference:**
  - Running `pipeline.predict_proba(df)` is CPU-bound.
  - Although tabular prediction takes only 1–3 ms, running it inside an async route under load can block the event loop.
  - *Best Practice:* Execute inference via `await asyncio.to_thread(pipeline.predict_proba, input_df)`.

---

### Phases 5 & 6: Reliability & Structured Logging
> **Feasibility Rating:**  **High**

- **Readiness Probe (`/health/ready`):**
  - Checking DB ping (`await db.execute(text("SELECT 1"))`) and verifying model loaded (`app.state.model is not None`).
  - Returning `HTTP 503 Service Unavailable` on failure is strictly compliant with Kubernetes and load balancer health check standards.
- **Logging & Tracing:**
  - `structlog` or `asgi-correlation-id` + stdlib JSON formatting enables end-to-end request tracing (`X-Request-ID`), fulfilling standard production observability requirements.

---

### Phase 7: Testing Strategy
> **Feasibility Rating:**  **High**

- **Async Fixtures:** Requires `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Database Isolation:**
  - Plan suggests Docker Compose Postgres for integration tests.
  - *Recommendation:* Keep fast unit tests completely isolated with mocks or SQLite for sub-second developer feedback loops. Reserve the real Postgres container for end-to-end API integration tests and rollback validation.

---

### Phases 8 & 9: Containerization & Cloud Deployment
> **Feasibility Rating:**  **High**

- **Docker Image Size:**
  - Base image: `python:3.12-slim`.
  - With `fastapi`, `uvicorn`, `asyncpg`, `pydantic`, `scikit-learn`, `xgboost`, and `numpy`, the final image size will be ~450–600 MB.
- **Hosting Resource Limits:**
  - Free/entry tiers on Render, Railway, or Fly.io typically offer 512 MB RAM.
  - A single-worker Uvicorn process with the serialized XGBoost tabular pipeline loaded in memory consumes ~140–200 MB RAM, fitting comfortably within the 512 MB threshold.
- **Database URL Handling:**
  - Cloud providers often supply `DATABASE_URL` starting with `postgres://`. SQLAlchemy 2.0 requires `postgresql+asyncpg://`. A simple validator in `BaseSettings` should replace `postgres://` or `postgresql://` with `postgresql+asyncpg://`.

---

## Architecture & Feasibility Matrix

```
┌─────────────────────────┬─────────────┬────────────────────────────────────────────────────────┐
│ Component               │ Feasibility │ Key Watchouts / Recommendations                       │
├─────────────────────────┼─────────────┼────────────────────────────────────────────────────────┤
│ ML Pipeline & Splits    │ ⚠️ 6.5/10   │ Bypass PyPI FDB; use modern scikit-learn + XGBoost.    │
│ Preprocessing Pipeline  │ ⚠️ 7.0/10   │ Must serialize ColumnTransformer + Model together.     │
│ FastAPI Web Layer       │  10/10    │ Idiomatic, high-performance, excellent docs.         │
│ Database & Migrations   │  9.5/10   │ Use Alembic async template; handle asyncpg URLs.       │
│ Authentication          │ ⚠️ 7.5/10   │ Replace passlib/python-jose with pwdlib/bcrypt + PyJWT.│
│ Endpoints & Validation  │  9.5/10   │ 38-field Pydantic schema with complete OpenAPI examples│
│ Reliability & Logging   │  10/10    │ /health/ready (503) + structlog + correlation IDs.     │
│ Testing Suite           │  9.0/10   │ Separate mocked fast tests from Docker DB tests.       │
│ Docker & Cloud Deploy   │  9.5/10   │ Fits within 512MB RAM on free/hobby hosting tiers.     │
└─────────────────────────┴─────────────┴────────────────────────────────────────────────────────┘
```

---

## Actionable Recommendations for Implementation

1. **Fix Phase 0 First:**
   - Create a dedicated script (`scripts/train.py`) that loads the raw dataset, builds a `ColumnTransformer` (handling categorical encoding and imputations), trains `XGBClassifier`, evaluates ROC-AUC, and exports `artifacts/model_pipeline.joblib`.
2. **Update Dependency Specs:**
   - Replace:
     ```text
     passlib[bcrypt]
     python-jose
     fraud-dataset-benchmark
     ```
   - With:
     ```text
     pwdlib[argon2] (or bcrypt >= 4.0.0)
     pyjwt[crypto]
     scikit-learn >= 1.4.0
     xgboost >= 2.0.0
     asyncpg >= 0.29.0
     asgi-correlation-id >= 4.3.0
     ```
3. **Handle Dataset Metric Context in Documentation:**
   - In `REPRODUCTION.md`, clearly distinguish between:
     - The FDB paper's default baseline without feature engineering (~0.52 AUC).
     - The Kaggle competition feature-engineered models (~0.65–0.67 AUC).
     - Your reproduced score.
   - This prevents interviewers from questioning metric discrepancies.
