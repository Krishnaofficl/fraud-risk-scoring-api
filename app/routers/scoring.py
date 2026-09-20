import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.scoring import ScoringRequest
from app.models.user import User
from app.schemas.scoring import LoanApplicantInput, RiskDecision, ScoringResultResponse

router = APIRouter(prefix="/v1", tags=["Scoring"])


@router.post(
    "/score",
    response_model=ScoringResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Score a single vehicle loan applicant",
    description=(
        "Evaluates the applicant's 38 features using the trained ML pipeline in a non-blocking threadpool. "
        "Applies automated risk decision thresholds (< 0.20 APPROVE, 0.20–0.40 REVIEW, > 0.40 DENY), "
        "stores the audit record in PostgreSQL, and returns the prediction result."
    ),
)
async def score_applicant(
    applicant: LoanApplicantInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluates risk for a loan applicant:
    - Verifies user authentication.
    - Converts inputs into a 40-feature DataFrame.
    - Executes non-blocking inference via asyncio.to_thread.
    - Determines decision threshold (< 0.20: APPROVE, 0.20–0.40: REVIEW, > 0.40: DENY).
    - Persists audit trail in PostgreSQL scoring_requests table (with JSONB input features).
    - Returns standardized ScoringResultResponse.
    """
    pipeline = getattr(request.app.state, "model_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine learning model pipeline is not loaded.",
        )

    model_version = getattr(request.app.state, "model_version", "unknown")

    # 1. Convert validated inputs into model-compatible DataFrame
    df = applicant.to_model_dataframe()

    # 2. Non-blocking model inference
    try:
        probs = await asyncio.to_thread(pipeline.predict_proba, df)
        prob_default = float(probs[0, 1])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(exc)}",
        )

    # 3. Apply Decision Thresholds
    if prob_default < 0.20:
        decision = RiskDecision.APPROVE.value
    elif prob_default <= 0.40:
        decision = RiskDecision.REVIEW.value
    else:
        decision = RiskDecision.DENY.value

    # 4. Persist to PostgreSQL
    scoring_record = ScoringRequest(
        user_id=current_user.id,
        input_features=applicant.model_dump(by_alias=True, mode="json"),
        predicted_probability=round(prob_default, 4),
        decision=decision,
        model_version=model_version,
    )
    db.add(scoring_record)
    await db.commit()
    await db.refresh(scoring_record)

    return scoring_record
