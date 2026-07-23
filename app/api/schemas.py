from typing import Optional
from pydantic import BaseModel, Field


class PostGenerateRequest(BaseModel):
    """Request schema for generating a new LinkedIn post.

    Topic is selected autonomously inside the agent graph to prevent duplicates
    and maintain category diversity. No input required from caller.

    Can be triggered by a dumb cron scheduler with NO payload.
    """
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Unique key for idempotent request handling (prevents duplicate posts)",
        max_length=255
    )

    class Config:
        json_schema_extra = {
            "example": {
                "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class PostResponse(BaseModel):
    """Response schema for post data."""
    post_id: int = Field(..., description="Unique post identifier")
    topic: str = Field(..., description="Topic of the post")
    status: str = Field(..., description="Current status of the post (queued, published, failed)")
    draft_content: Optional[str] = Field(None, description="Draft content of the post")
    final_content: Optional[str] = Field(None, description="Final published content")
    image_url: Optional[str] = Field(None, description="URL of the AI-generated image")
    linkedin_post_id: Optional[str] = Field(None, description="LinkedIn post ID after publishing")
    error_reason: Optional[str] = Field(None, description="Error details if post failed")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "post_id": 1,
                "topic": "Building Scalable Distributed Systems",
                "status": "published",
                "draft_content": "When building distributed systems, consider async patterns...",
                "final_content": "When building distributed systems, consider async patterns...",
                "linkedin_post_id": "7085123456789012345",
                "error_reason": None
            }
        }
