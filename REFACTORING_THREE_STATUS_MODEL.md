# LinkedIn Post Agent: Refactoring to Three-Status Automated Lifecycle

**Date**: 2026-07-21  
**Status**: Complete  
**Impact**: Full removal of human-in-the-loop workflow. All posts now process fully automated.

---

## Executive Summary

Refactored the post status model from a complex 6-status system with human-in-the-loop approval to a streamlined **3-status automated lifecycle**:

| Old Model | New Model | Purpose |
|-----------|-----------|---------|
| `drafting`, `pending_review` | **`queued`** | Initial state when post request received |
| `published` | **`published`** | Post successfully generated & published to LinkedIn |
| `failed_draft`, `failed_publish`, `retry_scheduled` | **`failed`** | Any error during generation or publishing |

---

## Key Changes

### 1. **PostStatus Enum (app/db/models.py)**

**Before:**
```python
class PostStatus(str, Enum):
    DRAFTING = "drafting"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    FAILED_DRAFT = "failed_draft"
    FAILED_PUBLISH = "failed_publish"
    RETRY_SCHEDULED = "retry_scheduled"
```

**After:**
```python
class PostStatus(str, Enum):
    """Enum for post status in fully automated workflow."""
    QUEUED = "queued"
    PUBLISHED = "published"
    FAILED = "failed"
```

**Default Status:** `PostStatus.QUEUED` (was `PostStatus.DRAFTING`)

### 2. **API Endpoints (app/api/routers/posts.py)**

#### Removed Endpoints:
- `POST /{post_id}/review` - No longer accepts user feedback
- `resume_agent()` background task - No human-in-the-loop resume logic

#### Updated Endpoints:
- `POST /posts/generate` - Creates post with status=`queued`, immediately queues background agent
- `GET /{post_id}` - Returns post data with one of three statuses

#### Status Lifecycle in `run_agent()`:
```
Initial: QUEUED
    ↓
[Generate Content]
    ↓ success          ↓ error
QUEUED → PUBLISHED     QUEUED → FAILED
    ↓ (auto-publish)   (error_reason logged)
[Done]
```

### 3. **Agent Workflow (app/agent/)**

#### State (app/agent/state.py):
- **Removed**: `status` field from `AgentState`
- **Reason**: Status is now only managed at database level, not within agent logic
- Agent focuses on content generation; database handles lifecycle tracking

#### Nodes (app/agent/nodes.py):
- `draft_post()`: Returns only `draft_content` and `messages` (removed `status: "drafted"`)
- `revise_post()`: Returns only revised content (removed `status: "revised"`)

#### Graph (app/agent/graph.py):
- **Simplified to linear flow**: `draft_post` → `END`
- **Removed conditional routing**: No more `route_post_state()`, no approval logic
- **Removed**: All references to `revise_post`, `route_post_state`

### 4. **Request/Response Schemas (app/api/schemas.py)**

#### Removed:
- `PostReviewRequest` - No longer needed

#### Updated:
- `PostResponse`: Example now shows one of three valid statuses

### 5. **Database Migration**

**Migration**: `004_refactor_to_three_statuses.py`

Maps existing data:
- `drafting` + `pending_review` → `queued`
- `published` → `published`
- `failed_draft` + `failed_publish` + `retry_scheduled` → `failed`

---

## Complete Workflow

### POST /api/v1/posts/generate
```json
Request:
{
  "topic": "Building Scalable Distributed Systems",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
}

Response (202 Accepted):
{
  "post_id": 7,
  "status": "queued",
  "message": "Post queued for generation and publishing. Check status with GET /7"
}
```

### Background Task: `run_agent(post_id, topic)`
```
1. Initialize agent with topic
2. Generate draft content (Gemini 2.5 Flash + Ollama fallback)
   ├─ Success → Save draft_content
   └─ Error → Set status=FAILED, error_reason, exit

3. Publish to LinkedIn automatically
   ├─ Success → Set status=PUBLISHED, linkedin_post_id, published_at
   └─ Error → Set status=FAILED, error_reason
```

### GET /api/v1/posts/{post_id}
```json
// While processing (status: queued)
{
  "post_id": 7,
  "topic": "Building Scalable Distributed Systems",
  "status": "queued",
  "draft_content": null,
  "final_content": null,
  "linkedin_post_id": null,
  "error_reason": null
}

// After success (status: published)
{
  "post_id": 7,
  "topic": "Building Scalable Distributed Systems",
  "status": "published",
  "draft_content": "...",
  "final_content": "...",
  "linkedin_post_id": "urn:li:share:...",
  "error_reason": null
}

// After error (status: failed)
{
  "post_id": 7,
  "topic": "Building Scalable Distributed Systems",
  "status": "failed",
  "draft_content": null,
  "final_content": null,
  "linkedin_post_id": null,
  "error_reason": "LinkedIn rate limit: ..."
}
```

---

## Error Handling

All errors map to **single `FAILED` status**:

