# Fixes for Feasibility Analysis Findings

Addresses each blocker/discrepancy raised in `feasibility_analysis.md`. Apply these as corrections to `fraud-risk-api-implementation-plan.md`, primarily affecting Phase 0 and Phase 3.

---

## Fix 1 — FDB package doesn't exist on PyPI / legacy deps unusable

**Problem:** `pip install fraud-dataset-benchmark` fails; the GitHub repo pins ancient, Linux-only, Python 3.11/3.12-incompatible dependencies.

**Solution:** Don't install the FDB package at all. Use it only as a **methodology reference** (its README documents exactly which Kaggle dataset, which columns, and which train/test split logic it uses for `vehicleloan`) and reproduce the data loading yourself with modern libraries.

**Steps:**
1. Get the raw dataset directly from Kaggle: *"Vehicle Loan Default Prediction"* (search Kaggle for this exact title — it's the L&T Financial Services dataset FDB wraps).
2. Set up Kaggle API access:
   ```bash
   pip install kaggle
   # Get kaggle.json from kaggle.com/settings/account → API → Create New Token
   # Place at ~/.kaggle/kaggle.json (chmod 600 on Linux/Mac)
   kaggle datasets download -d <dataset-slug> -p data/raw --unzip
   ```
   (If the exact slug is unclear, download manually from the Kaggle competition/dataset page instead — same result, no API needed.)
3. Replicate FDB's split logic yourself, referencing their GitHub loader script for the exact column selection and split ratio (see Fix 3 below for the correct ratio) — you're reproducing their *methodology*, not their *code*, which is a perfectly legitimate and often clearer story to tell in an interview.
4. Use current library versions throughout: `pandas>=2.0`, `scikit-learn>=1.4`, `xgboost>=2.0`.

---

## Fix 2 — Model serialization must include preprocessing, not just the classifier

**Problem:** The `vehicleloan` dataset has 13 categorical + 22 numeric + date fields. Saving only `xgb.pkl` means the API has no way to encode categorical strings or handle missing values at inference time.

**Solution:** Build and serialize a single `sklearn.Pipeline` covering preprocessing + model.

```python
# scripts/train.py
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

df = pd.read_csv("data/raw/train.csv")

numeric_features = [...]      # your 22 numeric columns
categorical_features = [...]  # your 13 categorical columns

preprocessor = ColumnTransformer(transformers=[
    ("num", SimpleImputer(strategy="median"), numeric_features),
    ("cat", Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore")),
    ]), categorical_features),
])

pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", XGBClassifier(eval_metric="auc", n_estimators=300)),
])

X = df[numeric_features + categorical_features]
y = df["loan_default"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

pipeline.fit(X_train, y_train)
auc = roc_auc_score(y_test, pipeline.predict_proba(X_test)[:, 1])
print(f"Test AUC: {auc:.4f}")

joblib.dump(pipeline, "artifacts/model_pipeline.joblib")
```

At inference time in the API, load `model_pipeline.joblib` and call `.predict_proba(raw_input_df)` directly — no manual encoding needed, since the pipeline handles it.

---

## Fix 3 — Correct train/test split numbers

**Problem:** Plan stated `186,523 train / 11,658 test`; FDB's actual recorded split is `186,523 train / 46,631 test` (a clean 80/20 of 233,154 total rows).

**Solution:** Use the standard 80/20 split going forward:
```python
train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
```
Update the implementation plan's Phase 0 exit criteria to reference `186,523 / 46,631`, and drop the `11,658` figure entirely (it doesn't correspond to a standard split for this dataset).

---

## Fix 4 — Realistic AUC target (this is the most important fix)

