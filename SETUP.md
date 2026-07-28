# LinkedIn Post Agent - Complete Setup Guide

Welcome! This guide will walk you through setting up the LinkedIn Post Agent from scratch—locally and in production—in approximately 15 minutes.

**Table of Contents**
- [Prerequisites](#prerequisites)
- [Local Repository & Environment Setup](#local-repository--environment-setup)
- [Supabase Database Setup](#supabase-database-setup)
- [Environment Configuration](#environment-configuration)
- [Database Migrations via Alembic](#database-migrations-via-alembic)
- [Running the Application Locally](#running-the-application-locally)
- [Production Deployment (Render)](#production-deployment-render)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed and ready:

### System Requirements
- **Python 3.12+** (verify with `python --version`)
  - Download from [python.org](https://www.python.org/downloads/)
  - On Windows, ensure "Add Python to PATH" is checked during installation
- **Git** (verify with `git --version`)
  - Download from [git-scm.com](https://git-scm.com/)
- **PostgreSQL Client Tools** (optional, for manual database inspection)
  - On Windows: Download from [postgresql.org/download](https://www.postgresql.org/download/windows/)
  - On macOS: `brew install postgresql`
  - On Linux: `sudo apt-get install postgresql-client`

### Third-Party Accounts & API Keys
You'll need to create/obtain the following before completing setup:

1. **Supabase Account** (Free tier available)
   - Sign up at [supabase.com](https://supabase.com/)
   - Create a new project (select PostgreSQL 15+)
   - Note your project URL and anon key from the dashboard

2. **Google Gemini API Key** (Free tier: 60 requests/minute)
   - Visit [Google AI Studio](https://ai.google.dev/)
   - Click "Get API Key" and create a key for your project
   - Copy the API key (you'll need it in `.env`)

3. **LangSmith API Key** (Optional but recommended for observability)
   - Sign up at [smith.langchain.com](https://smith.langchain.com/)
   - Create an API key from the dashboard
   - This enables tracing, debugging, and monitoring of LLM calls

4. **LinkedIn OAuth Credentials** (For production posting)
   - Register your app at [LinkedIn Developers](https://www.linkedin.com/developers/)
   - Create a new app and get `CLIENT_ID` and `CLIENT_SECRET`
   - Obtain a `LINKEDIN_ACCESS_TOKEN` via OAuth flow or manually via LinkedIn app settings
   - Find your LinkedIn Person URN from your profile URL

5. **Ollama** (Optional, for fallback LLM)
   - Download from [ollama.ai](https://ollama.ai/)
   - After installation, run: `ollama pull gemma3:4b` (in separate terminal)

---

## Local Repository & Environment Setup

### Step 1: Clone the Repository

Open your terminal (PowerShell on Windows, Terminal on macOS/Linux) and run:

```bash
git clone https://github.com/yourusername/linkedin-post-agent.git
cd linkedin-post-agent
```

Replace `yourusername` with the actual GitHub username.

### Step 2: Create a Python Virtual Environment

Creating a virtual environment isolates this project's dependencies from your system Python.

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you encounter an execution policy error, run:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then retry the activation command above.

**On macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` appear at the start of your terminal prompt, indicating the virtual environment is active.

### Step 3: Upgrade pip and Install Dependencies

Ensure pip is up-to-date:

```bash
pip install --upgrade pip
```

Install all project dependencies:

```bash
pip install -r requirements.txt
```

This will install:
- **FastAPI & Uvicorn** (web framework & server)
- **SQLAlchemy 2.0 & Alembic** (ORM & database migrations)
- **psycopg 3** (PostgreSQL async driver)
- **LangChain 0.3, LangGraph, LangSmith** (AI orchestration & tracing)
- **Pydantic** (data validation)
- **All other dependencies** listed in `requirements.txt`

**Verify Installation:**
```bash
pip list | grep -E "fastapi|sqlalchemy|langchain|langgraph"
```

You should see entries for FastAPI, SQLAlchemy, LangChain, and LangGraph.

---

## Supabase Database Setup

### Step 1: Create a Supabase Project

1. Log in to [supabase.com](https://supabase.com/)
2. Click **"New Project"**
3. Fill in:
   - **Name:** `linkedin-agent-db` (or your preferred name)
   - **Database Password:** Generate a strong password and save it securely
   - **Region:** Choose a region closest to your deployment location
4. Click **"Create new project"** and wait ~2 minutes for provisioning

### Step 2: Obtain the PostgreSQL Connection String

1. In your Supabase project dashboard, navigate to **Settings** → **Database**
2. Under **Connection string**, you'll see two options:
   - **Session pooler** (for web frameworks, short-lived connections)
   - **Transaction pooler** (for serverless, transaction-scoped connections)

   **For this project, use the Session pooler URL** (it's the default and works best with SQLAlchemy + psycopg v3)

3. Copy the connection string. It will look like:
   ```
   postgresql://postgres.xxxxx:password@db.xxxxx.supabase.co:5432/postgres
   ```

4. **Important:** Replace `[YOUR-PASSWORD]` in the URL with your actual database password (the one you set during project creation)

5. **For async support with psycopg v3**, modify the URL to:
   ```
   postgresql+psycopg_async://postgres.xxxxx:password@db.xxxxx.supabase.co:5432/postgres
   ```

   Replace `postgresql://` with `postgresql+psycopg_async://` (note the underscore in `psycopg_async`)

### Step 3: Enable Required PostgreSQL Extensions

Some database migrations may require extensions like `pgvector` (for embeddings) or `uuid-ossp`. Enable them preemptively:

1. In Supabase, navigate to **SQL Editor**
2. Click **"New Query"**
3. Paste and run the following SQL:
   ```sql
   -- Enable required extensions
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pgvector";
   
   -- Verify they're installed
   SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgvector');
   ```
4. You should see both extensions listed in the results

### Step 4: Verify the Connection Locally

Before moving forward, test that your local environment can connect to Supabase:

```bash
python -c "
from sqlalchemy import create_engine, text
url = 'YOUR_DATABASE_URL_HERE'  # Paste your async connection string
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✅ Connection successful:', result.fetchone())
"
```

Replace `YOUR_DATABASE_URL_HERE` with your actual connection string.

**Expected output:**
```
✅ Connection successful: (1,)
```

If you see an error:
- **SSL verification failed:** Add `?sslmode=require` to the end of your connection URL
- **Authentication failed:** Verify the password in your connection string matches your database password
- **Connection refused:** Verify Supabase project is running and region is correct

---

## Environment Configuration

### Step 1: Create `.env` File

Copy the `.env.example` template (if it exists) or create a new `.env` file in the project root:

```bash
# On Windows (PowerShell)
Copy-Item ".env.example" ".env"

# On macOS/Linux
cp .env.example .env
```

If `.env.example` doesn't exist, create `.env` manually:

```bash
touch .env  # macOS/Linux
# or
New-Item -ItemType File -Name ".env"  # Windows PowerShell
```

### Step 2: Populate Environment Variables

Edit the `.env` file with your actual credentials. Here's a complete template with all required variables:

```env
################################
# FastAPI & Server Configuration
################################
PROJECT_NAME=LinkedIn AI Agent
PORT=8000

################################
# Database Configuration
################################
# CRITICAL: Use postgresql+psycopg_async:// for async SQLAlchemy + psycopg v3
# Replace password, host, and port with your Supabase credentials
DATABASE_URL=postgresql+psycopg_async://postgres.xxxxxx:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres?sslmode=require

################################
# Supabase (Optional, for auth)
################################
SUPABASE_URL=https://xxxxxx.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here

################################
# LLM Configuration (Primary)
################################
# Google Gemini API Key (free tier: 60 requests/minute)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-3.5-flash

################################
# LLM Fallback Configuration (Ollama)
################################
# Only needed if running Ollama locally
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=gemma3:4b

################################
# LangSmith Observability
################################
# Recommended for debugging and monitoring LLM calls
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=linkedin-content-agent

################################
# LinkedIn OAuth & Publishing
################################
# Obtain from LinkedIn Developer Console
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_ACCESS_TOKEN=your_access_token_here
LINKEDIN_PERSON_URN=urn:li:person:xxxxxxxxxxxxx

# LinkedIn API Configuration
LINKEDIN_API_VERSION=v2
LINKEDIN_MAX_RETRIES=3
LINKEDIN_RETRY_BACKOFF=2.0
LINKEDIN_POSTS_PER_DAY=100

################################
# Image Rendering Configuration (Branding)
################################
PROFILE_NAME=Your Name
PROFILE_ROLE=Your Role (e.g., Gen AI Engineer)
TEMPLATE_IMAGE_PATH=assets/branding/linkedin_template.png
FONTS_PATH=assets/fonts/
IMAGE_BRAND_COLOR=#0077B5

################################
# Concurrency & Rate Limiting
################################
MAX_CONCURRENT_LLM_CALLS=2

################################
# Logging
################################
LOG_LEVEL=INFO

################################
# Redis (Optional, for background tasks)
################################
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### Step 3: Verify Environment Variables Are Loaded

Test that your `.env` file is correctly loaded:

```bash
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
print('✅ DATABASE_URL:', os.getenv('DATABASE_URL')[:50] + '...' if os.getenv('DATABASE_URL') else '❌ Not set')
print('✅ GEMINI_API_KEY:', 'Set' if os.getenv('GEMINI_API_KEY') else '❌ Not set')
print('✅ LANGCHAIN_API_KEY:', 'Set' if os.getenv('LANGCHAIN_API_KEY') else '❌ Not set')
"
```

You should see "✅ Set" for critical variables. If you see "❌ Not set", revisit your `.env` file.

---

## Database Migrations via Alembic

Alembic manages your database schema changes. You must run migrations to create the required tables.

### Step 1: Verify Migration Files

List all migration files:

```bash
ls -la alembic/versions/  # macOS/Linux
Get-ChildItem alembic/versions/  # Windows PowerShell
```

You should see files like:
- `001_init_init_supabase_schema.py`
- `002_add_missing_post_columns.py`
- etc.

### Step 2: Configure Alembic for Your Database

1. Open `alembic/env.py`
2. Locate the `sqlalchemy.url` configuration (around line 25–30)
3. Ensure it reads your `DATABASE_URL` from environment:
   ```python
   from app.core.config import settings
   config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
   ```
4. Save the file

### Step 3: Run Migrations Against Supabase

Execute all pending migrations:

```bash
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade ... -> 001_init_init_supabase_schema.py
INFO  [alembic.runtime.migration] Running upgrade 001... -> 002_add_missing_post_columns.py
...
INFO  [alembic.runtime.migration] Done.
```

### Step 4: Verify Tables Were Created

Check that tables exist in Supabase:

```bash
python -c "
from sqlalchemy import create_engine, inspect, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print('✅ Tables in database:', tables)
"
```

You should see: `['users', 'posts', ...]`

**Troubleshooting Migration Issues:**

If you encounter errors:

1. **Connection Error:** Verify `DATABASE_URL` is correct and Supabase is running
   ```bash
   python -c "from app.core.config import settings; print(settings.DATABASE_URL)"
   ```

2. **Permission Denied:** Ensure your database user has CREATE TABLE privileges (usually does by default on Supabase)

3. **Table Already Exists:** If a table already exists from a prior run, Alembic skips it. This is safe.

4. **Rollback a Migration (if needed):**
   ```bash
   alembic downgrade -1  # Rolls back 1 migration
   alembic downgrade base  # Rolls back all migrations
   ```

---

## Running the Application Locally

### Step 1: Start the FastAPI Server

Ensure your virtual environment is active (you should see `(.venv)` in your terminal prompt).

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Parameters explained:**
- `app.api.main:app` — Points to the FastAPI app instance in `app/api/main.py`
- `--host 0.0.0.0` — Listen on all network interfaces
- `--port 8000` — Run on localhost:8000
- `--reload` — Auto-restart on code changes (development only)

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
[OK] Database initialized
```

### Step 2: Test the Health Endpoint

In a new terminal (keeping the Uvicorn server running), test the health endpoint:

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "ok",
  "database": "supabase",
  "agent": "langgraph"
}
```

### Step 3: Explore the API Documentation

Open your browser and visit:

```
http://localhost:8000/docs
```

This opens the interactive **Swagger UI** where you can:
- View all endpoints
- Test API calls directly
- See request/response schemas

### Step 4: Test a Simple Request (Optional)

To generate a LinkedIn post, make a POST request:

```bash
curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "topic": "Distributed Systems"
  }'
```

**Expected response:**
```json
{
  "post_id": 1,
  "topic": "Distributed Systems",
  "status": "queued",
  "created_at": "2026-07-27T10:30:00Z"
}
```

### Step 5: Stop the Server

Press `Ctrl+C` in the terminal running Uvicorn.

---

## Production Deployment (Render)

Render is a cloud platform that auto-deploys your app when you push to GitHub.

### Step 1: Push Your Repository to GitHub

If you haven't already, push your code to GitHub:

```bash
git add .
git commit -m "Initial commit: LinkedIn Post Agent setup"
git push -u origin main
```

### Step 2: Create a Render Account

1. Go to [render.com](https://render.com/)
2. Click **"Sign Up"** and authenticate with GitHub
3. Grant Render permission to access your GitHub repositories

### Step 3: Create a New Web Service

1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Select your `linkedin-post-agent` repository
3. Fill in the configuration:
   - **Name:** `linkedin-post-agent`
   - **Environment:** `Python 3`
   - **Region:** Choose closest to your users
   - **Branch:** `main`
   - **Build Command:**
     ```
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```
     alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** `Standard` (free tier available)

### Step 4: Set Environment Variables on Render

1. In the Render web service settings, scroll to **"Environment"**
2. Add each variable from your `.env` file:
   - Click **"Add Environment Variable"** for each entry
   - Copy from your local `.env` file

   **Critical variables:**
   - `DATABASE_URL` (use your Supabase connection string)
   - `GEMINI_API_KEY`
   - `LANGCHAIN_API_KEY`
   - `LINKEDIN_ACCESS_TOKEN`
   - `LINKEDIN_PERSON_URN`
   - (and all others from your `.env`)

3. Click **"Save"**

### Step 5: Deploy

1. Scroll down and click **"Create Web Service"**
2. Render will immediately start building and deploying
3. Watch the logs in real-time:
   - **Build logs** show pip installations
   - **Deployment logs** show server startup
   - **Runtime logs** show API requests

**Expected output (in logs):**
```
[OK] Database initialized
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Access Your Deployed App

1. Once deployment completes, Render provides a URL: `https://linkedin-post-agent.onrender.com`
2. Test the health endpoint:
   ```
   https://linkedin-post-agent.onrender.com/health
   ```
3. Access Swagger UI:
   ```
   https://linkedin-post-agent.onrender.com/docs
   ```

### Step 7: Enable Auto-Deploy on Git Push

By default, Render redeploys on every push to `main`. To verify:

1. In Render web service settings, check **"Auto-Deploy"** is enabled
2. On each `git push origin main`, Render automatically rebuilds and redeploys

---

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'fastapi'`

**Solution:** Ensure your virtual environment is activated:
```bash
# Windows
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Then reinstall dependencies:
```bash
pip install -r requirements.txt
```

---

### Issue: `psycopg3 version conflict` or `connection refused`

**Solution:** Verify your `DATABASE_URL` uses the correct async driver:
```
postgresql+psycopg_async://...
```
(not `postgresql+asyncpg://` or plain `postgresql://`)

Test the connection:
```bash
python -c "
from sqlalchemy import create_engine
from app.core.config import settings
engine = create_engine(settings.DATABASE_URL)
print('✅ Connection successful' if engine else '❌ Failed')
"
```

---

### Issue: `alembic upgrade head` hangs or times out

**Solution:** This usually indicates a network issue with Supabase. Try:

1. **Check Supabase is running:**
   - Log in to Supabase dashboard
   - Verify project status is "Active"

2. **Increase timeout:**
   ```bash
   # Set a longer timeout (in seconds)
   PGCONNECT_TIMEOUT=30 alembic upgrade head
   ```

3. **Verify credentials:**
   ```bash
   python -c "from app.core.config import settings; print(settings.DATABASE_URL[:60])"
   ```

4. **Manually test SQL connection:**
   ```bash
   python -c "
   from sqlalchemy import create_engine, text
   from app.core.config import settings
   engine = create_engine(settings.DATABASE_URL)
   with engine.connect() as conn:
       result = conn.execute(text('SELECT 1'))
       print('✅ Connected')
   "
   ```

---

### Issue: `GEMINI_API_KEY not found` at runtime

**Solution:** Verify your `.env` file exists in the project root:
```bash
ls -la .env  # macOS/Linux
Get-ChildItem .env  # Windows
```

If it doesn't exist, create it following the [Environment Configuration](#environment-configuration) section.

Ensure Pydantic is loading environment variables:
```bash
python -c "
from dotenv import load_dotenv
from app.core.config import settings
load_dotenv()
print('GEMINI_API_KEY:', '✅ Loaded' if settings.GEMINI_API_KEY else '❌ Not set')
"
```

---

### Issue: Render deployment fails with `Build failed`

**Solution:** Check the build logs in Render:

1. Click **"Logs"** in your Render web service
2. Look for errors like:
   - `pip install failed` → Verify all dependencies in `requirements.txt` are available
   - `Python 3.12 not available` → Change **Instance Type** to ensure Python 3.12+ is used
   - `DATABASE_URL not found` → Add environment variables to Render dashboard

3. **Redeploy manually:**
   - In Render dashboard, click **"Manual Deploy"** → **"Deploy latest commit"**

---

### Issue: LinkedIn posts fail to publish

**Solution:**

1. **Verify credentials in `.env`:**
   ```bash
   python -c "
   from app.core.config import settings
   print('LINKEDIN_ACCESS_TOKEN:', '✅' if settings.LINKEDIN_ACCESS_TOKEN else '❌ Missing')
   print('LINKEDIN_PERSON_URN:', '✅' if settings.LINKEDIN_PERSON_URN else '❌ Missing')
   "
   ```

2. **Check token expiration:**
   - LinkedIn access tokens expire after a period
   - Refresh via LinkedIn OAuth flow or manual token generation

3. **Review LangSmith logs:**
   - If `LANGCHAIN_API_KEY` is set, view traces at [smith.langchain.com](https://smith.langchain.com/)
   - Filter by project `linkedin-content-agent` to see detailed error messages

---

## Next Steps

Once you've completed this setup:

1. **Test Locally:** Generate a few posts locally using the Swagger UI at `http://localhost:8000/docs`
2. **Deploy:** Push to GitHub to trigger Render deployment
3. **Monitor:** Check LangSmith (if enabled) for LLM call traces
4. **Configure Scheduling:** Set up scheduled posts via a cron job or task scheduler
5. **Scale:** Monitor Render logs for performance; upgrade instance type if needed

---

## Support & Resources

- **FastAPI Docs:** [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- **SQLAlchemy Docs:** [sqlalchemy.org](https://docs.sqlalchemy.org/)
- **LangChain Docs:** [python.langchain.com](https://python.langchain.com/)
- **LangGraph Docs:** [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/)
- **Supabase Docs:** [supabase.com/docs](https://supabase.com/docs)
- **Render Docs:** [render.com/docs](https://render.com/docs)

---

**You're all set!** Your LinkedIn Post Agent is ready to generate and publish high-engagement technical content. 🚀
