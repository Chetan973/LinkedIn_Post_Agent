# Implementation Guide: Deploy Three-Status Model

**Estimated Time**: 15-30 minutes  
**Risk Level**: Low (fully backward compatible data migration)  
**Rollback Time**: 5 minutes (if needed)

---

## Step 1: Verify Changes (5 minutes)

All code changes have been applied. Verify by checking these files:

```bash
# Check enum was updated
grep -A 5 "class PostStatus" app/db/models.py
# Should show: QUEUED, PUBLISHED, FAILED (3 values only)

# Check default status changed
grep "default=PostStatus" app/db/models.py
# Should show: default=PostStatus.QUEUED

# Check /review endpoint removed
grep -n "async def review_post" app/api/routers/posts.py
# Should return: (no results)

# Check agent state simplified
grep -c "status:" app/agent/state.py
# Should return: 0 (no status field)
```

---

## Step 2: Backup Your Database (5 minutes)

**CRITICAL**: Always backup before migrations

```bash
# Using PostgreSQL/Supabase
pg_dump -h <host> -U <user> -d linkedin_agent > backup_pre_migration_$(date +%Y%m%d_%H%M%S).sql

# Using Supabase CLI
supabase db dump --local > backup_$(date +%Y%m%d_%H%M%S).sql

# Store in safe location
ls -lh backup_*.sql  # Verify file created and has reasonable size (>1MB)
```

---

## Step 3: Stop Running Services (2 minutes)

```bash
# Stop the FastAPI server
# Press Ctrl+C in the terminal where uvicorn is running

# OR if running in background:
pkill -f uvicorn
pkill -f "python.*main:app"

# Verify no lingering processes
ps aux | grep -E "(uvicorn|python)" | grep -v grep
# Should return: (empty or no app processes)
```

---

## Step 4: Run Database Migration (5 minutes)

```bash
# Navigate to project root
cd E:\Internship\Linkedin_Post_Agent

# Activate virtual environment (if not already active)
.\.venv\Scripts\Activate.ps1  # PowerShell
# OR
source .venv/bin/activate  # Bash/Unix

# View migration that will be applied
alembic history --verbose
# Should show: 003_add_status_enums (last applied)

# Apply pending migration
alembic upgrade head

# Expected output:
# INFO [alembic.runtime.migration] Running upgrade 003_add_status_enums -> 004_three_statuses
# ...
# INFO [alembic.runtime.migration] Done. Scanned from head to base, and 1 new upgrade

# Verify migration applied
alembic current
# Should output: 004_three_statuses

# Verify data was migrated correctly
python -c "
import asyncio
from sqlalchemy import select, text
from app.db import Post, get_session_maker

async def verify():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text('SELECT DISTINCT status FROM posts ORDER BY status'))
        statuses = [row[0] for row in result]
        print(f'Statuses in database: {statuses}')
        
        if all(s in ['queued', 'published', 'failed', None] for s in statuses):
            print('✓ All statuses valid!')
        else:
            print('✗ Invalid statuses found!')

asyncio.run(verify())
"
```

---

## Step 5: Verify Database Schema (3 minutes)

```bash
# Check posts table schema
python -c "
import asyncio
from sqlalchemy import inspect, text
from app.db import Post, get_session_maker

async def verify():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text('''
            SELECT column_name, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'posts' AND column_name = 'status'
        '''))
        row = result.first()
        print(f'Status column default: {row[1]}')

asyncio.run(verify())
"

# Check record counts by status
python -c "
import asyncio
from sqlalchemy import select, func, text
from app.db import Post, get_session_maker

async def verify():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text('SELECT status, COUNT(*) FROM posts GROUP BY status ORDER BY status'))
        for status, count in result:
            print(f'  {status}: {count}')

asyncio.run(verify())
"
```

---

## Step 6: Start Services & Test (5 minutes)

