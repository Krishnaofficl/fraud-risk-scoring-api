"""
Download or ingest the Vehicle Loan Default Prediction dataset.
Sourced from the LTFS Vehicle Loan Default Prediction dataset on Kaggle:
https://www.kaggle.com/c/vehicle-loan-default-prediction/data
"""

import os
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
TARGET_FILE = DATA_DIR / "train.csv"


def check_or_download():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if TARGET_FILE.exists():
        print(f" Dataset already present at: {TARGET_FILE}")
        print(f"File size: {TARGET_FILE.stat().st_size / (1024 * 1024):.2f} MB")
        return

    print("Checking for Kaggle CLI credentials...")
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"

    if kaggle_json.exists() or "KAGGLE_USERNAME" in os.environ:
        print("Kaggle credentials found. Attempting download via Kaggle API...")
        try:
            import kaggle
            kaggle.api.authenticate()
            # The Kaggle competition slug
            kaggle.api.competition_download_file(
                competition="vehicle-loan-default-prediction",
                file_name="train.csv",
                path=str(DATA_DIR)
            )
            print(f" Successfully downloaded train.csv to {DATA_DIR}")
            return
        except Exception as e:
            print(f"Automatic Kaggle download failed: {e}")

    print("\n" + "=" * 60)
    print("MANUAL DOWNLOAD INSTRUCTIONS:")
    print("1. Visit: https://www.kaggle.com/c/vehicle-loan-default-prediction/data")
    print("2. Download 'train.csv'")
    print(f"3. Place 'train.csv' in: {DATA_DIR.resolve()}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    check_or_download()
