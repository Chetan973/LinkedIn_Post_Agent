# Phase 8: AI Image Generation & LinkedIn Media Asset Upload

**Status**: ✅ Complete  
**Date**: 2026-07-21  
**Feature**: Extends the LinkedIn Post Agent to generate and upload images with posts

---

## Overview

Phase 8 adds AI-powered image generation to your LinkedIn Post Agent. The system now:

1. **Generates Images**: Uses OpenAI DALL-E 3 to create professional illustrations based on post topics
2. **Uploads to LinkedIn**: Implements LinkedIn's 3-step media asset upload API
3. **Publishes with Media**: Creates image + text posts on LinkedIn automatically
4. **Graceful Fallback**: If image generation fails, posts text-only (doesn't break the workflow)

---

## Architecture

### New Workflow

```
POST /generate → Create Post (status=QUEUED)
    ↓
Run Agent:
  1. draft_post node → Generate text content
  2. generate_image node → AI image generation (DALL-E 3)
  3. Publish to LinkedIn → Upload image + text
    ↓
Update Status → PUBLISHED (with image_url)
```

### Components Added

| Component | Purpose |
|-----------|---------|
| `app/Services/image_generation.py` | DALL-E 3 image generation |
| `app/Services/linkedin_media.py` | LinkedIn 3-step media upload API |
| `app/agent/nodes.py:generate_image()` | LangGraph node for image generation |
| `alembic/versions/006_add_image_url_column.py` | Database schema migration |
| `app/db/models.py:image_url` | New column in Post model |

---

## Database Changes

### Migration: `006_add_image_url_column.py`

Adds a new column to store generated image URLs:

```sql
ALTER TABLE posts ADD COLUMN image_url TEXT;
```

### Updated Post Model

```python
image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

The image URL is stored for reference and is displayed in API responses.

---

## OpenAI DALL-E 3 Integration

### Configuration

Add your OpenAI API key to `.env`:

```ini
OPENAI_API_KEY=sk-proj-...
```

### Image Generation (`app/Services/image_generation.py`)

```python
generator = ImageGenerator()
image_url = await generator.generate_image(
    topic="Building Scalable Distributed Systems",
    style="professional"
)
```

**Features**:
- Generates 1024x1024 professional images
- Uses intelligent prompting for topic-relevant visuals
- Graceful error handling (doesn't break the workflow)
- Logs image generation progress

---

## LinkedIn 3-Step Media Upload API

### Overview

LinkedIn requires a 3-step process for media uploads:

1. **Register Upload**: Get presigned URL and asset URN
2. **Upload Binary**: PUT image bytes to presigned URL
3. **Create Post**: Include asset URN in UGC payload

### Implementation (`app/Services/linkedin_media.py`)

#### Step 1: Register Upload

```python
uploader = LinkedInMediaUploader(access_token)
upload_url, asset_urn = await uploader.register_upload(person_urn)
```

**Request**:
```
POST /v2/assets?action=registerUpload
{
  "registerUploadRequest": {
    "recipes": ["urn:li:digitalmediarecipe:feedshare-image"],
    "owner": "urn:li:person:ABC123",
    "serviceRelationships": [...]
  }
}
```

**Response**:
```json
{
  "uploadMechanism": {
    "com.linkedin.digitalmediaupload.mediauploadhttpresponse": {
      "uploadUrl": "https://upload.linkedin.com/..."
    }
  },
  "asset": "urn:li:digitalMediaAsset:12345..."
}
```

#### Step 2: Upload Image Bytes

```python
await uploader.upload_image(upload_url, image_url)
```

**Request**:
```
PUT <presigned_url>
Content-Type: image/jpeg
<raw_image_bytes>
```

**Note**: Presigned URL doesn't require Authorization header

#### Step 3: Create UGC Post with Media

```python
ugc_payload = uploader.create_ugc_payload_with_image(
    text=post_text,
    asset_urn=asset_urn,
    person_urn=person_urn
)
```

**Payload Structure**:
```json
{
  "author": "urn:li:person:ABC123",
  "specificContent": {
    "com.linkedin.ugc.share.UGCContent": {
      "shareCommentary": {
        "text": "Post text here"
      },
      "shareMediaCategory": "IMAGE",
      "media": [
        {
          "status": "READY",
          "media": "urn:li:digitalMediaAsset:12345..."
        }
      ]
    }
  },
  "visibility": {
    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
  }
}
```

---

## LangGraph Workflow Changes

### New Node: `generate_image`

Added to `app/agent/nodes.py`:

```python
async def generate_image(state: AgentState) -> dict:
    """Generate image for the post topic using DALL-E 3."""
    image_url = await generate_post_image(state["topic"])
    return {"image_url": image_url, "messages": [...]}
```

**Features**:
- Graceful error handling (skips on API key missing or quota reached)
- Returns `image_url: None` if generation fails
- Doesn't interrupt the workflow

### Updated Graph Flow

**Before**:
```
draft_post → END
```

**After**:
```
draft_post → generate_image → END
```

The image generation is optional and sequential.

---

## Publishing Flow Updates

### Text-Only Posts (Existing)

If no image was generated:
```
publish_to_linkedin(draft_content) → linkedin_post_id
```

### Image + Text Posts (New)

If image was generated:
```
upload_image_to_linkedin(image_url, text, credentials)
  → ugc_payload + asset_urn
  → POST /rest/posts with ugc_payload
  → linkedin_post_id
```

### Fallback Logic

If image upload fails, automatically falls back to text-only post:
```
try:
    publish_with_image()
except:
    log_error()
    publish_text_only()  # Graceful degradation
```

---

## API Response Changes

### POST /api/v1/posts/generate

Response now includes image status:

```json
{
  "post_id": 1,
  "status": "queued",
  "message": "Post queued for generation and publishing..."
}
```

### GET /api/v1/posts/{post_id}

Response includes new fields:

```json
{
  "post_id": 1,
  "topic": "Building Scalable Distributed Systems",
  "status": "published",
  "draft_content": "...",
  "final_content": "...",
  "image_url": "https://oaidalleapiprodpuc.blob.core.windows.net/...",
  "linkedin_post_id": "7085123456789012345",
  "error_reason": null
}
```

---

## Deployment Checklist

### 1. Environment Configuration

Add to `.env`:
```ini
# OpenAI for DALL-E 3 image generation
OPENAI_API_KEY=sk-proj-...your-api-key...
```

### 2. Database Migration

```bash
# Run the migration to add image_url column
alembic upgrade head

# Verify
alembic current  # Should show: 006_add_image_url
```

### 3. Dependencies

Ensure these packages are installed:
```bash
pip install openai aiohttp
```

Check `requirements.txt`:
```
openai>=1.0.0
aiohttp>=3.8.0
```

### 4. Testing

```bash
# 1. Create a checkpoint table (if not already done)
python -c "
import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings

async def setup():
    async with AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL) as saver:
        await saver.setup()

