"""Pydantic schemas for API request/response serialization.

These map DB models to the JSON shapes the frontend expects,
matching the wireframes (Dashboard, PR Review Detail, Analytics).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    username: str
    role: str = "developer"


# ---------------------------------------------------------------------------
# Repos
# ---------------------------------------------------------------------------

class RepoCreate(BaseModel):
    github_url: str


class RepoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_url: str
    webhook_status: str
    created_at: datetime
    pr_count: int = 0  # computed in the endpoint


class RepoListResponse(BaseModel):
    repos: list[RepoResponse]
    total: int


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    type: str
    description: str
    file: str
    line: int | None


# ---------------------------------------------------------------------------
# Proposed Fixes
# ---------------------------------------------------------------------------

class ProposedFixResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    diff_text: str
    reasoning_text: str
    accepted: bool


# ---------------------------------------------------------------------------
# Test Runs
# ---------------------------------------------------------------------------

class TestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_id: int
    passed: bool
    failed: bool
    traceback_text: str | None


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class ReviewListItem(BaseModel):
    """Shape for the Dashboard table rows."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    pr_id: int
    pr_number: int = 0
    pr_title: str = ""
    repo_name: str = ""
    confidence_score: float
    decision: str
    created_at: datetime
    findings_count: int = 0
    tests_passed: int = 0
    tests_total: int = 0


class ReviewDetailResponse(BaseModel):
    """Full review detail — matches the PR Review Detail wireframe."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    pr_id: int
    pr_number: int = 0
    pr_title: str = ""
    repo_name: str = ""
    confidence_score: float
    decision: str
    created_at: datetime
    findings: list[FindingResponse] = []
    proposed_fixes: list[ProposedFixResponse] = []
    test_runs: list[TestRunResponse] = []


class ReviewListResponse(BaseModel):
    reviews: list[ReviewListItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class AnalyticsSummary(BaseModel):
    """Aggregate counts for the Analytics Dashboard header cards."""
    total_prs_analyzed: int
    total_bugs_caught: int
    fix_acceptance_rate: float  # 0.0 - 1.0
    avg_confidence_score: float


class TrendDataPoint(BaseModel):
    """Single point in a time-series trend."""
    period: str  # e.g. "2024-W01" or "2024-01-15"
    value: float


class AnalyticsTrends(BaseModel):
    """Time-bucketed trend data for Recharts."""
    bugs_per_week: list[TrendDataPoint]
    acceptance_rate_over_time: list[TrendDataPoint]
