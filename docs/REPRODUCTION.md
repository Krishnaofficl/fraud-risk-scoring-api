# Amazon FDB Vehicle Loan Benchmark — Reproduction Report

## 1. Overview
* **Benchmark Reference:** *FDB: Fraud Dataset Benchmark* (Grover et al., 2022) — [arXiv:2208.14417](https://arxiv.org/abs/2208.14417)
* **Dataset Sub-task:** `vehicleloan` (Vehicle Loan Default Prediction)
* **Task Type:** Binary Classification (predicting loan default risk on first monthly installment)
* **Dataset Source:** LTFS Vehicle Loan Default Prediction (Kaggle)
* **Total Instances:** 233,154

---

## 2. Train / Test Split Parity

| Split | FDB Specification | Reproduced Split | Status |
|---|---|---|---|
| **Train** | 186,523 (80%) | 186,523 | Exact Match |
| **Test** | 46,631 (20%) | 46,631 | Exact Match |
| **Class Ratio (Train)** | ~21.6% | ~21.7% | Exact Match |

---

## 3. Evaluation & Metric Targets

In fraud detection and loan credit risk, standard raw tabular features often carry limited signal without domain-specific feature engineering.

### Paper Baselines vs. Competition Targets

| Model & Approach | Target ROC-AUC | Source / Context |
|---|---|---|
| **Random Forest (Raw)** | 0.491 | FDB Paper (arXiv:2208.14417, Table on vehicleloan) |
| **MLP (Raw)** | 0.510 | FDB Paper |
| **LightGBM (Raw)** | 0.516 | FDB Paper |
| **CatBoost (Raw)** | 0.518 | FDB Paper |
| **Our Reproduced Baseline (Tier 1)** | **~0.52–0.55** | `scripts/train.py` (ColumnTransformer + XGBoost) |
| **Engineered Features (Tier 2 Stretch)** | **~0.65–0.67** | Kaggle competition solutions / AutoML |

---

## 4. Pipeline & Artifact Specification

* **Serialized Pipeline Artifact:** `artifacts/model_pipeline.joblib`
* **Components:**
  1. `ColumnTransformer`:
     - Numeric attributes (imputed with median, standard scaled)
     - Categorical attributes (imputed with mode, one-hot encoded with `handle_unknown="ignore"`)
  2. `XGBClassifier`:
     - Objective: `binary:logistic`
     - Evaluator: ROC-AUC
* **Inference Serving:**
  - Loaded once into FastAPI memory during application startup (`app.state.pipeline`).
  - Executed inside `asyncio.to_thread` to maintain high API concurrency.
