from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.review import Review

class ProposedFix(Base):
    __tablename__ = "proposed_fixes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    diff_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_text: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="proposed_fixes")
