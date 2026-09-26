from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional, Union
from uuid import UUID
import numpy as np
import pandas as pd
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator



def _parse_duration_to_months(val: Union[int, float, str, None]) -> int:
    """Parses duration string like '2yrs 3mon' or integer months into integer months."""
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(val))
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
    if years == 0 and months == 0 and s.isdigit():
        return int(s)
    return max(0, (years * 12) + months)


def _parse_date_to_year_month(val: Union[date, str, None], default_year: int = 1990) -> tuple[int, int]:
    """Parses a date or date string into (year, month) with 2-digit century handling."""
    if val is None:
        return default_year, 1
    if isinstance(val, (date, datetime)):
        return val.year, val.month
    val_str = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(val_str, fmt)
            year = dt.year
            if year > 2026:
                year -= 100
            return year, dt.month
        except ValueError:
            continue
    return default_year, 1


class LoanApplicantInput(BaseModel):
    """
    38-Feature Pydantic schema for vehicle loan applicants.
    Accepts both standard snake_case and original CSV column aliases.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "disbursed_amount": 50000.0,
                    "asset_cost": 75000.0,
                    "ltv": 66.67,
                    "branch_id": 67,
                    "supplier_id": 22807,
                    "manufacturer_id": 45,
                    "current_pincode_id": 1441,
                    "state_id": 6,
                    "employee_code_id": 1998,
                    "aadhar_flag": 1,
                    "pan_flag": 1,
                    "voterid_flag": 0,
                    "driving_flag": 0,
                    "passport_flag": 0,
                    "perform_cns_score": 750,
                    "pri_no_of_accts": 3,
                    "pri_active_accts": 2,
                    "pri_overdue_accts": 0,
                    "pri_current_balance": 15000.0,
                    "pri_sanctioned_amount": 100000.0,
                    "pri_disbursed_amount": 100000.0,
                    "sec_no_of_accts": 0,
                    "sec_active_accts": 0,
                    "sec_overdue_accts": 0,
                    "sec_current_balance": 0.0,
                    "sec_sanctioned_amount": 0.0,
                    "sec_disbursed_amount": 0.0,
                    "primary_instal_amt": 2500.0,
                    "sec_instal_amt": 0.0,
                    "new_accts_in_last_six_months": 0,
                    "delinquent_accts_in_last_six_months": 0,
                    "average_acct_age": "2yrs 0mon",
                    "credit_history_length": "3yrs 6mon",
                    "no_of_inquiries": 0,
                    "date_of_birth": "1988-05-15",
                    "disbursal_date": "2018-08-01",
                    "employment_type": "Salaried",
                    "perform_cns_score_description": "A-Very Low Risk",
                }
            ]
        },
    )

    # Financial & Loan Metrics
    disbursed_amount: float = Field(
        ...,
        gt=0,
        description="Amount disbursed to the applicant",
        examples=[50000.0],
        alias="DisbursedAmount",
    )
    asset_cost: float = Field(
        ...,
        gt=0,
        description="Cost of the vehicle asset",
        examples=[65000.0],
        alias="AssetCost",
    )
    ltv: float = Field(
        ...,
        gt=0,
        le=150.0,
        description="Loan to Value ratio percentage",
        examples=[76.9],
        validation_alias=AliasChoices("ltv", "Ltv", "LTV"),
    )

    # Branch, Sourcing & Dealer Identifiers
    branch_id: int = Field(default=1, description="Branch identifier", examples=[67], alias="BranchId")
    supplier_id: int = Field(default=1, description="Vehicle supplier identifier", examples=[22807], alias="SupplierId")
    manufacturer_id: int = Field(default=1, description="Vehicle manufacturer identifier", examples=[45], alias="ManufacturerId")
    current_pincode_id: int = Field(default=1, description="Current pincode identifier", examples=[1441], alias="CurrentPincodeId")
    state_id: int = Field(default=1, description="State identifier", examples=[6], alias="StateId")
    employee_code_id: int = Field(default=1, description="Employee code identifier", examples=[1998], alias="EmployeeCodeId")

    # KYC & Identity Documentation Flags (0 or 1)
    aadhar_flag: int = Field(default=1, ge=0, le=1, description="Aadhar card verification flag", examples=[1], alias="AadharFlag")
    pan_flag: int = Field(default=0, ge=0, le=1, description="PAN card verification flag", examples=[0], alias="PanFlag")
    voterid_flag: int = Field(default=0, ge=0, le=1, description="Voter ID verification flag", examples=[0], alias="VoteridFlag")
    driving_flag: int = Field(default=0, ge=0, le=1, description="Driving license verification flag", examples=[0], alias="DrivingFlag")
    passport_flag: int = Field(default=0, ge=0, le=1, description="Passport verification flag", examples=[0], alias="PassportFlag")

    # Credit Bureau Scores & Primary Loan Accounts
    perform_cns_score: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Bureau CNS risk score (0–1000)",
        examples=[0],
        alias="PerformCnsScore",
    )
    pri_no_of_accts: int = Field(default=0, ge=0, description="Total primary accounts count", examples=[0], alias="PriNoOfAccts")
    pri_active_accts: int = Field(default=0, ge=0, description="Total active primary accounts", examples=[0], alias="PriActiveAccts")
    pri_overdue_accts: int = Field(default=0, ge=0, description="Total overdue primary accounts", examples=[0], alias="PriOverdueAccts")
    pri_current_balance: float = Field(default=0.0, description="Outstanding balance across primary accounts", examples=[0.0], alias="PriCurrentBalance")
    pri_sanctioned_amount: float = Field(default=0.0, ge=0.0, description="Total sanctioned loan amount for primary accounts", examples=[0.0], alias="PriSanctionedAmount")
    pri_disbursed_amount: float = Field(default=0.0, ge=0.0, description="Total disbursed amount across primary accounts", examples=[0.0], alias="PriDisbursedAmount")

    # Secondary (Guarantor/Co-applicant) Accounts
    sec_no_of_accts: int = Field(default=0, ge=0, description="Total secondary accounts count", examples=[0], alias="SecNoOfAccts")
    sec_active_accts: int = Field(default=0, ge=0, description="Total active secondary accounts", examples=[0], alias="SecActiveAccts")
    sec_overdue_accts: int = Field(default=0, ge=0, description="Total overdue secondary accounts", examples=[0], alias="SecOverdueAccts")
    sec_current_balance: float = Field(default=0.0, description="Outstanding balance across secondary accounts", examples=[0.0], alias="SecCurrentBalance")
    sec_sanctioned_amount: float = Field(default=0.0, ge=0.0, description="Total sanctioned loan amount for secondary accounts", examples=[0.0], alias="SecSanctionedAmount")
    sec_disbursed_amount: float = Field(default=0.0, ge=0.0, description="Total disbursed amount across secondary accounts", examples=[0.0], alias="SecDisbursedAmount")

    # Repayment EMI Installments
    primary_instal_amt: float = Field(default=0.0, ge=0.0, description="Monthly primary EMI installment", examples=[0.0], alias="PrimaryInstalAmt")
    sec_instal_amt: float = Field(default=0.0, ge=0.0, description="Monthly secondary EMI installment", examples=[0.0], alias="SecInstalAmt")

    # Delinquency & Inquiries
    new_accts_in_last_six_months: int = Field(default=0, ge=0, description="New accounts opened in past 6 months", examples=[0], alias="NewAcctsInLastSixMonths")
    delinquent_accts_in_last_six_months: int = Field(default=0, ge=0, description="Accounts delinquent in past 6 months", examples=[0], alias="DelinquentAcctsInLastSixMonths")
    average_acct_age: Union[int, str] = Field(default=0, description="Average account age (months or e.g. '2yrs 3mon')", examples=[0], alias="AverageAcctAge")
    credit_history_length: Union[int, str] = Field(default=0, description="Total credit history length (months or e.g. '3yrs 0mon')", examples=[0], alias="CreditHistoryLength")
    no_of_inquiries: int = Field(default=0, ge=0, description="Total credit inquiries made", examples=[0], alias="NoOfInquiries")

    # Dates
    date_of_birth: Union[date, str] = Field(default="1987-01-01", description="Date of birth", examples=["1987-01-01"], alias="DateOfBirth")
    disbursal_date: Union[date, str] = Field(default="2018-08-01", description="Disbursal date", examples=["2018-08-01"], alias="DisbursalDate")

    # Categorical Attributes
    employment_type: Optional[str] = Field(default="Salaried", description="Employment category", examples=["Salaried"], alias="EmploymentType")
    perform_cns_score_description: Optional[str] = Field(
        default="No Bureau History Available",
        description="CNS risk score rating category description",
        examples=["No Bureau History Available"],
        alias="PerformCnsScoreDescription",
    )

    def to_model_dataframe(self) -> pd.DataFrame:
        """
        Converts the validated Pydantic model into a single-row pandas DataFrame
        with exact column names and expected dtypes for the trained scikit-learn Pipeline.
        """
        dob_year, dob_month = _parse_date_to_year_month(self.date_of_birth, default_year=1990)
        disb_year, disb_month = _parse_date_to_year_month(self.disbursal_date, default_year=2018)
        avg_acct_months = _parse_duration_to_months(self.average_acct_age)
        cred_hist_months = _parse_duration_to_months(self.credit_history_length)

        record: Dict[str, Any] = {
            "disbursed_amount": float(self.disbursed_amount),
            "asset_cost": float(self.asset_cost),
            "ltv": float(self.ltv),
            "branch_id": int(self.branch_id),
            "supplier_id": int(self.supplier_id),
            "manufacturer_id": int(self.manufacturer_id),
            "Current_pincode_ID": int(self.current_pincode_id),
            "State_ID": int(self.state_id),
            "Employee_code_ID": int(self.employee_code_id),
            "Aadhar_flag": int(self.aadhar_flag),
            "PAN_flag": int(self.pan_flag),
            "VoterID_flag": int(self.voterid_flag),
            "Driving_flag": int(self.driving_flag),
            "Passport_flag": int(self.passport_flag),
            "PERFORM_CNS.SCORE": int(self.perform_cns_score),
            "PRI.NO.OF.ACCTS": int(self.pri_no_of_accts),
            "PRI.ACTIVE.ACCTS": int(self.pri_active_accts),
            "PRI.OVERDUE.ACCTS": int(self.pri_overdue_accts),
            "PRI.CURRENT.BALANCE": float(self.pri_current_balance),
            "PRI.SANCTIONED.AMOUNT": float(self.pri_sanctioned_amount),
            "PRI.DISBURSED.AMOUNT": float(self.pri_disbursed_amount),
            "SEC.NO.OF.ACCTS": int(self.sec_no_of_accts),
            "SEC.ACTIVE.ACCTS": int(self.sec_active_accts),
            "SEC.OVERDUE.ACCTS": int(self.sec_overdue_accts),
            "SEC.CURRENT.BALANCE": float(self.sec_current_balance),
            "SEC.SANCTIONED.AMOUNT": float(self.sec_sanctioned_amount),
            "SEC.DISBURSED.AMOUNT": float(self.sec_disbursed_amount),
            "PRIMARY.INSTAL.AMT": float(self.primary_instal_amt),
            "SEC.INSTAL.AMT": float(self.sec_instal_amt),
            "NEW.ACCTS.IN.LAST.SIX.MONTHS": int(self.new_accts_in_last_six_months),
            "DELINQUENT.ACCTS.IN.LAST.SIX.MONTHS": int(self.delinquent_accts_in_last_six_months),
            "AVERAGE.ACCT.AGE": int(avg_acct_months),
            "CREDIT.HISTORY.LENGTH": int(cred_hist_months),
            "NO.OF_INQUIRIES": int(self.no_of_inquiries),
            "Date.of.Birth_year": int(dob_year),
            "Date.of.Birth_month": int(dob_month),
            "DisbursalDate_year": int(disb_year),
            "DisbursalDate_month": int(disb_month),
            "Employment.Type": str(self.employment_type or "missing"),
            "PERFORM_CNS.SCORE.DESCRIPTION": str(self.perform_cns_score_description or "missing"),
        }

        return pd.DataFrame([record])


class RiskDecision(str, Enum):
    """Automated risk classification outcomes based on default probability thresholds."""
    APPROVE = "APPROVE"  # Probability < 0.20
    REVIEW = "REVIEW"    # Probability 0.20 – 0.40
    DENY = "DENY"        # Probability > 0.40


def classify_risk(probability: float) -> RiskDecision:
    """
    Classifies a predicted default probability into a standardized RiskDecision:
    - < 0.20: APPROVE
    - 0.20 to 0.40: REVIEW
    - > 0.40: DENY
    """
    if probability < 0.20:
        return RiskDecision.APPROVE
    elif probability <= 0.40:
        return RiskDecision.REVIEW
    else:
        return RiskDecision.DENY


class ScoringResultResponse(BaseModel):
    """
    Standard API response schema for a fraud risk scoring prediction.
    Supports direct serialization from the ScoringRequest ORM model.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "request_id": "c7a8b412-88ec-4c6e-821b-cfc19958ebae",
                "probability": 0.1742,
                "decision": "APPROVE",
                "model_version": "v1-baseline",
                "created_at": "2026-09-26T12:00:00Z",
            }
        },
    )

    request_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("request_id", "id"),
        description="Unique transaction identifier for this scoring request",
    )
    probability: float = Field(
        ...,
        validation_alias=AliasChoices("probability", "predicted_probability"),
        ge=0.0,
        le=1.0,
        description="Predicted probability of loan default (0.0 to 1.0)",
        examples=[0.1742],
    )
    decision: str = Field(
        ...,
        description="Automated risk decision outcome: APPROVE (< 0.20), REVIEW (0.20–0.40), DENY (> 0.40)",
        examples=["APPROVE"],
    )
    model_version: str = Field(
        ...,
        description="Model version identifier evaluated for inference",
        examples=["v1-baseline"],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the scoring evaluation was completed",
    )


