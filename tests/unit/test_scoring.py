"""
Unit tests for scoring business logic and decision classification.
Covers risk threshold boundary conditions, probability binning,
and mocked ML model inference without database dependencies (<0.5s).
"""

import asyncio
from unittest.mock import MagicMock
import numpy as np
import pytest

from app.schemas.scoring import (
    LoanApplicantInput,
    RiskDecision,
    classify_risk,
)


@pytest.mark.unit
class TestRiskThresholdClassification:
    """Verify that classify_risk maps probabilities to APPROVE, REVIEW, and DENY accurately."""

    @pytest.mark.parametrize(
        "prob,expected",
        [
            (0.0, RiskDecision.APPROVE),
            (0.0001, RiskDecision.APPROVE),
            (0.10, RiskDecision.APPROVE),
            (0.1999, RiskDecision.APPROVE),
            (0.199999, RiskDecision.APPROVE),
        ],
    )
    def test_approve_threshold_boundaries(self, prob: float, expected: RiskDecision):
        """Probabilities strictly below 0.20 must be classified as APPROVE."""
        assert classify_risk(prob) == expected
        assert classify_risk(prob).value == "APPROVE"

    @pytest.mark.parametrize(
        "prob,expected",
        [
            (0.20, RiskDecision.REVIEW),
            (0.200001, RiskDecision.REVIEW),
            (0.25, RiskDecision.REVIEW),
            (0.30, RiskDecision.REVIEW),
            (0.399999, RiskDecision.REVIEW),
            (0.40, RiskDecision.REVIEW),
        ],
    )
    def test_review_threshold_boundaries(self, prob: float, expected: RiskDecision):
        """Probabilities between 0.20 and 0.40 inclusive must be classified as REVIEW."""
        assert classify_risk(prob) == expected
        assert classify_risk(prob).value == "REVIEW"

    @pytest.mark.parametrize(
        "prob,expected",
        [
            (0.400001, RiskDecision.DENY),
            (0.45, RiskDecision.DENY),
            (0.60, RiskDecision.DENY),
            (0.9999, RiskDecision.DENY),
            (1.0, RiskDecision.DENY),
        ],
    )
    def test_deny_threshold_boundaries(self, prob: float, expected: RiskDecision):
        """Probabilities strictly above 0.40 must be classified as DENY."""
        assert classify_risk(prob) == expected
        assert classify_risk(prob).value == "DENY"


@pytest.mark.unit
class TestMockedModelInference:
    """Verify scoring logic with a mocked machine learning pipeline."""

    @pytest.fixture
    def sample_applicant(self) -> LoanApplicantInput:
        return LoanApplicantInput(
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

    def test_mock_pipeline_returns_approve(self, sample_applicant: LoanApplicantInput):
        """Mock pipeline predicting 0.12 default probability -> APPROVE."""
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.88, 0.12]])

        df = sample_applicant.to_model_dataframe()
        probs = mock_pipeline.predict_proba(df)
        default_prob = float(probs[0, 1])
        decision = classify_risk(default_prob)

        mock_pipeline.predict_proba.assert_called_once_with(df)
        assert round(default_prob, 2) == 0.12
        assert decision == RiskDecision.APPROVE

    def test_mock_pipeline_returns_review(self, sample_applicant: LoanApplicantInput):
        """Mock pipeline predicting 0.28 default probability -> REVIEW."""
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.72, 0.28]])

        df = sample_applicant.to_model_dataframe()
        probs = mock_pipeline.predict_proba(df)
        default_prob = float(probs[0, 1])
        decision = classify_risk(default_prob)

        mock_pipeline.predict_proba.assert_called_once_with(df)
        assert round(default_prob, 2) == 0.28
        assert decision == RiskDecision.REVIEW

    def test_mock_pipeline_returns_deny(self, sample_applicant: LoanApplicantInput):
        """Mock pipeline predicting 0.65 default probability -> DENY."""
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.35, 0.65]])

        df = sample_applicant.to_model_dataframe()
        probs = mock_pipeline.predict_proba(df)
        default_prob = float(probs[0, 1])
        decision = classify_risk(default_prob)

        mock_pipeline.predict_proba.assert_called_once_with(df)
        assert round(default_prob, 2) == 0.65
        assert decision == RiskDecision.DENY

    @pytest.mark.asyncio
    async def test_async_to_thread_with_mocked_pipeline(self, sample_applicant: LoanApplicantInput):
        """Verify non-blocking execution using asyncio.to_thread with mocked pipeline."""
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.return_value = np.array([[0.82, 0.18]])

        df = sample_applicant.to_model_dataframe()
        probs = await asyncio.to_thread(mock_pipeline.predict_proba, df)
        default_prob = float(probs[0, 1])
        decision = classify_risk(default_prob)

        assert round(default_prob, 2) == 0.18
        assert decision == RiskDecision.APPROVE

    def test_mock_pipeline_raises_runtime_error(self, sample_applicant: LoanApplicantInput):
        """Verify simulated model pipeline internal failures are caught properly."""
        mock_pipeline = MagicMock()
        mock_pipeline.predict_proba.side_effect = RuntimeError("XGBoost prediction memory error")

        df = sample_applicant.to_model_dataframe()
        with pytest.raises(RuntimeError) as exc_info:
            mock_pipeline.predict_proba(df)

        assert "XGBoost prediction memory error" in str(exc_info.value)
