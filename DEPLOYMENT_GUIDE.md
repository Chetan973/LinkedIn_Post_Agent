# 🚀 Production Deployment Guide

## Quick Start

### 1. Database Migration

```bash
alembic upgrade head
```

### 2. Assets Setup

```bash
mkdir -p assets/branding assets/fonts
# Copy linkedin_template.png (1080×1350) to assets/branding/
# Copy Inter-SemiBold.ttf to assets/fonts/
```

### 3. Update .env

```env
PROFILE_NAME=Your Name
PROFILE_ROLE=Your Title
TEMPLATE_IMAGE_PATH=assets/branding/linkedin_template.png
FONTS_PATH=assets/fonts/
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt Pillow
```

### 5. Start Server

```bash
uvicorn app.api.main:app --reload
```

### 6. Test (No topic input required!)

```bash
# Generate post autonomously
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{}'

# Check status
curl http://localhost:8000/api/v1/posts/1
```

## Key Improvements

✅ **Autonomous Topic Selection** - No manual input required
✅ **Deduplication** - No repeated topics
✅ **LLM Tracking** - Know which model was used
✅ **Image Rendering** - PIL template overlay (not AI)
✅ **Thought Generation** - 20-35 word overlays for images
✅ **Content Validation** - Pre-flight checks before publishing
✅ **Observability** - Track category, char count, LLM used, tokens

## Monitoring

```sql
-- LLM usage
SELECT llm_used, COUNT(*) FROM posts WHERE status='published' GROUP BY llm_used;

-- Fallback rate
SELECT COUNT(*) as fallbacks, COUNT(*) FILTER (WHERE llm_fallback_used) as total FROM posts;

-- Content metrics
SELECT category, AVG(char_count) FROM posts WHERE status='published' GROUP BY category;
```

## Files Created/Modified

**New:** 7 files (topic selection, thought generation, validation, image rendering nodes)  
**Modified:** 7 files (state, graph, API, database, LLM, config, schemas)  
**Migration:** 1 file (007_add_observability_columns.py)

All changes are production-ready and fully tested.
