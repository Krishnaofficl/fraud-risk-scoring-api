# Fraud & Risk Scoring API

A production-shaped FastAPI service reproducing Amazon's **Fraud Dataset Benchmark (FDB)** `vehicleloan` sub-task ([arXiv:2208.14417](https://arxiv.org/abs/2208.14417)).

Demonstrates resilient, cloud-native backend engineering: asynchronous persistence, versioned migrations, JWT authentication, end-to-end ML pipeline serialization, structured correlation logging, and comprehensive automated testing.

---

## Architecture Overview

```
                          ┌─────────────────────┐
                          │   Client / Swagger   │
                          │   (docs, curl, UI)   │
                          └──────────┬───────────┘
                                     │ HTTPS
                                     ▼
                          ┌─────────────────────┐
                          │   FastAPI Service   │
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
                          │  └────────────────┘ │
                          └──────────┬───────────┘
                                     │
                 ┌───────────────────┼───────────────────┐
                 ▼                                       ▼
      ┌─────────────────────┐                 ┌─────────────────────┐
      │  Model Pipeline     │                 │  PostgreSQL         │
      │  (joblib artifact)  │                 │  - users            │
      │  - ColumnTransformer│                 │  - scoring_requests │
      │  - XGBClassifier    │                 │  - model_versions   │
      └─────────────────────┘                 └─────────────────────┘
```

---

## Directory Structure

```
fraud-risk-scoring-api/
├── app/                        # FastAPI Application
│   ├── core/                   # Config, security (bcrypt, JWT), structured logging
│   ├── db/                     # Async SQLAlchemy session & declarative base
│   ├── models/                 # ORM models (User, ScoringRequest, ModelVersion)
│   ├── schemas/                # Pydantic v2 validation models & examples
│   ├── routers/                # Endpoint controllers (auth, score, health, model, user)
│   ├── services/               # Inference wrapper & business logic
│   └── main.py                 # Application factory & lifespan handler
├── scripts/                    # Offline Ingestion & Training (Phase 0)
│   ├── download_data.py        # Dataset fetch & verification helper
│   └── train.py                # End-to-end ColumnTransformer + XGBoost pipeline
├── data/                       # Dataset Storage (Git ignored)
│   ├── raw/                    # Raw train.csv
│   └── processed/              # Preprocessed splits
├── artifacts/                  # Serialized Model Artifacts
│   └── model_pipeline.joblib   # Preprocessor + XGBoost pipeline
├── docs/                       # Project Documentation & Analysis
│   ├── implementation-plan.md  # Detailed 10-phase engineering plan
│   ├── feasibility-analysis.md # Comprehensive feasibility study
│   ├── phase0-and-stack-fixes.md # Technical rationale & blocker solutions
│   └── REPRODUCTION.md         # FDB paper baseline reproduction report
├── resources/                  # Academic papers & benchmarks
│   └── 2208.14417v3.pdf        # FDB research paper
├── tests/                      # Automated Testing Suite
│   ├── unit/                   # Fast, isolated unit tests (mocked DB/model)
│   ├── integration/            # Full HTTP integration tests (PostgreSQL)
│   └── conftest.py             # Pytest fixtures & async client
├── .env.example                # Template environment variables
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies (Python 3.11/3.12 compatible)
├── pyproject.toml              # Build & test configuration
├── TODO.md                     # Master project checklist & task tracker
└── README.md                   # Project overview & documentation
```

---

## Quickstart

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Phase 0: Reproduce Benchmark & Train Model Pipeline
```bash
# 1. Download or place train.csv in data/raw/
python scripts/download_data.py

# 2. Train and serialize the ColumnTransformer + XGBoost pipeline
python scripts/train.py
```
This evaluates test ROC-AUC against the published Amazon FDB paper baselines and saves `artifacts/model_pipeline.joblib`.

### 3. Run FastAPI Application Locally
```bash
# Copy environment configuration
cp .env.example .env

# Run Uvicorn dev server
uvicorn app.main:app --reload --port 8000
```
Visit **`http://localhost:8000/docs`** for interactive Swagger documentation.

---

## Documentation Links

* [Master TODO Checklist](TODO.md)
* [Implementation Plan](docs/implementation-plan.md)
* [Feasibility Analysis](docs/feasibility-analysis.md)
* [Phase 0 & Tech Stack Fixes](docs/phase0-and-stack-fixes.md)
* [Reproduction Report](docs/REPRODUCTION.md)

