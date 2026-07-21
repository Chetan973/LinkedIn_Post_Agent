# Three-Status Model: Quick Reference

## Status Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  POST /api/v1/posts/generate { "topic": "..." }                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ status=QUEUED │  (Waiting for agent to start)
                    └──────────────┘
                           │
          ┌────────────────┬────────────────┐
          │                │                │
          ▼                │                ▼
    [Generate]             │           [Generate FAILS]
         │                 │                │
         ├─ Success ◄──────┤                └──► error_reason logged
         │                 │
         ▼                 │          ┌──────────────┐
   [Publish]              │          │ status=FAILED │
         │                 │          └──────────────┘
         ├─ Success ◄──────┘
         │
         ▼
    ┌────────────────┐
    │ status=PUBLISHED │  (Done - on LinkedIn)
    │ linkedin_post_id │
    │ published_at     │
    └────────────────┘
         │
    └────► (Or FAILED if publish error)
```

---

## Status Values

### ✅ QUEUED
- **Meaning**: Post received, waiting for generation
- **Database**: `status = 'queued'`
- **Transitions To**: `PUBLISHED` or `FAILED`
- **Fields Set**:
  - `status` ✓
  - `topic` ✓
  - `created_at` ✓
  - All other fields `NULL`

### ✅ PUBLISHED
- **Meaning**: Content generated and published to LinkedIn
- **Database**: `status = 'published'`
- **Transitions To**: None (terminal state)
- **Fields Set**:
  - `status` = 'published' ✓
  - `draft_content` ✓
  - `final_content` ✓
  - `linkedin_post_id` ✓
  - `published_at` ✓
  - `error_reason` = NULL

### ❌ FAILED
- **Meaning**: Any error during generation or publishing
- **Database**: `status = 'failed'`
- **Transitions To**: None (terminal state)
- **Fields Set**:
  - `status` = 'failed' ✓
  - `error_reason` ✓ (human-readable error message)
  - `draft_content` may be partial/NULL
  - `final_content` = NULL
  - `linkedin_post_id` = NULL

---

## Common Status Queries

### Find all queued posts (still processing)
```sql
SELECT post_id, topic, created_at 
FROM posts 
WHERE status = 'queued' 
ORDER BY created_at;
```

### Find all published posts today
```sql
SELECT post_id, topic, linkedin_post_id 
FROM posts 
WHERE status = 'published' 
AND DATE(published_at) = CURRENT_DATE;
```

### Find all failed posts with error reasons
```sql
SELECT post_id, topic, error_reason, created_at 
FROM posts 
WHERE status = 'failed' 
ORDER BY created_at DESC;
```

### Count by status
```sql
SELECT status, COUNT(*) as count 
FROM posts 
GROUP BY status;
```

---

## API Examples

### 1. Create a Post (Immediately Returns QUEUED)
```bash
POST http://localhost:8000/api/v1/posts/generate
Content-Type: application/json

{
  "topic": "Building Scalable Distributed Systems",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
}

# Response (202 Accepted - request queued, no waiting)
{
  "post_id": 42,
  "status": "queued",
  "message": "Post queued for generation and publishing. Check status with GET /42"
}
```

### 2. Check Status While Processing (Still QUEUED)
```bash
GET http://localhost:8000/api/v1/posts/42

# Response while processing:
{
  "post_id": 42,
  "topic": "Building Scalable Distributed Systems",
  "status": "queued",
  "draft_content": null,
  "final_content": null,
  "linkedin_post_id": null,
  "error_reason": null
}
```

### 3. Check Status After Success (PUBLISHED)
```bash
GET http://localhost:8000/api/v1/posts/42

# Response after ~30-60 seconds:
{
  "post_id": 42,
  "topic": "Building Scalable Distributed Systems",
  "status": "published",
  "draft_content": "When building distributed systems...",
  "final_content": "When building distributed systems...",
  "linkedin_post_id": "urn:li:ugcPost:7085123456789012345",
  "error_reason": null
}
```

### 4. Check Status After Error (FAILED)
```bash
GET http://localhost:8000/api/v1/posts/42