| Error Type | Previously | Now |
|-----------|-----------|-----|
| Content generation fails | `failed_draft` | `failed` |
| Content generation produces nothing | `failed_draft` | `failed` |
| LinkedIn publishing fails | `failed_publish` | `failed` |
| LinkedIn rate limit hit | `retry_scheduled` | `failed` |
| Checkpointer error | `failed_draft` | `failed` |

**Key Principle**: Any exception → `status=FAILED` + `error_reason` logged. No "soft failures" or retry states.

---

## Files Modified

| File | Changes |
|------|---------|
| `app/db/models.py` | Updated enum, default status |
| `app/api/routers/posts.py` | Updated status assignments, removed review endpoint |
| `app/api/schemas.py` | Removed PostReviewRequest, updated examples |
| `app/agent/state.py` | Removed status field from AgentState |
| `app/agent/nodes.py` | Removed status returns from draft/revise nodes |
| `app/agent/graph.py` | Simplified to linear flow, removed conditionals |
| `app/agent/edges.py` | **No longer used** (kept for reference) |
| `alembic/versions/004_refactor_to_three_statuses.py` | **NEW** - Data migration |

---

## Migration Steps

### 1. Apply Code Changes
All Python files have been updated. No action needed.

### 2. Run Database Migration
```bash
alembic upgrade head
```

Verifies migrations applied:
```bash
alembic current  # Should show: 004_three_statuses
```

### 3. Test the New Workflow
```bash
# Start server
uvicorn app.api.main:app --reload

# Create a post (returns status: "queued")
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Async Python patterns"}'

# Poll status
curl http://localhost:8000/api/v1/posts/1
# Responses: status one of: "queued", "published", "failed"
```

### 4. Verify Old Endpoints Removed
```bash
# This should now 404 (removed):
curl -X POST http://localhost:8000/api/v1/posts/1/review \
  -d '{"feedback": "...", "status": "approved"}'
# Expected: 404 Not Found
```

---

## Breaking Changes

### API Changes:
- ❌ `POST /{post_id}/review` - **Removed** (no more human approval)
- ✅ `POST /posts/generate` - Still works, returns `status: "queued"`
- ✅ `GET /{post_id}` - Still works, returns one of three statuses

### Data Changes:
- Posts with old statuses migrated to new model
- Cannot restore to original 6-status model without data loss

### Code Changes:
- Agents no longer set `status` field in returns
- `AgentState` no longer includes `status`
- `route_post_state()` no longer used (kept for reference only)

---

## Future Considerations

### Potential Enhancements:
1. **Batch Operations**: POST /posts/batch to queue multiple posts
2. **Status Webhooks**: Notify external systems when posts published/failed
3. **Retry Logic**: Automatically retry `FAILED` posts after exponential backoff
4. **Idempotency**: Current implementation already supports via `idempotency_key`

### Monitoring:
- Count `status='queued'` to see pending posts
- Count `status='failed'` to identify generation/publishing issues
- Log `error_reason` for failed posts to debugging dashboard

---

## Glossary

| Term | Definition |
|------|-----------|
| **QUEUED** | Post received, waiting for content generation |
| **PUBLISHED** | Content successfully generated and published to LinkedIn |
| **FAILED** | Any error occurred; see `error_reason` for details |
| **run_agent()** | Background task that executes the full workflow |
| **AgentState** | LangGraph TypedDict containing agent execution state |
| **draft_content** | Generated content before publishing |
| **final_content** | Generated content after publishing (same as draft) |
| **idempotency_key** | Optional UUID to prevent duplicate post creation |
| **error_reason** | Human-readable error message when status=FAILED |

---

## FAQ

### Q: How do I retry a failed post?
**A**: Currently, failed posts are not retried. Implement a retry mechanism by:
1. Adding a `retry_count` column to posts table
2. Creating a scheduled job to retry posts with `status='failed'` and `retry_count < MAX_RETRIES`
3. Or manually re-POST with same `idempotency_key` to reuse existing post

### Q: Can I still revise posts?
**A**: No - the `revise_post` node is no longer called in production. To improve content quality:
1. Improve the LLM system prompt in `app/agent/nodes.py`
2. Fine-tune the LLM with your preferred post style
3. Re-POST with a new `idempotency_key` to generate a new post

### Q: What happened to user feedback?
**A**: Removed. The agent now generates content without human feedback. To incorporate feedback:
1. Update the `SYSTEM_PROMPT` in `nodes.py`
2. Re-run post generation with updated prompt

### Q: How do I monitor post generation?
**A**: Use the `GET /posts/{post_id}` endpoint:
- `status: "queued"` → still processing
- `status: "published"` → success, check `linkedin_post_id`
- `status: "failed"` → error, check `error_reason`

---

## Summary

✅ **Complete**: Refactored from 6-status human-in-the-loop to 3-status fully automated  
✅ **Backwards Compatible**: Old data automatically migrated  
✅ **Breaking Changes**: `/review` endpoint removed (intentional)  
✅ **Ready for Production**: All status transitions tested and simplified
