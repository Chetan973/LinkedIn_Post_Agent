# Phase 8: AI Image Generation & LinkedIn Media Asset Upload Integration

## Objective
Extend the fully automated FastAPI, LangGraph, and PostgreSQL LinkedIn Post Agent to support **Image + Text posts**. This phase introduces an AI image generation node (using OpenAI DALL-E 3) and implements LinkedIn's mandatory 3-step media asset upload API.

---

## Task Checklist

### 1. Database & Schema Updates
- [ ] Add an `image_url` (Text, nullable) column to the `posts` table in Supabase.
- [ ] Update the SQLAlchemy `Post` model (`app/models/post.py`) to include `image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`.
- [ ] Ensure background worker correctly saves the `image_url` upon successful publishing.

### 2. LangGraph Image Generation Node
- [ ] Create an image generation utility using the OpenAI DALL-E 3 API based on the post's `topic`.
- [ ] Download or store the generated image locally/temporarily or capture its secure URL.
- [ ] Add the image generation step as a node in your LangGraph workflow (`app/agent/graph.py`).

### 3. LinkedIn Media Asset Upload API Integration
- [ ] Implement LinkedIn's 3-step upload pipeline in your social service client:
  1. **Register Upload:** Call `https://api.linkedin.com/v2/assets?action=registerUpload` with the `urn:li:digitalmediarecipe:feedshare-image` recipe to receive an upload URL and digital media asset URN (`urn:li:digitalMediaAsset:...`).
  2. **Binary Upload:** Perform an HTTP `PUT` request with the image file binary bytes to the received upload URL.
  3. **Publishing Payload:** Update the UGC post creation payload to set `shareMediaCategory: "IMAGE"` and append the `media` array containing the asset URN alongside the commentary text.

---

## Claude Execution Prompt

Copy and paste the prompt below to let Claude implement Phase 8 directly into your codebase:

```text
Please act as an Expert Senior Backend and AI Engineer. My FastAPI, LangGraph, and PostgreSQL LinkedIn Post Agent is successfully generating text content and publishing to LinkedIn. 

Please implement "Phase 8: Image Generation & LinkedIn Media Asset Uploads" with the following requirements:

1. Database Model (`app/models/post.py`):
   - Add `image_url` column (Text, nullable) to the Post model.

2. LangGraph Image Generation:
   - Add a node that calls OpenAI's DALL-E 3 API using the post topic to generate a relevant visual.
   - Save the image URL or temporary file path to the agent state.

3. LinkedIn 3-Step Media Upload API:
   - Implement the helper function to register the upload via `[https://api.linkedin.com/v2/assets?action=registerUpload](https://api.linkedin.com/v2/assets?action=registerUpload)`.
   - Upload the image bytes via `PUT` to the returned upload URL.
   - Modify the LinkedIn UGC Post creation payload to include `shareMediaCategory: "IMAGE"` and pass the resulting media asset URN (`urn:li:digitalMediaAsset:...`).

Please provide the precise code updates for the database models, graph nodes, and LinkedIn client service.