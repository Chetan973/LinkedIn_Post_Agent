from typing import Literal, Optional
from pydantic import BaseModel, Field


class PostGenerateRequest(BaseModel):
    """Request schema for generating a new LinkedIn post draft."""
    topic: str = Field(..., description="Topic for the LinkedIn post", min_length=1, max_length=500)
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Unique key for idempotent request handling (prevents duplicate posts)",
        max_length=255
    )

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Building Scalable Distributed Systems with Async Python",
                "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class PostReviewRequest(BaseModel):
    """Request schema for reviewing and providing feedback on a post."""
    feedback: str = Field(..., description="User feedback on the post", min_length=1, max_length=2000)
    status: Literal["approved", "rejected", "needs_revision"] = Field(
        ..., description="Status of the post review"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "feedback": "Add more details about async patterns",
                "status": "needs_revision"
            }
        }


class PostResponse(BaseModel):
    """Response schema for post data."""
    post_id: int = Field(..., description="Unique post identifier")
    topic: str = Field(..., description="Topic of the post")
    status: str = Field(..., description="Current status of the post")
    draft_content: Optional[str] = Field(None, description="Draft content of the post")
    final_content: Optional[str] = Field(None, description="Final published content")
    linkedin_post_id: Optional[str] = Field(None, description="LinkedIn post ID after publishing")
    error_reason: Optional[str] = Field(None, description="Error details if post failed")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "post_id": 1,
                "topic": "Building Scalable Distributed Systems",
                "status": "published",
                "draft_content": "When building distributed systems...",
                "final_content": "When building distributed systems...",
                "linkedin_post_id": "7085123456789012345",
                "error_reason": None
            }
        }
