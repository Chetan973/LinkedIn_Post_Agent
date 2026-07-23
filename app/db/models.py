from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.0 DeclarativeBase."""
    pass


class PostStatus(str, Enum):
    """Enum for post status in fully automated workflow."""
    QUEUED = "queued"
    PUBLISHED = "published"
    FAILED = "failed"


class User(Base):
    """User model for storing LinkedIn user information."""
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    linkedin_profile_url: Mapped[str] = mapped_column(String(500), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, email={self.email})>"


class Post(Base):
    """Post model with complete observability tracking.

    Stores LinkedIn posts with full lifecycle tracking:
    - Topic selection and category diversity
    - Content generation and validation
    - LLM usage (primary vs fallback)
    - Image rendering metrics
    - Publishing status and timestamps
    """
    __tablename__ = "posts"

    # Primary & Foreign Keys
    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content Fields
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    draft_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_thought: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated thought for image overlay (20-35 words)",
    )

    # Status & Publishing
    status: Mapped[str] = mapped_column(
        String,
        default=PostStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    linkedin_post_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Image & Media
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_urn: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="LinkedIn image asset URN (urn:li:image:...)",
    )

    # Observability: Content Metrics
    char_count: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Final content length in characters",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Topic category (java_spring, python_async, etc.) for diversity analysis",
    )

    # Observability: LLM Tracking
    llm_used: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Which LLM model generated content (gemini-3.5-flash or ollama-gemma3:4b)",
    )
    llm_fallback_used: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
        comment="Whether primary Gemini failed and fallback Ollama was used",
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Estimated total tokens used for generation",
    )

    # Observability: Execution Metrics
    execution_time_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Total workflow execution time in milliseconds",
    )

    # Error Handling
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="posts",
    )

    def __repr__(self) -> str:
        return (
            f"<Post(post_id={self.post_id}, topic={self.topic}, "
            f"category={self.category}, status={self.status}, llm={self.llm_used})>"
        )