```bash
# Start FastAPI server
uvicorn app.api.main:app --reload

# Wait for startup message:
# INFO:     Application startup complete.

# In a new terminal, run integration tests:

# Test 1: Create a post (should return status: "queued")
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Test Post"}'

# Expected response:
# {
#   "post_id": N,
#   "status": "queued",
#   "message": "Post queued for generation..."
# }

# Test 2: Check post status
curl http://localhost:8000/api/v1/posts/N

# Expected response (while processing):
# {
#   "post_id": N,
#   "status": "queued",
#   "draft_content": null,
#   ...
# }

# Test 3: Verify /review endpoint removed (should return 404)
curl -X POST http://localhost:8000/api/v1/posts/N/review \
  -H "Content-Type: application/json" \
  -d '{"feedback": "test", "status": "approved"}'

# Expected: 404 Not Found
# If you see 405 Method Not Allowed: endpoint still exists (check code)
```

---

## Step 7: Verify OpenAPI Schema Updated (3 minutes)

```bash
# Visit Swagger UI
open http://localhost:8000/docs
# OR
xdg-open http://localhost:8000/docs  # Linux

# Check:
# 1. "/posts/generate" endpoint exists ✓
# 2. "/posts/{post_id}" endpoint exists ✓
# 3. "/posts/{post_id}/review" endpoint MISSING ✓ (should be gone)
# 4. Response schema shows "status" is string with "queued|published|failed"

# OR check OpenAPI spec directly
curl http://localhost:8000/openapi.json | grep -A 20 '"PostResponse"'
# Should show status as one of three values
```

---

## Step 8: Verify Logs Show New Format (2 minutes)

```bash
# Create another test post
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "AsyncIO in Production"}'

# Check uvicorn logs for new format:
# [POST N] Created for topic: AsyncIO in Production
# [POST N] Starting fully automated agent
# ...
# [POST N] Status updated to PUBLISHED

# New format should have [POST N] prefix on all relevant logs
```

---

## Step 9: Clean Up (2 minutes)

```bash
# Remove old code files that are no longer used (optional)
# These files are kept for reference but not called anymore:

# Check if revise_post is used anywhere
grep -r "revise_post" app/ --exclude-dir=.venv

# Expected: Only in app/agent/nodes.py (definition)
# NOT in graph.py or routers (should be removed)

# Check if route_post_state is used anywhere
grep -r "route_post_state" app/ --exclude-dir=.venv

# Expected: Only in app/agent/edges.py (definition)
# NOT used anywhere (can delete edges.py if desired)

# Optional: Delete unused edge routing file
# rm app/agent/edges.py
```

---

## Rollback Procedure (If Needed)

### If Critical Issue Found

```bash
# Stop server
pkill -f uvicorn

# Downgrade migration
alembic downgrade -1
# This maps: queued → drafting, failed → failed_draft

# Restore from backup if data corrupted
psql -h <host> -U <user> -d linkedin_agent < backup_pre_migration_YYYYMMDD_HHMMSS.sql

# Restart server
uvicorn app.api.main:app --reload

# Verify old endpoints work
curl -X POST http://localhost:8000/api/v1/posts/1/review \
  -d '{"feedback": "test", "status": "approved"}'
# Should work (not 404)
```

---

## Testing Scenarios

### Scenario 1: Normal Generation → Publishing

```bash
# 1. Create post
POST http://localhost:8000/api/v1/posts/generate
Body: {"topic": "Test"}
# Returns: status: "queued"

# 2. Wait 30-60 seconds, check status
GET http://localhost:8000/api/v1/posts/1
# Returns: status: "published", linkedin_post_id: "urn:li:...", published_at: "2026-07-21T..."

# 3. Check database
psql: SELECT status, error_reason FROM posts WHERE post_id=1;
# Returns: published | (NULL)
```

### Scenario 2: Generation Error

```bash
# Simulate error (kill Ollama if Gemini quota exceeded)
# Create post that will fail

# Check status
GET http://localhost:8000/api/v1/posts/2
# Returns: status: "failed", error_reason: "All connection attempts failed"

# Check database
psql: SELECT status, error_reason FROM posts WHERE post_id=2;
# Returns: failed | All connection attempts failed
```

### Scenario 3: Duplicate Request Handling

```bash
# Create post with idempotency_key
POST http://localhost:8000/api/v1/posts/generate
Body: {"topic": "Test", "idempotency_key": "abc123"}
# Returns: post_id: 3, status: "queued"

# Send duplicate request with same key
POST http://localhost:8000/api/v1/posts/generate
Body: {"topic": "Test", "idempotency_key": "abc123"}
# Returns: post_id: 3, status: "queued" (same post, no duplicate created)
```

---

## Monitoring

