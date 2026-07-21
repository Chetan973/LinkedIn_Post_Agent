# Environment Variables & Configuration Fixes

## Issues Found & Fixed

### 1. **Database Schema Missing Columns** ❌ → ✅
**Problem**: The migration `001_init_init_supabase_schema.py` was missing 4 columns that are defined in `models.py`:
- `idempotency_key` (unique constraint, indexed)
- `linkedin_post_id` (unique constraint, indexed)
- `published_at` (datetime field)
- `error_reason` (text field)

This caused the error:
```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn) column posts.idempotency_key does not exist
```

**Solution**: Created new migration `002_add_missing_post_columns.py` to add these columns.

**Action Required**:
```bash
# Run the new migration
alembic upgrade head
```

---

### 2. **.env File Formatting Issues** ❌ → ✅
**Problems Found**:
- **Inconsistent quoting**: Some values had quotes, others didn't, causing python-dotenv parser confusion
- **Special characters in passwords**: `DATABASE_URL` password contains `$` which needs escaping or quoting
- **Format inconsistency**: 
  ```
  # BEFORE (inconsistent)
  PROJECT_NAME="LinkedIn AI Agent"  # quoted
  DATABASE_URL=postgresql+psycopg...  # not quoted (but has special chars!)
  SUPABASE_URL="https://..."  # quoted
  ```

**Solution**: Standardized `.env` formatting:
- **RULE 1**: Quote values that contain special characters (`$`, `@`, spaces, `:`)
- **RULE 2**: Do NOT quote simple alphanumeric values (cleaner, equivalent)
- **RULE 3**: All URLs, tokens, and strings with special chars → QUOTED

```ini
# ✅ CORRECT FORMAT (after fix)
DATABASE_URL="postgresql+psycopg_async://postgres:<pASSWORD>@db.buubdwydkzjuetybicby.supabase.co:5432/postgres"
SUPABASE_ANON_KEY=<YOUR_KEY>
LANGCHAIN_API_KEY=<YOUR-KEY>
```

---

### 3. **Configuration Class Pydantic v2 Migration** ❌ → ✅
**Problem**: `config.py` was using Pydantic v1 style `Config` class:
```python
# ❌ OLD (Pydantic v1 style)
class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True
```

This still works due to Pydantic's compatibility layer, but is deprecated.

**Solution**: Migrated to Pydantic v2 `model_config`:
```python
# ✅ NEW (Pydantic v2 style)
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str = Field(default="")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }
```

**Benefits**:
- Forward compatible with future Pydantic versions
- Better type hints and validation
- Cleaner API

---

### 4. **LLM Configuration & API Key Validation** ❌ → ✅
**Problem**: 
- The invalid key `"AQ.Ab8RN6L_..."` doesn't match Google's API key format
- No validation that `GEMINI_API_KEY` is actually set
- Errors weren't logged clearly when API key was wrong

**Solution**: Updated `llm_fallback.py`:
```python
class FallbackLLM:
    def __init__(self, temperature: float = 0.7):
        # Validate Gemini API key is set
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            logger.warning(
                "GEMINI_API_KEY is not set or uses placeholder. "
                "Get your key from: https://aistudio.google.com/apikey"
            )
        # ... rest of init
```

