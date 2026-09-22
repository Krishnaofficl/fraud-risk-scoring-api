"""
Unit tests for Pydantic schemas across the application.
Covers 38-feature LoanApplicantInput validation, alias resolution,
type coercion, boundary condition enforcement, duration/date parsers,
authentication request/response models, and error response models.
Runs strictly in memory without database dependencies (<0.5s).
"""

import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from app.schemas.error import ErrorResponse
from app.schemas.scoring import (
    LoanApplicantInput,
    PaginatedScoringHistoryResponse,
    RiskDecision,
    ScoringDetailResponse,
    ScoringResultResponse,
    _parse_date_to_year_month,
    _parse_duration_to_months,
)


@pytest.mark.unit
class TestApplicantSchema:
    def test_minimal_valid_applicant(self):
        """Minimal input with only required fields uses correct sensible defaults."""
        data = {
            "disbursed_amount": 45000.0,
            "asset_cost": 60000.0,
            "ltv": 75.0,
        }
        applicant = LoanApplicantInput(**data)
        assert applicant.disbursed_amount == 45000.0
        assert applicant.asset_cost == 60000.0
        assert applicant.ltv == 75.0
        assert applicant.employment_type == "Salaried"
        assert applicant.aadhar_flag == 1
        assert applicant.pan_flag == 0
        assert applicant.pri_active_accts == 0

    def test_csv_pascalcase_alias_population(self):
        """Input with original CSV column headers should populate correctly."""
        csv_payload = {
            "DisbursedAmount": 55000.0,
            "AssetCost": 72000.0,
            "LTV": 76.39,
            "BranchId": 67,
            "SupplierId": 22807,
            "ManufacturerId": 45,
            "CurrentPincodeId": 1441,
            "StateId": 6,
            "EmployeeCodeId": 1998,
            "DateOfBirth": "1990-05-15",
            "DisbursalDate": "2018-09-01",
            "EmploymentType": "Self employed",
            "AadharFlag": 1,
            "PanFlag": 1,
            "VoteridFlag": 0,
            "DrivingFlag": 0,
            "PassportFlag": 0,
            "PerformCnsScore": 650,
            "PriActiveAccts": 2,
            "PriOverdueAccts": 0,
            "AverageAcctAge": "1yr 6mon",
            "CreditHistoryLength": "3yrs 2mon",
            "NoOfInquiries": 1,
        }
        applicant = LoanApplicantInput(**csv_payload)
        assert applicant.disbursed_amount == 55000.0
        assert applicant.asset_cost == 72000.0
        assert applicant.employment_type == "Self employed"
        assert applicant.pan_flag == 1
        assert applicant.perform_cns_score == 650

    def test_type_coercion(self):
        """Numeric strings should coerce to floats and ints properly."""
        payload = {
            "disbursed_amount": "60000",
            "asset_cost": "75000.50",
            "ltv": "80",
            "branch_id": "101",
            "perform_cns_score": "720",
        }
        applicant = LoanApplicantInput(**payload)
        assert applicant.disbursed_amount == 60000.0
        assert applicant.asset_cost == 75000.50
        assert applicant.ltv == 80.0
        assert applicant.branch_id == 101
        assert applicant.perform_cns_score == 720

    def test_boundary_validation_negative_or_zero_values(self):
        """Disbursed amount, asset cost, and ltv must be strictly positive."""
        with pytest.raises(ValidationError) as exc:
            LoanApplicantInput(disbursed_amount=0, asset_cost=50000, ltv=70)
        assert "disbursed_amount" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            LoanApplicantInput(disbursed_amount=-500, asset_cost=50000, ltv=70)
        assert "disbursed_amount" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            LoanApplicantInput(disbursed_amount=50000, asset_cost=-10, ltv=70)
        assert "asset_cost" in str(exc.value)

    def test_missing_mandatory_fields(self):
        """Omitting required financial metrics should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            LoanApplicantInput(disbursed_amount=50000)
        err_str = str(exc.value).lower()
        assert "assetcost" in err_str or "asset_cost" in err_str
        assert "ltv" in err_str

    def test_duration_parsing(self):
        """Verify year/month duration strings parse into total months integer."""
        assert _parse_duration_to_months("2yrs 3mon") == 27
        assert _parse_duration_to_months("0yrs 0mon") == 0
        assert _parse_duration_to_months("5yrs 11mon") == 71
        assert _parse_duration_to_months("1yr 0mon") == 12
        assert _parse_duration_to_months(24) == 24
        assert _parse_duration_to_months("18") == 18
        assert _parse_duration_to_months(None) == 0
        assert _parse_duration_to_months("invalid_text") == 0

    def test_date_parsing(self):
        """Verify ISO dates and 2-digit century dates parse to year and month."""
        year, month = _parse_date_to_year_month("1988-11-25")
        assert year == 1988
        assert month == 11

        year, month = _parse_date_to_year_month("15-08-95")
        assert year == 1995
        assert month == 8

        # Fallback for invalid format
        year, month = _parse_date_to_year_month("not-a-date", default_year=1990)
        assert year == 1990
        assert month == 1

    def test_to_model_dataframe_structure(self):
        """Verify the extracted DataFrame matches the 40 columns expected by ML pipeline."""
        applicant = LoanApplicantInput(
            disbursed_amount=50000.0,
            asset_cost=65000.0,
            ltv=76.9,
            date_of_birth="1992-04-10",
            disbursal_date="2018-10-01",
            average_acct_age="2yrs 1mon",
            credit_history_length="3yrs 6mon",
        )
        df = applicant.to_model_dataframe()
        assert df.shape == (1, 40)
        assert "AVERAGE.ACCT.AGE" in df.columns
        assert df["AVERAGE.ACCT.AGE"].iloc[0] == 25
        assert "CREDIT.HISTORY.LENGTH" in df.columns
        assert df["CREDIT.HISTORY.LENGTH"].iloc[0] == 42
        assert "Date.of.Birth_year" in df.columns
        assert df["Date.of.Birth_year"].iloc[0] == 1992


@pytest.mark.unit
class TestScoringResponseSchemas:
    def test_scoring_result_response_valid(self):
        req_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        res = ScoringResultResponse(
            request_id=req_id,
            probability=0.1523,
            decision=RiskDecision.APPROVE,
            model_version="v1-baseline",
            created_at=now,
        )
        assert res.request_id == req_id
        assert res.probability == 0.1523
        assert res.decision == "APPROVE"

    def test_scoring_result_response_from_orm(self):
        req_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

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

    def test_scoring_result_probability_bounds(self):
        req_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ScoringResultResponse(
                request_id=req_id,
                probability=1.05,
                decision=RiskDecision.DENY,
                model_version="v1-baseline",
                created_at=now,
            )

        with pytest.raises(ValidationError):
            ScoringResultResponse(
                request_id=req_id,
                probability=-0.01,
                decision=RiskDecision.APPROVE,
                model_version="v1-baseline",
                created_at=now,
            )

    def test_paginated_history_response(self):
        now = datetime.now(timezone.utc)
        item = ScoringResultResponse(
            request_id=uuid.uuid4(),
            probability=0.32,
            decision=RiskDecision.REVIEW,
            model_version="v1-baseline",
            created_at=now,
        )
        paginated = PaginatedScoringHistoryResponse(
            items=[item],
            total=10,
            limit=5,
            offset=0,
        )
        assert len(paginated.items) == 1
        assert paginated.total == 10
        assert paginated.limit == 5
        assert paginated.offset == 0


@pytest.mark.unit
class TestAuthSchemas:
    def test_user_register_valid(self):
        data = {"email": "analyst@example.com", "password": "SecurePassword123!"}
        reg = UserRegister(**data)
        assert reg.email == "analyst@example.com"
        assert reg.password == "SecurePassword123!"

    def test_user_register_invalid_email(self):
        with pytest.raises(ValidationError):
            UserRegister(email="not-an-email", password="ValidPassword123!")

    def test_user_register_short_password(self):
        with pytest.raises(ValidationError):
            UserRegister(email="valid@example.com", password="123")

    def test_user_login_valid(self):
        model = UserLogin(email="user@example.com", password="anypassword")
        assert model.email == "user@example.com"
        assert model.password == "anypassword"

    def test_token_response(self):
        token = TokenResponse(access_token="abc.def.ghi", token_type="bearer", expires_in=3600)
        assert token.access_token == "abc.def.ghi"
        assert token.token_type == "bearer"
        assert token.expires_in == 3600

    def test_user_response_from_attributes(self):
        test_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        class MockUserORM:
            id = test_id
            email = "analyst@bank.com"
            is_active = True
            created_at = now

        user_resp = UserResponse.model_validate(MockUserORM())
        assert user_resp.id == test_id
        assert user_resp.email == "analyst@bank.com"
        assert user_resp.is_active is True
        assert user_resp.created_at == now


@pytest.mark.unit
class TestErrorEnvelopeSchema:
    def test_error_response_valid(self):
        err = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Payload failed schema validation",
            detail=[{"field": "disbursed_amount", "issue": "Must be greater than 0"}],
            request_id="req_test_12345",
        )
        assert err.error_code == "VALIDATION_ERROR"
        assert err.message == "Payload failed schema validation"
        assert len(err.detail) == 1
        assert err.request_id == "req_test_12345"
        assert isinstance(err.timestamp, datetime)

    def test_error_response_defaults(self):
        err = ErrorResponse(
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected condition occurred",
        )
        assert err.error_code == "INTERNAL_SERVER_ERROR"
        assert err.message == "An unexpected condition occurred"
        assert err.detail is None
        assert err.request_id is None
        assert isinstance(err.timestamp, datetime)
        assert err.timestamp.tzinfo == timezone.utc

    def test_error_response_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ErrorResponse(message="Missing error_code")

        with pytest.raises(ValidationError):
            ErrorResponse(error_code="SOME_ERROR")
