import joblib
import pytest
from pydantic import ValidationError

from app.schemas.scoring import LoanApplicantInput, _parse_duration_to_months, _parse_date_to_year_month


def test_parse_duration_to_months():
    assert _parse_duration_to_months("2yrs 3mon") == 27
    assert _parse_duration_to_months("0yrs 6mon") == 6
    assert _parse_duration_to_months("1yr 0mon") == 12
    assert _parse_duration_to_months("15") == 15
    assert _parse_duration_to_months(24) == 24
    assert _parse_duration_to_months(None) == 0


def test_parse_date_to_year_month():
    year, month = _parse_date_to_year_month("1984-05-12")
    assert year == 1984
    assert month == 5

    # 2-digit century test (84 should map to 1984)
    year, month = _parse_date_to_year_month("12-05-84")
    assert year == 1984
    assert month == 5


def test_loan_applicant_input_defaults_and_validation():
    # Valid minimal input
    applicant = LoanApplicantInput(
        disbursed_amount=50000.0,
        asset_cost=65000.0,
        ltv=76.9,
    )
    assert applicant.disbursed_amount == 50000.0
    assert applicant.aadhar_flag == 1
    assert applicant.employment_type == "Salaried"


def test_loan_applicant_validation_errors():
    # Disbursed amount <= 0 rejected
    with pytest.raises(ValidationError):
        LoanApplicantInput(disbursed_amount=-100, asset_cost=50000, ltv=80.0)

    # Missing asset_cost rejected
    with pytest.raises(ValidationError):
        LoanApplicantInput(disbursed_amount=50000, ltv=80.0)


def test_dataframe_conversion_and_pipeline_inference():
    applicant = LoanApplicantInput(
        disbursed_amount=50000.0,
        asset_cost=65000.0,
        ltv=76.9,
        branch_id=67,
        supplier_id=22807,
        manufacturer_id=45,
        current_pincode_id=1441,
        state_id=6,
        employee_code_id=1998,
        date_of_birth="1987-01-01",
        disbursal_date="2018-08-01",
        average_acct_age="1yr 2mon",
        credit_history_length="2yrs 6mon",
    )

    df = applicant.to_model_dataframe()
    assert df.shape == (1, 40)
    assert df["AVERAGE.ACCT.AGE"].iloc[0] == 14
    assert df["CREDIT.HISTORY.LENGTH"].iloc[0] == 30
    assert df["Date.of.Birth_year"].iloc[0] == 1987

    # Load model and verify end-to-end inference works cleanly
    pipeline = joblib.load("artifacts/model_pipeline.joblib")
    probs = pipeline.predict_proba(df)
    assert probs.shape == (1, 2)
    fraud_prob = float(probs[0, 1])
    assert 0.0 <= fraud_prob <= 1.0