asyncio.run(setup())
"

# 2. Start server
uvicorn app.api.main:app --reload

# 3. Create a post with image generation
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Building Scalable Distributed Systems"}'

# 4. Poll status (image generation takes ~10-30 seconds)
curl http://localhost:8000/api/v1/posts/1

# 5. Verify image_url is populated in response
```

---

## Error Handling

### Image Generation Errors

| Error | Behavior |
|-------|----------|
| OPENAI_API_KEY not set | Skip image generation, publish text-only |
| Quota exceeded | Log warning, publish text-only |
| Network error | Retry once, then publish text-only |
| Generation timeout | Skip image, publish text-only |

### LinkedIn Media Upload Errors

| Error | Behavior |
|-------|----------|
| Register upload fails | Fall back to text-only post |
| Image upload fails | Fall back to text-only post |
| UGC post creation fails | Retry with exponential backoff |

### Database Errors

If `image_url` column missing: Migration will add it automatically.

---

## Performance Considerations

### Image Generation

- **Time**: 10-30 seconds per image (DALL-E 3 standard)
- **Cost**: ~$0.04 per image (at DALL-E 3 standard pricing)
- **Concurrency**: Limited by `MAX_CONCURRENT_LLM_CALLS` semaphore

### LinkedIn Upload

- **Time**: 2-5 seconds for 3-step process
- **Retry**: Exponential backoff on server errors
- **Rate Limit**: Subject to LinkedIn's API limits

### Optimization Tips

1. **Reuse Images**: Cache generated images if same topic used
2. **Batch Generation**: Pre-generate images before posting
3. **Disable Images**: Set `OPENAI_API_KEY=""` to skip image generation

---

## Logging

All image generation and upload operations are logged:

```
[POST 1] Agent execution complete
[POST 1] Generating image for topic: Building Scalable Distributed Systems...
[POST 1] Image generated successfully: https://oaid...
[POST 1] Publishing with image: https://oaid...
[POST 1] Image uploaded. Asset URN: urn:li:digitalMediaAsset:12345
[POST 1] Image post published to LinkedIn: 7085123456789012345
[POST 1] Status updated to PUBLISHED
```

Check logs with:
```bash
grep "\[POST" app.log | tail -20
```

---

## LinkedIn API Reference

### Endpoints Used

1. **Register Upload**
   ```
   POST /v2/assets?action=registerUpload
   ```

2. **Binary Upload** (Presigned URL)
   ```
   PUT <upload_url>
   ```

3. **Create UGC Post**
   ```
   POST /rest/posts
   ```

### Required Credentials

- `LINKEDIN_ACCESS_TOKEN`: OAuth token with `w_member_social` scope
- `LINKEDIN_PERSON_URN`: User's LinkedIn person URN (e.g., `urn:li:person:ABC123`)

---

## Future Enhancements

### Phase 8.1: Multi-Image Posts
- Support carousel posts with multiple images
- Generate 2-3 complementary images per post

### Phase 8.2: Image Customization
- Allow users to specify image style (minimalist, technical, etc.)
- Support custom image dimensions (LinkedIn carousel vs. feed)

### Phase 8.3: Image Caching
- Cache generated images to reduce API calls
- Reuse images for similar topics

### Phase 8.4: Analytics Integration
- Track image engagement separately
- Monitor image performance vs. text-only posts

---

## Troubleshooting

### "OPENAI_API_KEY not set"

**Issue**: Image generation skipped  
**Solution**: Add `OPENAI_API_KEY=sk-proj-...` to `.env`

### "Image upload failed: 401"

**Issue**: LinkedIn authentication failed  
**Solution**: Verify `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN` in `.env`

### "Asset registration failed: 400"

**Issue**: Invalid media recipe  
**Solution**: Ensure image format is JPEG/PNG, under 5MB

### "Image URL not persisted"

**Issue**: `image_url` null in database  
**Solution**: Run migration `alembic upgrade head`

### "Image generation timeout"

**Issue**: DALL-E 3 slow (>30 seconds)  
**Solution**: Check OpenAI API status, may be experiencing load

---

## Summary

✅ **Implemented**:
- DALL-E 3 image generation with fallback
- LinkedIn 3-step media asset upload
- Database schema with `image_url` column
- LangGraph node for async image generation
- Graceful error handling (text-only fallback)
- Updated API responses with image data
- Comprehensive logging throughout

✅ **Tested**:
- Image generation with DALL-E 3
- LinkedIn media upload pipeline
- Fallback to text-only posts
- Database persistence

✅ **Production Ready**:
- All error cases handled
- Graceful degradation
- Proper logging
- Async/await patterns

---

## Next Steps

1. Run `alembic upgrade head` to add `image_url` column
2. Add `OPENAI_API_KEY` to `.env`
3. Test image generation with: `POST /generate`
4. Monitor logs for image generation/upload
5. (Optional) Phase 8.1: Implement multi-image carousel support

