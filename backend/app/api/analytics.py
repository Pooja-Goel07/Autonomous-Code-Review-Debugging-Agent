"""Analytics API — aggregate stats and time-series trends.

Endpoints:
- GET /analytics/summary — header cards data
- GET /analytics/trends — time-bucketed data for Recharts

All endpoints require JWT authentication.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import (
    AnalyticsSummary,
    AnalyticsTrends,
    TrendDataPoint,
    UserResponse,
)
from app.db.session import get_db
from app.models.finding import Finding
from app.models.review import Review

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> AnalyticsSummary:
    """Aggregate counts for the Analytics Dashboard header cards.

    - Total PRs Analyzed: count of all reviews
    - Bugs Caught: count of all findings
    - Fix Acceptance Rate: accepted / (accepted + needs_human_review)
    - Avg Agent Confidence: mean of confidence_score across all reviews
    """
    # Total reviews (= PRs analyzed)
    total_result = await db.execute(select(func.count(Review.id)))
    total_prs = total_result.scalar() or 0

    # Total findings (bugs caught)
    findings_result = await db.execute(select(func.count(Finding.id)))
    total_bugs = findings_result.scalar() or 0

    # Fix acceptance rate
    accepted_result = await db.execute(
        select(func.count(Review.id)).where(Review.decision == "accepted")
    )
    accepted_count = accepted_result.scalar() or 0

    needs_review_result = await db.execute(
        select(func.count(Review.id)).where(Review.decision == "needs_human_review")
    )
    needs_review_count = needs_review_result.scalar() or 0

    denominator = accepted_count + needs_review_count
    acceptance_rate = accepted_count / denominator if denominator > 0 else 0.0

    # Average confidence
    avg_result = await db.execute(select(func.avg(Review.confidence_score)))
    avg_confidence = avg_result.scalar() or 0.0

    return AnalyticsSummary(
        total_prs_analyzed=total_prs,
        total_bugs_caught=total_bugs,
        fix_acceptance_rate=round(acceptance_rate, 4),
        avg_confidence_score=round(float(avg_confidence), 4),
    )


@router.get("/trends", response_model=AnalyticsTrends)
async def get_analytics_trends(
    weeks: int = Query(7, ge=1, le=52, description="Number of weeks of trend data"),
    db: AsyncSession = Depends(get_db),
    _user: UserResponse = Depends(get_current_user),
) -> AnalyticsTrends:
    """Time-bucketed trend data shaped for Recharts.

    Returns weekly datapoints for:
    - bugs_per_week: findings count per week
    - acceptance_rate_over_time: accepted / total per week
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(weeks=weeks)

    # We'll compute trends by iterating over week buckets
    # This approach works with any SQL backend (no DB-specific date_trunc)
    bugs_per_week: list[TrendDataPoint] = []
    acceptance_per_week: list[TrendDataPoint] = []

    for week_offset in range(weeks):
        week_start = start_date + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(weeks=1)
        week_label = f"W{week_offset + 1}"

        # Findings created this week (via their review's created_at)
        findings_count_result = await db.execute(
            select(func.count(Finding.id))
            .join(Review, Finding.review_id == Review.id)
            .where(Review.created_at >= week_start)
            .where(Review.created_at < week_end)
        )
        findings_count = findings_count_result.scalar() or 0
        bugs_per_week.append(TrendDataPoint(period=week_label, value=float(findings_count)))

        # Acceptance rate this week
        week_accepted = await db.execute(
            select(func.count(Review.id))
            .where(Review.created_at >= week_start)
            .where(Review.created_at < week_end)
            .where(Review.decision == "accepted")
        )
        week_total = await db.execute(
            select(func.count(Review.id))
            .where(Review.created_at >= week_start)
            .where(Review.created_at < week_end)
            .where(Review.decision.in_(["accepted", "needs_human_review"]))
        )
        acc = week_accepted.scalar() or 0
        tot = week_total.scalar() or 0
        rate = acc / tot if tot > 0 else 0.0
        acceptance_per_week.append(TrendDataPoint(period=week_label, value=round(rate, 4)))

    return AnalyticsTrends(
        bugs_per_week=bugs_per_week,
        acceptance_rate_over_time=acceptance_per_week,
    )
