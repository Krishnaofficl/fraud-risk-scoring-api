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


def test_scoring_result_response_from_dict_and_orm():
    import uuid
    from datetime import datetime, timezone
    from app.schemas.scoring import ScoringResultResponse, RiskDecision

    req_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. From direct dictionary
    res_dict = ScoringResultResponse(
        request_id=req_id,
        probability=0.1850,
        decision=RiskDecision.APPROVE,
        model_version="v1-baseline",
        created_at=now,
    )
    assert res_dict.request_id == req_id
    assert res_dict.probability == 0.1850
    assert res_dict.decision == "APPROVE"

    # 2. From mock ORM object (with id and predicted_probability)
    class MockScoringORM:
        id = req_id
        predicted_probability = 0.2500
        decision = "REVIEW"
        model_version = "v1-baseline"
        created_at = now

    res_orm = ScoringResultResponse.model_validate(MockScoringORM())
    assert res_orm.request_id == req_id
    assert res_orm.probability == 0.2500
    assert res_orm.decision == "REVIEW"


def test_scoring_result_response_validation():
    import uuid
    from datetime import datetime, timezone
    from app.schemas.scoring import ScoringResultResponse

    # Probability > 1.0 rejected
    with pytest.raises(ValidationError):
        ScoringResultResponse(
            request_id=uuid.uuid4(),
            probability=1.5,
            decision="DENY",
            model_version="v1",
            created_at=datetime.now(timezone.utc),
        )


def test_paginated_scoring_history_response():
    import uuid
    from datetime import datetime, timezone
    from app.schemas.scoring import ScoringResultResponse, PaginatedScoringHistoryResponse

    item = ScoringResultResponse(
        request_id=uuid.uuid4(),
        probability=0.35,
        decision="REVIEW",
        model_version="v1-baseline",
        created_at=datetime.now(timezone.utc),
    )
    history = PaginatedScoringHistoryResponse(
        items=[item],
        total=1,
        limit=10,
        offset=0,
    )
    assert len(history.items) == 1
    assert history.total == 1
    assert history.limit == 10
    assert history.offset == 0