**Problem:** The `~0.65–0.67` figure in the plan actually corresponds to **feature-engineered** Kaggle-competition solutions or AutoGluon/Amazon Fraud Detector runs — not a raw baseline. A plain XGBoost model on raw features (matching the FDB paper's own baselines) realistically lands around **0.50–0.55 AUC**.

**Solution:** Set two honest, tiered targets instead of one number:

| Tier | Target AUC | What it requires |
|---|---|---|
| **Tier 1 — Baseline reproduction** | ~0.50–0.55 | Raw features, minimal preprocessing (matches FDB paper's own Random Forest/LightGBM/CatBoost baselines: 0.491–0.518) |
| **Tier 2 — Feature-engineered (stretch goal)** | ~0.65–0.67 | Add engineered features: loan-to-value ratio buckets, credit bureau score bands, disbursal-to-first-installment time gaps, account age at disbursal — the kind of feature engineering top Kaggle solutions used |

**In `REPRODUCTION.md`, state explicitly:**
- "Tier 1 reproduces the FDB paper's raw baseline (~0.52 AUC) — confirms methodology parity."
- "Tier 2 (optional stretch) approaches Kaggle-competition-level performance (~0.65+) through feature engineering, going beyond the paper's own scope."

This framing turns what looked like an error into a deliberate, well-explained two-stage result — which is a *stronger* interview story than a single unexplained number.

---

## Fix 5 — Replace deprecated auth libraries

**Problem:** `passlib[bcrypt]` is unmaintained and breaks on `bcrypt>=4.0`/Python 3.12; `python-jose` is stale.

**Solution — password hashing with `bcrypt` directly (no passlib needed):**
```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

**Solution — JWT with `pyjwt` instead of `python-jose`:**
```python
import jwt
from datetime import datetime, timedelta, timezone

def create_access_token(subject: str, secret: str, expires_minutes: int = 30) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_access_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])
```

**Updated `requirements.txt` entries:**
```
bcrypt>=4.0.0
pyjwt[crypto]>=2.8.0
```
(Remove `passlib` and `python-jose` entirely.)

---

## Fix 6 — Async event loop blocking on CPU-bound inference

**Problem:** `pipeline.predict_proba(df)` is synchronous and CPU-bound; calling it directly inside an `async def` route can block the event loop under load.

**Solution:**
```python
import asyncio

@router.post("/v1/score")
async def score(payload: ScoreRequest, ...):
    input_df = pd.DataFrame([payload.model_dump()])
    proba = await asyncio.to_thread(pipeline.predict_proba, input_df)
    ...
```

---

## Fix 7 — Alembic async setup

**Problem:** Default Alembic templates are synchronous; SQLAlchemy 2.0 async engines need the async template.

**Solution:**
```bash
alembic init -t async alembic
```
This generates an `env.py` that already handles `run_sync` and async engine connections correctly — don't hand-write this part.

---

## Fix 8 — Test isolation strategy

**Problem:** Using the same Postgres container for both fast unit tests and integration tests slows down the dev feedback loop.

**Solution:**
- **Unit tests:** mock the model and DB session entirely (or use SQLite in-memory for anything that touches the ORM but doesn't need Postgres-specific features like `JSONB`)
- **Integration tests:** real Postgres via Docker Compose, `pytest-asyncio` with `asyncio_mode = "auto"` in `pytest.ini`/`pyproject.toml`
- Keep them in separate directories: `tests/unit/` and `tests/integration/`, runnable independently (`pytest tests/unit` for fast iteration, full suite before pushing)

---

## Fix 9 — `DATABASE_URL` scheme mismatch on cloud hosts

**Problem:** Render/Railway/Fly often provide `postgres://...` or `postgresql://...`; SQLAlchemy 2.0 async needs `postgresql+asyncpg://...`.

**Solution — normalize in your Pydantic settings:**
```python
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str

    @field_validator("database_url")
    @classmethod
    def fix_scheme(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
```

---

## Updated `requirements.txt` (delta from original plan)

```diff
- passlib[bcrypt]
- python-jose
- fraud-dataset-benchmark
+ bcrypt>=4.0.0
+ pyjwt[crypto]>=2.8.0
+ scikit-learn>=1.4.0
+ xgboost>=2.0.0
+ asyncpg>=0.29.0
+ pandas>=2.0.0
```

---

## Summary of Plan Edits

| Section of original plan | Change |
|---|---|
| Phase 0 todo | Drop `pip install fraud-dataset-benchmark`; add Kaggle download steps; reference FDB GitHub as methodology only |
| Phase 0 exit criteria | Split numbers corrected to 186,523 / 46,631; AUC target split into Tier 1 (~0.52) / Tier 2 stretch (~0.65+) |
| Phase 0 todo | Add: build `ColumnTransformer` + `Pipeline`, not a bare classifier |
| Phase 3 stack | Swap `passlib`/`python-jose` → `bcrypt`/`pyjwt` |
| Phase 4 todo | Add: wrap inference call in `asyncio.to_thread` |
| Phase 2 todo | Add: `alembic init -t async alembic` |
| Phase 7 todo | Add: separate unit (mocked/SQLite) vs. integration (real Postgres) test directories |
| Phase 9 todo | Add: `DATABASE_URL` scheme normalization in settings validator |