### View Pending Posts
```bash
python -c "
import asyncio
from sqlalchemy import text
from app.db import get_session_maker

async def pending():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text(
            'SELECT post_id, topic, created_at FROM posts WHERE status = \"queued\" ORDER BY created_at DESC'
        ))
        for post_id, topic, created_at in result:
            print(f'{post_id}: {topic[:50]} ({created_at})')

asyncio.run(pending())
"
```

### View Recent Failures
```bash
python -c "
import asyncio
from sqlalchemy import text
from app.db import get_session_maker

async def failures():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text(
            'SELECT post_id, topic, error_reason FROM posts WHERE status = \"failed\" ORDER BY created_at DESC LIMIT 5'
        ))
        for post_id, topic, error_reason in result:
            print(f'{post_id}: {topic[:50]}')
            print(f'   Error: {error_reason[:100]}...')

asyncio.run(failures())
"
```

### View Today's Published Posts
```bash
python -c "
import asyncio
from sqlalchemy import text
from app.db import get_session_maker

async def published():
    session_maker = get_session_maker()
    async with session_maker() as db:
        result = await db.execute(text(
            'SELECT post_id, topic, linkedin_post_id, published_at FROM posts WHERE status = \"published\" AND DATE(published_at) = CURRENT_DATE ORDER BY published_at DESC'
        ))
        for post_id, topic, linkedin_post_id, published_at in result:
            print(f'{post_id}: {topic[:50]} → {linkedin_post_id} ({published_at})')

asyncio.run(published())
"
```

---

## Documentation Files Created

- ✅ `REFACTORING_THREE_STATUS_MODEL.md` - Complete technical documentation
- ✅ `STATUS_MODEL_QUICK_REFERENCE.md` - Quick reference & examples
- ✅ `REFACTORING_SUMMARY.md` - Line-by-line change log
- ✅ `IMPLEMENTATION_GUIDE.md` - This guide

---

## Success Checklist

- [ ] Backup created and verified
- [ ] Services stopped cleanly
- [ ] Migration ran without errors
- [ ] alembic current shows: 004_three_statuses
- [ ] All old status values migrated to new model
- [ ] Server started successfully
- [ ] POST /generate returns status: "queued"
- [ ] GET /{id} returns valid status value
- [ ] POST /{id}/review returns 404
- [ ] Logs show [POST N] prefix format
- [ ] OpenAPI schema updated
- [ ] At least one test post generated successfully

---

## Troubleshooting

### Migration Fails with Permission Error
```bash
# Ensure database user has ALTER TABLE permissions
# If using Supabase, ensure using service role key
```

### Server Won't Start After Migration
```bash
# Check logs: grep "ERROR" uvicorn.log
# Common issues:
# 1. Database password wrong (check .env)
# 2. PostgreSQL syntax error in migration
# 3. Table locks from previous operations

# Clear locks and retry:
psql: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'linkedin_agent';
alembic upgrade head
```

### Old Posts Have Invalid Statuses After Migration
```bash
# This shouldn't happen if migration ran, but if it did:
python -c "
import asyncio
from sqlalchemy import text, update
from app.db import Post, get_session_maker

async def fix():
    session_maker = get_session_maker()
    async with session_maker() as db:
        # Reset any invalid statuses to 'failed'
        result = await db.execute(text(
            'UPDATE posts SET status = \"failed\" WHERE status NOT IN (\"queued\", \"published\", \"failed\")'
        ))
        await db.commit()
        print(f'Fixed {result.rowcount} posts')

asyncio.run(fix())
"
```

---

## Next Steps

1. ✅ **This Week**: Deploy to staging, run all tests
2. **Next Week**: Deploy to production during low-traffic window
3. **Day After**: Monitor logs for any issues
4. **1 Week Later**: Review published posts, verify workflow working
5. **2 Weeks Later**: Archive backup file

---

## Questions?

- **Detailed Reference**: See `REFACTORING_THREE_STATUS_MODEL.md`
- **Quick Lookup**: See `STATUS_MODEL_QUICK_REFERENCE.md`
- **Code Changes**: See `REFACTORING_SUMMARY.md`

---

**Last Updated**: 2026-07-21  
**Status**: ✅ Ready for Deployment  
**Estimated Downtime**: 5-10 minutes (during migration)
