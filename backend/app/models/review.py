from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest
    from app.models.finding import Finding
    from app.models.proposed_fix import ProposedFix
    from app.models.test_run import TestRun

class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    decision: Mapped[str] = mapped_column(String(50), default="needs_review", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        default=func.now(), 
        nullable=False
    )

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="reviews")
    findings: Mapped[List["Finding"]] = relationship(
        "Finding",
        back_populates="review",
        cascade="all, delete-orphan"
    )
    proposed_fixes: Mapped[List["ProposedFix"]] = relationship(
        "ProposedFix",
        back_populates="review",
        cascade="all, delete-orphan"
    )
    test_runs: Mapped[List["TestRun"]] = relationship(
        "TestRun",
        back_populates="review",
        cascade="all, delete-orphan"
    )