class ScoringDetailResponse(ScoringResultResponse):
    """
    Detailed scoring transaction response including applicant input features and user ID.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "request_id": "c7a8b412-88ec-4c6e-821b-cfc19958ebae",
                "user_id": "fa94e502-dcfb-4a58-9c6a-493e9ad1cf23",
                "probability": 0.1742,
                "decision": "APPROVE",
                "model_version": "v1-baseline",
                "created_at": "2026-09-26T12:00:00Z",
                "input_features": {
                    "disbursed_amount": 50000.0,
                    "asset_cost": 75000.0,
                    "ltv": 66.67,
                    "branch_id": 67,
                    "supplier_id": 22807,
                    "perform_cns_score": 750,
                },
            }
        },
    )

    user_id: UUID = Field(..., description="ID of the user who submitted the scoring request")
    input_features: Dict[str, Any] = Field(..., description="Raw applicant input features evaluated")


class PaginatedScoringHistoryResponse(BaseModel):
    """
    Paginated response container for historical scoring queries.
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "request_id": "c7a8b412-88ec-4c6e-821b-cfc19958ebae",
                        "probability": 0.1742,
                        "decision": "APPROVE",
                        "model_version": "v1-baseline",
                        "created_at": "2026-09-26T12:00:00Z",
                    }
                ],
                "total": 42,
                "limit": 10,
                "offset": 0,
            }
        }
    )

    items: list[ScoringResultResponse] = Field(..., description="List of scoring evaluations")
    total: int = Field(..., ge=0, description="Total count of matching records across all pages")
    limit: int = Field(..., ge=1, description="Page limit")
    offset: int = Field(..., ge=0, description="Page offset")


class ModelInfoResponse(BaseModel):
    """
    Public metadata response for the active machine learning risk model.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "version": "v1-baseline",
                "trained_at": "2026-09-21T18:00:00Z",
                "reported_auc": 0.6665,
                "paper_baseline_auc": 0.5180,
                "artifact_path": "artifacts/model_pipeline.joblib",
            }
        },
    )

    version: str = Field(..., description="Model version identifier", examples=["v1-baseline"])
    trained_at: datetime = Field(..., description="UTC timestamp when the model was trained")
    reported_auc: float = Field(..., description="Reproduction holdout test ROC-AUC score", examples=[0.6665])
    paper_baseline_auc: float = Field(..., description="Amazon FDB published paper baseline ROC-AUC", examples=[0.5180])
    artifact_path: str = Field(..., description="Filesystem location of the model artifact", examples=["artifacts/model_pipeline.joblib"])