# Response if generation/publishing failed:
{
  "post_id": 42,
  "topic": "Building Scalable Distributed Systems",
  "status": "failed",
  "draft_content": null,
  "final_content": null,
  "linkedin_post_id": null,
  "error_reason": "LinkedIn rate limit: You exceeded your current quota..."
}
```

---

## Status Transitions Map

| Current | Error? | New Status | error_reason |
|---------|--------|-----------|-------------|
| `QUEUED` | ❌ | `PUBLISHED` | NULL |
| `QUEUED` | ✅ Generation fails | `FAILED` | "Content generation failed: {error}" |
| `QUEUED` | ✅ Publishing fails | `FAILED` | "Publishing error: {error}" |
| `QUEUED` | ✅ Rate limited | `FAILED` | "LinkedIn rate limit: {error}" |
| `PUBLISHED` | - | (terminal) | NULL |
| `FAILED` | - | (terminal) | (set at error time) |

---

## Old Model → New Model Mapping

These mappings were applied during migration `004_refactor_to_three_statuses`:

| Old Status | New Status | Reason |
|-----------|-----------|--------|
| `drafting` | `queued` | Both mean "in progress" |
| `pending_review` | `queued` | No more human review |
| `published` | `published` | Same meaning |
| `failed_draft` | `failed` | All errors → single status |
| `failed_publish` | `failed` | All errors → single status |
| `retry_scheduled` | `failed` | No more retry scheduling |

---

## Implementation Details

### Where Status is Set

1. **Creation** (`POST /generate` endpoint):
   ```python
   post = Post(
       topic=request.topic,
       status=PostStatus.QUEUED,  # Always start here
       ...
   )
   ```

2. **Success** (`run_agent()` background task):
   ```python
   db_post.status = PostStatus.PUBLISHED.value
   db_post.linkedin_post_id = linkedin_post_id
   db_post.published_at = datetime.now(timezone.utc)
   ```

3. **Any Error**:
   ```python
   db_post.status = PostStatus.FAILED.value
   db_post.error_reason = str(e)  # Human-readable error
   ```

### Status Column
- **Type**: VARCHAR (string)
- **Default**: 'queued'
- **Constraints**: NOT NULL, indexed for fast queries
- **Valid Values**: 'queued', 'published', 'failed'

---

## Monitoring & Observability

### Health Check Query
```sql
-- Posts currently being processed
SELECT COUNT(*) as queued_count 
FROM posts 
WHERE status = 'queued' 
AND created_at > NOW() - INTERVAL '1 hour';

-- Recent failures
SELECT COUNT(*) as failed_today 
FROM posts 
WHERE status = 'failed' 
AND DATE(created_at) = CURRENT_DATE;
```

### Logging
All state transitions logged with `[POST {post_id}]` prefix:
```
[POST 42] Created for topic: Building Scalable Distributed Systems
[POST 42] Starting fully automated agent
[POST 42] Draft content saved
[POST 42] Successfully published to LinkedIn: urn:li:ugcPost:...
[POST 42] Status updated to PUBLISHED
```

### Common Patterns
- **Find stuck posts**: `WHERE status = 'queued' AND created_at < NOW() - INTERVAL '10 minutes'`
- **Find recent failures**: `WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 day'`
- **Success rate**: `SELECT 100 * COUNT(*) FILTER (WHERE status='published') / COUNT(*) as success_rate FROM posts`

---

## Troubleshooting

### Q: Post stuck in QUEUED for 10 minutes?
**A**: Check logs for errors:
```bash
grep "\[POST 42\]" app.log
```
- If no logs: background task may not have started
- If error logs: Check `POST 42` status in database to see if updated to FAILED

### Q: Can't access /posts/{id}/review endpoint?
**A**: Endpoint removed. The system is now fully automated. To improve generation:
- Update system prompt in `app/agent/nodes.py`
- Regenerate post (submit new request with different topic)

### Q: How to handle failed posts?
**A**: Currently no automatic retry. Options:
1. Manually check `error_reason` field
2. Fix the underlying issue (e.g., LinkedIn credentials)
3. Re-submit the post with same `idempotency_key` to reuse entry

### Q: Need to understand an error?
**A**: Check `error_reason` field on the failed post:
```bash
curl http://localhost:8000/api/v1/posts/{post_id} | jq .error_reason
```

---

## Database Schema

```sql
CREATE TABLE posts (
  post_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  topic VARCHAR(255) NOT NULL,
  draft_content TEXT,
  final_content TEXT,
  status VARCHAR NOT NULL DEFAULT 'queued',  -- ← simplified
  idempotency_key VARCHAR(255) UNIQUE,
  linkedin_post_id VARCHAR(255) UNIQUE,
  published_at TIMESTAMP WITH TIME ZONE,
  error_reason TEXT,  -- ← stores error details
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

---

## Summary

✨ **Simplified**: 6 statuses → 3 statuses  
⚡ **Automated**: No human-in-the-loop, full end-to-end automation  
📊 **Observable**: Clear terminal states, detailed error logging  
🔄 **Idempotent**: Duplicate requests handled via `idempotency_key`
