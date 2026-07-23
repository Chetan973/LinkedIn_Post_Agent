# LinkedIn_Post_Agent
🚀 LinkedIn Post Agent (AI Powered)

An Autonomous AI Agent built with LangGraph + FastAPI that researches topics, generates high-quality LinkedIn posts, creates branded images, and publishes both text and image posts directly to LinkedIn using the latest LinkedIn REST APIs.

📌 Project Overview

The LinkedIn Post Agent automates the complete LinkedIn content creation workflow.

Instead of manually:

Researching a topic
Writing a post
Creating an image
Formatting hashtags
Uploading media
Publishing to LinkedIn

the AI Agent performs everything autonomously.

🎯 Key Features
✅ Autonomous Topic Selection
✅ AI-powered LinkedIn Post Generation
✅ Dynamic Hashtag Generation
✅ Markdown Cleanup & Formatting
✅ Branded Image Generation
✅ LinkedIn Image Upload Pipeline
✅ Image + Text Publishing
✅ LangGraph Agent Workflow
✅ FastAPI REST Backend
✅ PostgreSQL Persistence
✅ Async Background Processing
✅ Production Logging & Error Handling
🏗 High-Level Architecture
                    User Request
                          │
                          ▼
                  FastAPI REST API
                          │
                          ▼
               Background Async Task
                          │
                          ▼
                   LangGraph Agent
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
 Topic Selection     Web Research      Memory Retrieval
        │                 │                  │
        └─────────────────┼──────────────────┘
                          ▼
               AI Content Generation
                          │
                          ▼
            Markdown Cleanup & Validation
                          │
                          ▼
          LinkedIn Image Generation Agent
                          │
                          ▼
         Render Final Image Template (PIL)
                          │
                          ▼
            Save Image to Local Storage
                          │
                          ▼
         LinkedIn initializeUpload API
                          │
                          ▼
        Upload Binary Image to LinkedIn
                          │
                          ▼
           Build LinkedIn Post Payload
                          │
                          ▼
           LinkedIn REST Posts API
                          │
                          ▼
            LinkedIn Feed Published
⚙ Technology Stack
Backend
Python 3.12+
FastAPI
SQLAlchemy
Alembic
PostgreSQL
Pydantic
AI
LangGraph
LangChain
Google Gemini 2.5 Flash
Ollama (Gemma 3:4B Fallback)
Image Processing
Pillow (PIL)
Custom LinkedIn Templates
APIs
LinkedIn REST API
LinkedIn Images API
LinkedIn Posts API
Authentication
LinkedIn OAuth 2.0
🔄 End-to-End Workflow
Step 1

Receive request

POST /api/v1/posts/generate
Step 2

Create new Post record

Status:

PENDING
Step 3

Run Background Task

run_agent(post_id)
Step 4

Load LangGraph Workflow

The AI Agent starts executing.

Step 5

Select Topic

Agent can

Generate topic automatically

or

Use user supplied topic
Step 6

Research

Collect context

Generate knowledge

Prepare references

Step 7

Generate LinkedIn Content

Gemini generates

Hook
Body
CTA
Hashtags
Step 8

Content Cleanup

Remove

Markdown
Invalid characters
Code blocks

Ensure

LinkedIn compliant
Step 9

Validate Length

LinkedIn limit

4000 Characters

Automatically truncate if necessary.

Step 10

Generate Image Prompt

Convert content into

Professional LinkedIn image prompt.

Step 11

Generate Image

Use

linkedin_template.png

Render

Title
Subtitle
Branding
Footer
Step 12

Store Image

Example

assets/generated_images/post_15.png
Step 13

LinkedIn Image Upload

13.1

Initialize Upload

POST /rest/images?action=initializeUpload

Returns

uploadUrl

imageURN
13.2

Upload Binary

PUT uploadUrl
13.3

Create Payload

{
  "author":"urn:li:person:xxxx",
  "commentary":"Generated Content",
  "content":{
      "media":{
          "id":"urn:li:image:xxxxx"
      }
  }
}
13.4

Publish

POST /rest/posts
Step 14

LinkedIn Feed Updated

Image

Text

Published Successfully

Step 15

Update Database

Status

SUCCESS

Store

LinkedIn Post ID
Image URN
Timestamp
🧠 LangGraph Workflow
START

↓

Topic Selection

↓

Research

↓

Generate Content

↓

Clean Content

↓

Generate Image

↓

Upload Image

↓

Publish Post

↓

Update Database

↓

END
🖼 LinkedIn Image Upload Pipeline
Generate Image

↓

Save PNG

↓

Initialize Upload

↓

Receive Upload URL

↓

Upload Binary

↓

Receive Image URN

↓

Create Post Payload

↓

Publish Post

📂 Project Structure
LinkedIn_Post_Agent/

│
├── app/
│   ├── api/
│   ├── graph/
│   ├── services/
│   ├── database/
│   ├── repository/
│   ├── models/
│   ├── prompts/
│   ├── utils/
│   ├── config/
│   └── core/
│
├── assets/
│   ├── templates/
│   └── generated_images/
│
├── alembic/
├── tests/
├── scripts/
├── docs/
├── requirements.txt
└── README.md
🔐 Environment Variables
DATABASE_URL=

GEMINI_API_KEY=

OLLAMA_BASE_URL=

LINKEDIN_CLIENT_ID=

LINKEDIN_CLIENT_SECRET=

LINKEDIN_ACCESS_TOKEN=

LINKEDIN_PERSON_URN=

LINKEDIN_API_VERSION=

LOG_LEVEL=
🚀 Future Roadmap
Multi-Agent Architecture
Scheduled LinkedIn Posting
AI Trend Detection
Auto Comment Generation
Engagement Analytics
Carousel Posts
Video Upload Support
Multi-language Content
Team Collaboration
Human Approval Workflow
RAG-based Knowledge Base
Vector Database Integration
Redis Caching
Docker & Kubernetes Deployment
CI/CD with GitHub Actions
Observability (OpenTelemetry, Prometheus, Grafana)
⭐ Production Highlights
LangGraph-based autonomous workflow
Async processing with FastAPI
Production-ready LinkedIn REST integration
Image + text publishing support
Gemini primary LLM with Ollama fallback
Modular service architecture
PostgreSQL persistence
Comprehensive logging and diagnostics
Enterprise-friendly, extensible design
Ready for cloud deployment and future multi-agent expansion

This structure will make your repository look polished and understandable for recruiters, hiring managers, and developers exploring your project.





You should be proud of this milestone
Over the course of this debugging session, you:

Collected evidence instead of guessing.

Fixed a real async bug.

Verified the upload pipeline with runtime logs.

Narrowed the problem to a single stage.

Confirmed the correct production workflow with a successful 201 Created.

That's exactly how complex integrations are debugged in production environments.

Congratulations on getting your LangGraph-powered LinkedIn Image Posting Agent working end to end!
