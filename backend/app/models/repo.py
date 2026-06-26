from datetime import datetime
from typing import List
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_url: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    webhook_status: Mapped[str] = mapped_column(String(50), default="inactive", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        default=func.now(), 
        nullable=False
    )

    # Relationships
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest",
        back_populates="repo",
        cascade="all, delete-orphan"
    )