**How to get valid Gemini API key**:
1. Go to: https://aistudio.google.com/apikey
2. Click "Create API Key"
3. Copy the key (it's a long alphanumeric string, NOT starting with "AQ.")
4. Add to `.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_key_here
```

---

## .env File Complete Formatting Rules

### ✅ DO's:
```ini
# ✅ Simple values without special chars - NO quotes needed
PROJECT_NAME=LinkedIn AI Agent
OLLAMA_MODEL_NAME=llama3
API_V1_STR=/api/v1

# ✅ URLs, tokens, keys with special chars - QUOTED
DATABASE_URL="postgresql+psycopg_async://user:pass$word@host:5432/db"
SUPABASE_SERVICE_ROLE_KEY=your_SERVICE_token_here...
LINKEDIN_ACCESS_TOKEN=<your_lINKEDIN_token_here>...

# ✅ Boolean values (no quotes)
LANGCHAIN_TRACING_V2=true

# ✅ Comments
# This is a comment
VALID_KEY=value  # inline comments supported
```

### ❌ DON'Ts:
```ini
# ❌ Inconsistent quoting
KEY1="value1"
KEY2=value2
KEY3="value3"  # mixes quoted and unquoted

# ❌ Unquoted values with special chars
DATABASE_URL=postgresql://user:pass$word@host:5432/db  # $ needs escaping!

# ❌ Extra spaces
KEY = value  # spaces around = cause parsing issues
KEY= value   # leading/trailing spaces in values

# ❌ Multi-line values without proper format
MULTILINE_KEY="line1
line2"  # should use different format
```

---

## BONUS FIX: Post Status Enum Missing Values ✅

**New Issue Found**: The database had posts with status `'failed_draft'` but the enum only defined `DRAFTING`, `PENDING_REVIEW`, and `PUBLISHED`.

**Root Cause**: The code was setting invalid status values when errors occurred:
```python
# ❌ INVALID - not in enum
db_post.status = "failed_draft"      # Line 125 posts.py
db_post.status = "failed_publish"    # Line 114
db_post.status = "retry_scheduled"   # Line 104
```

**Solution**: 
1. Added new enum values to `PostStatus`:
   ```python
   class PostStatus(str, Enum):
       DRAFTING = "drafting"
       PENDING_REVIEW = "pending_review"
       PUBLISHED = "published"
       FAILED_DRAFT = "failed_draft"         # NEW
       FAILED_PUBLISH = "failed_publish"     # NEW
       RETRY_SCHEDULED = "retry_scheduled"   # NEW
   ```

2. Updated code to use enum values:
   ```python
   # ✅ CORRECT
   db_post.status = PostStatus.FAILED_DRAFT.value
   db_post.status = PostStatus.FAILED_PUBLISH.value
   db_post.status = PostStatus.RETRY_SCHEDULED.value
   ```

---

## Files Modified

1. ✅ **`.env`** - Fixed formatting, standardized quoting
   - Added placeholder for GEMINI_API_KEY
   - Quoted DATABASE_URL (contains special $)
   - Removed inconsistent quotes

2. ✅ **`app/core/config.py`** - Migrated to Pydantic v2
   - Changed from `class Config:` to `model_config = {}`
   - Added `Field()` imports for clarity
   - Maintained all configuration options

3. ✅ **`app/db/models.py`** - Added missing post status enum values
   - Added `FAILED_DRAFT = "failed_draft"`
   - Added `FAILED_PUBLISH = "failed_publish"`
   - Added `RETRY_SCHEDULED = "retry_scheduled"`

4. ✅ **`app/api/routers/posts.py`** - Fixed status assignments to use enum
   - Changed `status = "failed_draft"` to `status = PostStatus.FAILED_DRAFT.value`
   - Changed `status = "failed_publish"` to `status = PostStatus.FAILED_PUBLISH.value`
   - Changed `status = "retry_scheduled"` to `status = PostStatus.RETRY_SCHEDULED.value`

5. ✅ **`alembic/versions/002_add_missing_post_columns.py`** - New migration
   - Adds `idempotency_key` with unique constraint and index
   - Adds `linkedin_post_id` with unique constraint and index
   - Adds `published_at` datetime field
   - Adds `error_reason` text field

6. ✅ **`alembic/versions/003_add_post_status_enums.py`** - New migration (no-op)
   - Documents that status column uses VARCHAR, not PostgreSQL ENUM
   - Application-level validation via SQLAlchemy Enum type

7. ✅ **`app/Services/llm_fallback.py`** - Better validation & logging
   - Validates GEMINI_API_KEY is set
   - Improved error messages
   - Better logging for debugging connection issues

8. ✅ **`scripts/fix_post_statuses.py`** - New utility script
   - Fixes any posts with invalid status values in the database
   - Verifies all statuses are valid after fixing

---

## Next Steps

### 1. Update `.env` with Real Credentials
```bash
# 1. Get Gemini API key from https://aistudio.google.com/apikey
# 2. Update in .env file:
GEMINI_API_KEY=your_actual_gemini_key_from_aistudio
```

### 2. Fix Database Posts with Invalid Statuses
```bash
# Run the cleanup script to fix any posts with invalid status values
python scripts/fix_post_statuses.py

# Expected output:
# Found 1 posts with status 'failed_draft'
#   → Updating to 'failed_draft'
#   ✓ Updated 1 posts
# ✓ All posts have valid statuses: {'drafting', 'failed_draft', ...}
```

### 3. Run Database Migrations
```bash
# Apply all pending migrations to add missing columns and enum values
alembic upgrade head

# Verify migrations applied:
alembic current  # Should show: 003_add_status_enums
```

### 4. Verify Configuration Loading
```python
# Test in Python shell
from app.core.config import settings
print(f"GEMINI_API_KEY loaded: {bool(settings.GEMINI_API_KEY)}")
print(f"DATABASE_URL: {settings.DATABASE_URL[:50]}...")  # first 50 chars
print(f"OLLAMA_BASE_URL: {settings.OLLAMA_BASE_URL}")
```

### 5. Test Fallback LLM
```python
# Test if both providers can initialize
from app.Services.llm_fallback import FallbackLLM
llm = FallbackLLM()
# Should show warning if GEMINI_API_KEY is not set
```

### 6. Start the Server
```bash
# Start uvicorn and test the /api/v1/posts/generate endpoint
uvicorn app.api.main:app --reload
```

---

## Troubleshooting

### "python-dotenv syntax errors"
- Check for unquoted special characters in passwords
- Verify no extra spaces around `=`
- Ensure quotes are balanced (`"value"` not `"value`)

### "column posts.idempotency_key does not exist"
- Run: `alembic upgrade head` to apply migration
- Verify migration executed: `alembic current` should show `002_add_missing`

### "GEMINI_API_KEY not recognized"
- Check `.env` file is in project root: `ls .env`
- Verify key doesn't contain quotes in `settings.GEMINI_API_KEY` access
- Check config loading: `python -c "from app.core.config import settings; print(settings.GEMINI_API_KEY)"`

### "Ollama connection failed"
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check `OLLAMA_BASE_URL` and `OLLAMA_MODEL_NAME` in `.env`
- Ensure model exists: `ollama list | grep llama3`

---

## Environment Variable Reference

| Variable | Type | Required | Notes |
|----------|------|----------|-------|
| `GEMINI_API_KEY` | string | Yes (for primary LLM) | From https://aistudio.google.com/apikey |
| `DATABASE_URL` | string | Yes | PostgreSQL async URL, quote if has special chars |
| `LANGCHAIN_API_KEY` | string | Optional | For LangSmith tracing |
| `LINKEDIN_ACCESS_TOKEN` | string | Optional | For publishing posts |
| `OLLAMA_BASE_URL` | string | No | Default: http://localhost:11434 |
| `OLLAMA_MODEL_NAME` | string | No | Default: llama3 |

