"""Reviews API — list, detail, and re-run for PR reviews.

Endpoints:
- GET /reviews — paginated list with filtering
- GET /reviews/{id} — full detail with findings, fixes, test runs
- POST /reviews/{id}/rerun — reset review to pending (pipeline wiring later)

All endpoints require JWT authentication.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.api.schemas import (
    FindingResponse,
    ProposedFixResponse,
    ReviewDetailResponse,
    ReviewListItem,
    ReviewListResponse,
    TestRunResponse,
    UserResponse,
)
from app.db.session import get_db
from app.models.pull_request import PullRequest
from app.models.repo import Repo
from app.models.review import Review

router = APIRouter()


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    repo_id: int | None = Query(None, description="Filter by repo ID"),
    decision: str | None = Query(None, description="Filter by decision status"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> ReviewListResponse:
    """List reviews with optional filtering and pagination."""
    # Base query
    query = (
        select(Review)
        .join(PullRequest, Review.pr_id == PullRequest.id)
        .join(Repo, PullRequest.repo_id == Repo.id)
        .options(
            selectinload(Review.findings),
            selectinload(Review.test_runs),
        )
    )

    # Apply filters
    if repo_id is not None:
        query = query.where(PullRequest.repo_id == repo_id)
    if decision is not None:
        query = query.where(Review.decision == decision)
    if min_confidence is not None:
        query = query.where(Review.confidence_score >= min_confidence)

    # Count total (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Review.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    reviews = result.scalars().all()

    # Build response items — need PR and Repo info for each
    items: list[ReviewListItem] = []
    for review in reviews:
        # Load related PR and repo
        pr_result = await db.execute(
            select(PullRequest)
            .options(selectinload(PullRequest.repo))
            .where(PullRequest.id == review.pr_id)
        )
        pr = pr_result.scalar_one()

        # Calculate test totals
        tests_passed = sum(1 for tr in review.test_runs if tr.passed and not tr.failed)
        tests_total = len(review.test_runs)

        items.append(
            ReviewListItem(
                id=review.id,
                pr_id=review.pr_id,
                pr_number=pr.pr_number,
                pr_title=pr.title,
                repo_name=pr.repo.github_url,
                confidence_score=review.confidence_score,
                decision=review.decision,
                created_at=review.created_at,
                findings_count=len(review.findings),
                tests_passed=tests_passed,
                tests_total=tests_total,
            )
        )

    return ReviewListResponse(
        reviews=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> ReviewDetailResponse:
    """Get full review detail — includes PR info, findings, proposed fixes, test runs."""
    result = await db.execute(
        select(Review)
        .options(
            selectinload(Review.findings),
            selectinload(Review.proposed_fixes),
            selectinload(Review.test_runs),
        )
        .where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    # Load related PR + repo
    pr_result = await db.execute(
        select(PullRequest)
        .options(selectinload(PullRequest.repo))
        .where(PullRequest.id == review.pr_id)
    )
    pr = pr_result.scalar_one()

    return ReviewDetailResponse(
        id=review.id,
        pr_id=review.pr_id,
        pr_number=pr.pr_number,
        pr_title=pr.title,
        repo_name=pr.repo.github_url,
        confidence_score=review.confidence_score,
        decision=review.decision,
        created_at=review.created_at,
        findings=[FindingResponse.model_validate(f) for f in review.findings],
        proposed_fixes=[ProposedFixResponse.model_validate(pf) for pf in review.proposed_fixes],
        test_runs=[TestRunResponse.model_validate(tr) for tr in review.test_runs],
    )


@router.post("/{review_id}/rerun")
async def rerun_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> dict:
    """Reset a review to pending for re-analysis.

    NOTE: Does not actually re-trigger the pipeline yet — that wiring
    comes in a later stage. For now, just resets the decision field.
    """
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    review.decision = "pending"
    review.confidence_score = 0.0
    await db.commit()

    return {
        "status": "success",
        "review_id": review_id,
        "message": "Review reset to pending. Pipeline re-trigger not yet wired.",
    }
