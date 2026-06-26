from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.review import Review

class TestRun(Base):
    __tablename__ = "test_runs"
    __test__ = False  # Prevent Pytest from collecting this as a test class

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    traceback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="test_runs")
