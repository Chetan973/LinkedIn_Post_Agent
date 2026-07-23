# Phase 8 Quick Start Guide

**Time to Deploy**: 10 minutes  
**Dependencies**: OpenAI API key  
**Breaking Changes**: None (fully backward compatible)

---

## 1. Add OpenAI API Key to `.env`

```bash
# Edit .env and add:
OPENAI_API_KEY=sk-proj-...your-openai-key...
```

Get your key from: https://platform.openai.com/api-keys

---

## 2. Run Database Migration

```bash
# Stop server first (Ctrl+C)

# Run migration to add image_url column
alembic upgrade head

# Verify
alembic current  # Should show: 006_add_image_url
```

---

## 3. Start Server

```bash
uvicorn app.api.main:app --reload
```

---

## 4. Test Image Generation

```bash
# Create a post (will generate image + text automatically)
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Building Scalable Distributed Systems with Python"}'

# Response:
# {
#   "post_id": 1,
#   "status": "queued"
# }

# Wait 30-60 seconds, then check status:
curl http://localhost:8000/api/v1/posts/1

# Response will include:
# {
#   "status": "published",
#   "image_url": "https://oaidalleapi...",
#   "linkedin_post_id": "7085123...",
#   ...
# }
```

---

## 5. Monitor Logs

Watch for image generation:

```bash
# In server output, look for:
# [POST 1] Generating image for topic: ...
# [POST 1] Image generated successfully: https://...
# [POST 1] Publishing with image: https://...
# [POST 1] Image uploaded. Asset URN: urn:li:digitalMediaAsset:...
# [POST 1] Status updated to PUBLISHED
```

---

## What's New

### ✅ Automatic Image Generation
- Every post now gets an AI-generated professional image
- Uses OpenAI DALL-E 3
- ~10-30 seconds per image

### ✅ LinkedIn Media Upload
- 3-step media asset upload pipeline
- Images appear on LinkedIn with posts
- Fallback to text-only if image fails

### ✅ Database Changes
- New `image_url` column in `posts` table
- Stores URL of generated image
- Fully backward compatible

### ✅ API Updates
- `GET /posts/{id}` now includes `image_url`
- Response shows image status

---

## Rollback (If Needed)

If you need to disable image generation:

**Option 1: Remove API Key**
```ini
# In .env, set:
OPENAI_API_KEY=
```
Posts will be published as text-only (no error).

**Option 2: Revert Migration**
```bash
alembic downgrade -1  # Removes image_url column
```

---

## Costs

- **DALL-E 3 Standard**: ~$0.04 per image
- **LinkedIn API**: Free (no additional cost)

---

## Troubleshooting

### Image generation fails but post still publishes
✅ This is correct! Posts fall back to text-only if image fails.

### Image URL is NULL
Check logs for generation errors. If OPENAI_API_KEY not set, this is expected.

### LinkedIn publishing fails with image
Try removing OPENAI_API_KEY to test text-only posts first.

---

## Files Changed

| File | Change |
|------|--------|
| `.env` | Add OPENAI_API_KEY |
| `alembic/versions/006_*` | New migration |
| `app/db/models.py` | Add image_url column |
| `app/agent/nodes.py` | Add generate_image node |
| `app/agent/graph.py` | Include generate_image in workflow |
| `app/Services/image_generation.py` | **NEW** - DALL-E 3 integration |
| `app/Services/linkedin_media.py` | **NEW** - LinkedIn 3-step upload |
| `app/api/routers/posts.py` | Update publishing with images |
| `app/api/schemas.py` | Add image_url to PostResponse |

---

## Next Steps

1. ✅ Deploy Phase 8
2. 📊 Monitor image generation quality
3. 🔧 Fine-tune image prompts if needed
4. 📈 Track LinkedIn engagement with images

---

## Support

For issues, check `PHASE_8_IMAGE_GENERATION.md` for detailed documentation.
