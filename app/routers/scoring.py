import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.scoring import ScoringRequest
from app.models.user import User
from app.schemas.scoring import (
    LoanApplicantInput,
    PaginatedScoringHistoryResponse,
    RiskDecision,
    ScoringDetailResponse,
    ScoringResultResponse,
)

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


@router.get(
    "/scores",
    response_model=PaginatedScoringHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get paginated history of scoring evaluations",
    description=(
        "Retrieves a paginated list of scoring transactions submitted by the authenticated user. "
        "Excludes soft-deleted records and supports filtering by decision, score threshold, and date range."
    ),
)
async def get_scoring_history(
    limit: int = Query(default=10, ge=1, le=100, description="Page size limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    decision: Optional[str] = Query(default=None, description="Filter by decision: APPROVE, REVIEW, DENY"),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Minimum predicted probability"),
    max_score: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Maximum predicted probability"),
    start_date: Optional[datetime] = Query(default=None, description="Filter records created on or after this timestamp"),
    end_date: Optional[datetime] = Query(default=None, description="Filter records created on or before this timestamp"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated scoring history for the authenticated user:
    - Strictly owner-only isolation (current_user.id).
    - Automatically filters out soft-deleted evaluations (deleted_at IS NULL).
    - Supports dynamic filters: decision, score bounds, and date intervals.
    """
    conditions = [
        ScoringRequest.user_id == current_user.id,
        ScoringRequest.deleted_at.is_(None),
    ]

    if decision:
        conditions.append(ScoringRequest.decision == decision.upper())
    if min_score is not None:
        conditions.append(ScoringRequest.predicted_probability >= min_score)
    if max_score is not None:
        conditions.append(ScoringRequest.predicted_probability <= max_score)
    if start_date is not None:
        conditions.append(ScoringRequest.created_at >= start_date)
    if end_date is not None:
        conditions.append(ScoringRequest.created_at <= end_date)

    # 1. Total matching count
    count_stmt = select(func.count()).select_from(ScoringRequest).where(*conditions)
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar() or 0

    # 2. Paginated items
    items_stmt = (
        select(ScoringRequest)
        .where(*conditions)
        .order_by(ScoringRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items_result = await db.execute(items_stmt)
    records = list(items_result.scalars().all())

    return PaginatedScoringHistoryResponse(
        items=records,
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/scores/{score_id}",
    response_model=ScoringDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get detailed scoring evaluation by ID",
    description="Fetches a single scoring request by its unique UUID. Strictly owner-only authorization.",
)
async def get_scoring_record(
    score_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetches a specific scoring transaction:
    - Verifies existence and soft-delete status (404 Not Found if missing or deleted).
    - Verifies ownership (403 Forbidden if accessed by a different user).
    - Returns full evaluation details including input_features JSONB.
    """
    stmt = select(ScoringRequest).where(
        ScoringRequest.id == score_id,
        ScoringRequest.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scoring record not found.",
        )

    if record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this scoring evaluation.",
        )

    return record


