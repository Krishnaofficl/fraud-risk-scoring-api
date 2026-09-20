"""
Phase 0 Training Script: Reproduce Amazon FDB Vehicle Loan Risk Benchmark.
Builds an end-to-end ColumnTransformer + XGBClassifier Pipeline and serializes to artifacts/model_pipeline.joblib.
"""

import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "raw" / "train.csv"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
MODEL_OUTPUT_PATH = ARTIFACTS_DIR / "model_pipeline.joblib"


def parse_duration_to_months(series: pd.Series) -> pd.Series:
    """Parses duration strings like '2yrs 3mon' or '0yrs 0mon' into total integer months."""
    def parse_str(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip().lower()
        years = 0
        months = 0
        if "yr" in s:
            parts = s.split("yr")
            years = int(parts[0].strip() or 0)
            s = parts[1]
        if "mon" in s:
            parts = s.split("mon")
            cleaned = parts[0].replace("s", "").strip()
            months = int(cleaned or 0)
        return (years * 12) + months

    return series.apply(parse_str)


def load_and_preprocess(data_path: Path):
    print(f"Loading raw dataset from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"Raw dataset shape: {df.shape}")

    target_col = "loan_default"
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset columns.")

    # Drop pure identifiers
    drop_cols = [c for c in ["UniqueID", "MobileNo_Avl_Flag"] if c in df.columns]
    df = df.drop(columns=drop_cols)

    # Standardize tenure string fields to numerical months if present
    for tenure_col in ["AVERAGE.ACCT.AGE", "CREDIT.HISTORY.LENGTH"]:
        if tenure_col in df.columns:
            df[tenure_col] = parse_duration_to_months(df[tenure_col])

    # Convert date strings into simple year/month features if present
    for date_col in ["Date.of.Birth", "DisbursalDate"]:
        if date_col in df.columns:
            dt = pd.to_datetime(df[date_col], format="%d-%m-%y", errors="coerce")
            # Correct century for 2-digit years (e.g. 84 -> 1984 rather than 2084)
            dt = dt.map(lambda d: d.replace(year=d.year - 100) if pd.notna(d) and d.year > 2026 else d)
            df[f"{date_col}_year"] = dt.dt.year
            df[f"{date_col}_month"] = dt.dt.month
            df = df.drop(columns=[date_col])

    y = df[target_col]
    X = df.drop(columns=[target_col])

    # Categorize column types (compatible with pandas 2.x and 3.x)
    categorical_cols = list(X.select_dtypes(exclude=["number"]).columns)
    numeric_cols = list(X.select_dtypes(include=["number"]).columns)

    print(f"Features: {len(numeric_cols)} numerical, {len(categorical_cols)} categorical.")
    return X, y, numeric_cols, categorical_cols


def build_pipeline(numeric_cols, categorical_cols):
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_cols),
            ("cat", categorical_transformer, categorical_cols),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=150,
                    max_depth=6,
                    learning_rate=0.08,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    eval_metric="logloss",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    return pipeline


def run_training():
    if not DATA_PATH.exists():
        print(f"Data file not found at {DATA_PATH}.")
        print("Please run `python scripts/download_data.py` first.")
        sys.exit(1)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    X, y, numeric_cols, categorical_cols = load_and_preprocess(DATA_PATH)

    # 80/20 train/test split matching FDB's benchmark specification
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Train samples: {len(X_train)} (Expected ~186,523)")
    print(f"Test samples:  {len(X_test)} (Expected ~46,631)")

    pipeline = build_pipeline(numeric_cols, categorical_cols)

    print("Fitting ColumnTransformer + XGBoost pipeline...")
    pipeline.fit(X_train, y_train)

    print("Evaluating holdout test set...")
    y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
    auc_score = roc_auc_score(y_test, y_pred_proba)

    print(f"\n==========================================")
    print(f" EVALUATION RESULT (ROC-AUC): {auc_score:.4f}")
    print(f"==========================================")
    print(f"Paper Baseline (Raw LightGBM): 0.516")
    print(f"Paper Baseline (Raw CatBoost): 0.518")
    print(f"Kaggle Feature-Engineered Target: ~0.65")
    print(f"==========================================\n")

    print(f"Exporting fitted pipeline to: {MODEL_OUTPUT_PATH}")
    joblib.dump(pipeline, MODEL_OUTPUT_PATH)
    print("Export complete. Pipeline is ready for API serving.")


if __name__ == "__main__":
    run_training()
