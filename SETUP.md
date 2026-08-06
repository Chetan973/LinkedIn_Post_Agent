# LinkedIn Post Agent — Complete Setup Guide

End-to-end setup for a fresh machine, plus the exact steps to move the agent
onto a different LinkedIn account (Pranav Kumar).

Everything in this guide was verified against the code in this repo, not
written from memory. Where a step matters, the file that enforces it is named.

**Contents**

1. [What this app actually does](#1-what-this-app-actually-does)
2. [Prerequisites](#2-prerequisites)
3. [Local install](#3-local-install)
4. [Environment variables that matter](#4-environment-variables-that-matter)
5. [Supabase database](#5-supabase-database)
6. [Getting a LinkedIn access token](#6-getting-a-linkedin-access-token)
7. [Getting the LinkedIn Person URN](#7-getting-the-linkedin-person-urn)
8. [Seeding the user row (required)](#8-seeding-the-user-row-required)
9. [Run and verify locally](#9-run-and-verify-locally)
10. [Switching the agent to Pranav Kumar](#10-switching-the-agent-to-pranav-kumar)
11. [Render.com deployment](#11-rendercom-deployment)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What this app actually does

A FastAPI service wrapping a LangGraph agent. One HTTP call publishes one
LinkedIn post, fully autonomously.

```
POST /api/v1/posts/generate
        │
        ├─ creates a `posts` row (status = queued)
        └─ FastAPI BackgroundTask → run_agent(post_id)
                │
                ├─ select_topic      pick from 14 whitelisted domains,
                │                    dedup against recent posts   (topic_selection.py)
                ├─ draft             180–260 word post body       (draft.py)
                ├─ generate_thought  8–12 word line for the image (thought_generation.py)
                ├─ validate          length / formatting checks   (validation.py)
                ├─ render_image      PIL draws thought onto the
                │                    per-URN branding template     (image_rendering.py)
                └─ publish           upload image → POST /rest/posts
                                     (falls back to text-only on image failure)
```

- **LLM chain:** Gemini `gemini-3.5-flash` primary → Groq `llama-3.1-8b-instant`
  fallback (`app/services/llm_fallback.py`). There is **no** OpenAI or Ollama call
  anywhere despite what old `.env` keys suggested.
- **State:** LangGraph checkpoints into the same Postgres (`checkpoints*` tables).
- **Schedule:** a Render cron job hits the endpoint Mon/Wed/Fri 09:00 UTC
  (`render.yaml` → `scripts/scheduled_post.py`). The schedule is dumb; topic
  choice and weekly domain diversity live in the agent.

### Which LinkedIn account gets posted to

This is the single most important thing to understand before switching accounts:

> Publishing uses **`LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN` from the
> environment** — not the token stored on the logged-in database user.

See `app/api/routers/posts.py` and `app/services/linkedin.py`. The Supabase
OAuth login flow exists and stores tokens in `users`, but the publish path does
not read them. So **changing the account = changing those two env vars.**

The database user matters for a different reason — see [section 8](#8-seeding-the-user-row-required).

---

## 2. Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11 or 3.12** | Render pins 3.11.9; local dev here is 3.12.10. Do not use 3.13 — `psycopg 3.2.3` and `langgraph 0.5.4` are pinned against older ABIs. |
| **Git** | `git --version` |
| **Supabase project** | Free tier is fine. Postgres 15+. |
| **Google Gemini API key** | https://aistudio.google.com/apikey |
| **Groq API key** | https://console.groq.com/keys |
| **LinkedIn Developer app** | https://www.linkedin.com/developers/apps — must be verified against a Company Page |

You do **not** need Redis, Celery, Ollama, or an OpenAI key. Ignore any older
docs that mention them.

---

## 3. Local install

```powershell
git clone <repo-url> LinkedIn_Post_Agent
cd LinkedIn_Post_Agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux equivalent:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
```

Verify:

```powershell
python -c "import fastapi, sqlalchemy, langgraph, psycopg, PIL; print('deps ok')"
```

> **Windows note:** `app/api/main.py` already switches asyncio to
> `WindowsSelectorEventLoopPolicy`, because psycopg3 cannot run on the default
> Proactor loop. Any standalone script you write that touches the DB on Windows
> must do the same.

---

## 4. Environment variables that matter

Copy the template and edit it:

```powershell
Copy-Item .env.example .env
```

The `.env` in this repo is annotated: every key is tagged `[USED]` or commented
out with the reason it is dead. Short version:

### Required — the app will not work without these

| Key | Purpose | Read by |
|---|---|---|
| `DATABASE_URL` | Supabase Postgres. **Must** keep the `postgresql+psycopg_async://` prefix. Quote it if the password has `$ @ #`. | `app/db/database.py` |
| `GEMINI_API_KEY` | Primary LLM | `llm_fallback.py` |
| `GROQ_API_KEY` | Fallback LLM | `llm_fallback.py` |
| `LINKEDIN_ACCESS_TOKEN` | Publishes the post | `linkedin.py`, `posts.py` |
| `LINKEDIN_PERSON_URN` | Post author + picks the branding template | `posts.py`, `image_rendering.py` |
| `LINKEDIN_USER_EMAIL` | Looked up in `users.email` to attach the post to a user row | `app/api/auth.py` |

### Required only for the browser OAuth login flow

`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`,
`OAUTH_REDIRECT_URI`, `SUPABASE_LINKEDIN_OIDC_PROVIDER`.

Posting works without these. They only power `/api/v1/auth/linkedin/login`.

### Branding

| Key | Purpose |
|---|---|
| `CHETAN_PERSON_URN` | maps to `assets/branding/linkedin_template.png` — **blank** template, renderer draws name + role + badge + thought |
| `PRANAV_PERSON_URN` | maps to `assets/branding/Pranav_Linkedin_Template.jpeg` — **prebranded**, renderer draws only the thought |
| `PRANAV_THOUGHT_TOP_Y` | y-coord where the thought starts on the prebranded template (default `545`) |
| `PROFILE_NAME` / `PROFILE_ROLE` | fallback identity, drawn **only** when the poster's URN is unregistered |
| `FONTS_PATH` | `assets/fonts/` — must contain `Inter_18pt-SemiBold.ttf` |

An empty URN is skipped at startup with a warning; that user falls back to the
blank template. Mapping lives in `app/branding/config.py`.

### Keys you may see but that do nothing

`OPENAI_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`, `CELERY_*`,
`LOG_LEVEL`, `TEMPLATE_IMAGE_PATH`, `IMAGE_BRAND_COLOR`, `LINKEDIN_API_VERSION`,
`LINKEDIN_POSTS_PER_DAY`, `TOKEN_REFRESH_*`, `SUPABASE_SERVICE_ROLE_KEY`.

Two of these deserve a callout:

- **`LANGCHAIN_*` (LangSmith tracing) is inert.** The LangSmith SDK reads
  `os.environ`, but this app never calls `load_dotenv()` — pydantic-settings
  keeps values on the `settings` object without exporting them to the process
  environment, and `render.yaml` does not define them either. Tracing has been
  silently off everywhere. To actually enable it, set them as **real** shell or
  Render environment variables, not in `.env`.
- **`LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` are never read at runtime.**
  The login flow is delegated to Supabase GoTrue, which stores its own copy.
  You still need them to mint an access token by hand (section 6), so they are
  kept in `.env` as reference.

Sanity-check what actually loaded:

```powershell
python -c "from app.core.config import settings; print(settings.DATABASE_URL.split('@')[-1]); print('gemini:', bool(settings.GEMINI_API_KEY), '| groq:', bool(settings.GROQ_API_KEY)); print('urn:', settings.LINKEDIN_PERSON_URN); print('user email:', settings.LINKEDIN_USER_EMAIL)"
```

---

## 5. Supabase database

### Option A — reuse the existing project (recommended)

The live project is `buubdwydkzjuetybicby`. Its schema is already at head. If
Pranav's machine points `DATABASE_URL` at it, nothing else is needed — skip to
section 6. Both accounts can share it; posts are separated by `user_id`.

### Option B — a fresh Supabase project

1. supabase.com → **New Project**. Save the DB password.
2. **Settings → Database → Connection string → Session pooler**. Copy it.
3. Rewrite the scheme for async psycopg 3:
   ```
   postgresql://...        →   postgresql+psycopg_async://...
   ```
   Quote the whole value in `.env` if the password contains `$`, `@` or `#`.
4. Run the migrations:
   ```powershell
   alembic upgrade head
   ```
   `alembic/env.py` calls `load_dotenv()` and reads `DATABASE_URL` directly, so
   no extra config is needed.

### Expected schema

After `alembic upgrade head` the public schema holds:

```
alembic_version        current revision: 009_add_linkedin_provider_tokens
users                  user_id, email (unique), full_name, linkedin_profile_url,
                       access_token, refresh_token, token_expires_at,
                       linkedin_access_token, linkedin_person_urn, timestamps
posts                  post_id, user_id → users, topic, draft_content,
                       final_content, ai_thought, status, idempotency_key,
                       linkedin_post_id, published_at, image_url, asset_urn,
                       char_count, category, llm_used, llm_fallback_used,
                       tokens_used, execution_time_ms, error_reason, timestamps
checkpoints            LangGraph state, auto-created on first agent run
checkpoint_blobs
checkpoint_writes
checkpoint_migrations
```

`status` is a plain varchar holding `queued` / `published` / `failed`
(`PostStatus` in `app/db/models.py`).

Verify:

```powershell
python -c "import psycopg,os; from dotenv import load_dotenv; load_dotenv(); u=os.getenv('DATABASE_URL').strip('\"').replace('postgresql+psycopg_async://','postgresql://'); c=psycopg.connect(u,connect_timeout=20); cur=c.cursor(); cur.execute(\"select table_name from information_schema.tables where table_schema='public' order by 1\"); print([r[0] for r in cur.fetchall()])"
```

> **Note:** `app/api/main.py` also calls `Base.metadata.create_all()` on startup,
> so tables appear even if you forget Alembic. Still run Alembic — `create_all`
> does not apply column-level migrations to existing tables.

---

## 6. Getting a LinkedIn access token

This is the token that publishes posts. It is a **member** token with a
**2-month** lifetime (5,184,000 s, as shown on the app's Auth tab), so it must
be regenerated roughly every 60 days.

### 6.1 Prepare the LinkedIn app

Go to https://www.linkedin.com/developers/apps → your app.

**Products tab** — request and wait for approval on:

| Product | Grants scopes |
|---|---|
| **Sign In with LinkedIn using OpenID Connect** | `openid`, `profile`, `email` — needed to read the Person URN |
| **Share on LinkedIn** | `w_member_social` — needed to publish |

Approval for these two is usually instant. Without `w_member_social` every
publish returns `403 ACCESS_DENIED`.

**Auth tab → Authorized redirect URLs** — must contain, exactly:

```
https://www.linkedin.com/developers/tools/oauth/redirect      ← required by the token generator
https://<your-supabase-ref>.supabase.co/auth/v1/callback      ← Supabase OIDC login
https://<your-render-app>.onrender.com/api/v1/auth/linkedin/callback
http://localhost:8000/api/v1/auth/linkedin/callback           ← add this for local login testing
```

The first entry is the one people forget; the OAuth 2.0 token generator will not
work without it.

Also on the Auth tab: copy the **Client ID** and **Primary Client Secret**.

> If two client secrets are active ("Multiple client secret keys have been active
> since …"), delete the unused one. A rotated-but-not-deleted secret is a common
> cause of intermittent `invalid_client` errors.

### 6.2 Generate the token (easiest path)

1. **Auth tab → OAuth 2.0 tools → Create token** (or go to
   https://www.linkedin.com/developers/tools/oauth/token-generator).
2. Select your app.
3. Tick the scopes: `openid`, `profile`, `email`, `w_member_social`.
4. Click **Request access token** → sign in as the account that will post →
   **Allow**.
5. Copy the `access_token` string. It is long (~500 chars) and starts with `AQ`.

Paste it into `.env`:

```env
LINKEDIN_ACCESS_TOKEN=AQV...
```

### 6.3 Manual OAuth flow (alternative)

If the generator is unavailable:

**Step 1** — open this in a browser (one line, URL-encoded redirect):

```
https://www.linkedin.com/oauth/v2/authorization
  ?response_type=code
  &client_id=<LINKEDIN_CLIENT_ID>
  &redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Flinkedin%2Fcallback
  &scope=openid%20profile%20email%20w_member_social
  &state=random123
```

Approve, then copy the `code=` value from the URL you land on.

**Step 2** — exchange it (PowerShell):

```powershell
$body = @{
  grant_type    = 'authorization_code'
  code          = '<PASTE_CODE>'
  redirect_uri  = 'http://localhost:8000/api/v1/auth/linkedin/callback'
  client_id     = '<LINKEDIN_CLIENT_ID>'
  client_secret = '<LINKEDIN_CLIENT_SECRET>'
}
Invoke-RestMethod -Method Post -Uri 'https://www.linkedin.com/oauth/v2/accessToken' -Body $body
```

The `access_token` field of the response is what you want. The `code` is
single-use and expires in ~30 seconds — if you get `invalid_grant`, redo step 1.

### 6.4 Verify the token works

```powershell
$t = '<ACCESS_TOKEN>'
Invoke-RestMethod -Uri 'https://api.linkedin.com/v2/userinfo' -Headers @{ Authorization = "Bearer $t" }
```

A JSON body with `sub`, `name`, `email` means the token is live.
`401` means expired or malformed; `403` means a missing scope.

---

## 7. Getting the LinkedIn Person URN

The URN is derived from the token — it is **not** the vanity slug in your
profile URL.

```powershell
$t = '<ACCESS_TOKEN>'
$me = Invoke-RestMethod -Uri 'https://api.linkedin.com/v2/userinfo' -Headers @{ Authorization = "Bearer $t" }
$me | ConvertTo-Json
"urn:li:person:$($me.sub)"
```

curl equivalent:

```bash
curl -s -H "Authorization: Bearer $T" https://api.linkedin.com/v2/userinfo
```

Response:

```json
{
  "sub": "qd_C3vqY6T",
  "name": "…",
  "given_name": "…",
  "family_name": "…",
  "email": "…"
}
```

Take `sub` and prefix it:

```env
LINKEDIN_PERSON_URN=urn:li:person:qd_C3vqY6T
```

The `urn:li:person:` prefix is required. `posts.py` will prepend it if missing,
but `app/branding/config.py` rejects any URN without it — so a bare `sub` value
silently loses the branding template. Always store the full form.

> `/v2/me` is the older endpoint and needs the legacy `r_liteprofile` scope,
> which is no longer granted to new apps. Use `/v2/userinfo`.

---

## 8. Seeding the user row (required)

`POST /api/v1/posts/generate` inserts `posts.user_id = current_user.user_id`,
and `posts.user_id` is `NOT NULL`.

`app/api/auth.py::get_current_user` resolves that user as follows:

```
look up users WHERE email = LINKEDIN_USER_EMAIL
  ├─ found AND linkedin_access_token IS NOT NULL  → use that row  ✅
  └─ otherwise → build an in-memory User with user_id = None      ❌
                 → insert fails: null value in column "user_id"
```

**So the `users` row must exist and its `linkedin_access_token` column must be
non-NULL.** Both conditions. A row whose `linkedin_access_token` is NULL fails
exactly the same way as a missing row.

Run this once in the **Supabase SQL Editor**, substituting your values:

```sql
insert into users (email, full_name, linkedin_profile_url,
                   linkedin_access_token, linkedin_person_urn)
values ('you@example.com',
        'Your Name',
        'https://linkedin.com/in/your-vanity-name',
        'AQV...your access token...',
        'urn:li:person:XXXXXXXX')
on conflict (email) do update set
  full_name             = excluded.full_name,
  linkedin_profile_url  = excluded.linkedin_profile_url,
  linkedin_access_token = excluded.linkedin_access_token,
  linkedin_person_urn   = excluded.linkedin_person_urn,
  updated_at            = now();
```

The `email` here must match `LINKEDIN_USER_EMAIL` in `.env` **character for
character**. Confirm:

```sql
select user_id, email, full_name,
       (linkedin_access_token is not null) as has_token,
       linkedin_person_urn
from users order by user_id;
```

`has_token` must be `true` for your row.

> The token stored in this column is not what publishes the post — the env var
> is. It functions here as the "this user is provisioned" flag. Keeping the two
> in sync avoids confusion later.

### Current state (as of 2026-08-07)

```
user_id | email                  | full_name | has_token | posts
--------+------------------------+-----------+-----------+------
      2 | chetuvinay08@gmail.com | CHETAN P  | true      |     9
```

Two corrections were applied on this date:

- **`vinayuttangi@gmail.com` → `chetuvinay08@gmail.com`.** That row held the
  token for `urn:li:person:qd_C3vqY6T`, but `GET /v2/userinfo` on that token
  returns `sub: qd_C3vqY6T, name: CHETAN P, email: chetuvinay08@gmail.com` — the
  email on the row was simply wrong. Corrected in place, so `user_id = 2` and
  its 9 posts were preserved.
- **`chetan@example.com` (user_id 1) deleted**, cascading its 40 posts.

⚠️ **Side effect of that deletion:** topic dedup queries *all* posts globally
with no user filter (`select_topic_autonomously()` in
`app/agent/nodes/topic_selection.py` — it reads the last 100 posts regardless of
owner). The distinct-topic pool dropped **42 → 7**, so the agent has lost most
of its memory of what it has already published and will begin repeating topics
sooner than before. It degrades gracefully — no errors, just repetition — and
rebuilds naturally as new posts accumulate.

A full pre-change snapshot of both tables is at
`backup_users_posts_2026-08-07.sql` in the repo root. It restores users *and*
posts, so replaying it recovers the dedup history:

```powershell
# restore if needed (psql, or paste into the Supabase SQL Editor)
psql "<libpq-connection-string>" -f backup_users_posts_2026-08-07.sql
```

That file contains a plaintext LinkedIn access token — it is covered by
`backup_*.sql` in `.gitignore`. Keep it out of version control and off shared
drives.

---

## 9. Run and verify locally

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Healthy startup:

```
[OK] Database initialized
[OK] Branding templates registered
INFO:     Application startup complete.
```

A line like `No URN configured for Pranav kumar. Skipping registration` is
expected whenever `PRANAV_PERSON_URN` is blank.

### Checks, in order

**1. Health**

```powershell
Invoke-RestMethod http://localhost:8000/health
```
→ `{ status = ok; database = supabase; agent = langgraph }`

**2. Swagger** — http://localhost:8000/docs

Note: `get_current_user` does not verify the Bearer header at all; it resolves
the user from `LINKEDIN_USER_EMAIL`. Endpoints are callable from Swagger with no
token. Do not treat this deployment as access-controlled.

**3. Generate a post — this publishes for real**

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/posts/generate `
  -ContentType 'application/json' `
  -Body '{"idempotency_key":"manual-test-1"}'
```

Returns `202` immediately with a `post_id`; the work happens in the background.
The request body takes only `idempotency_key` — the topic is chosen by the
agent. Reusing a key returns the existing post instead of publishing twice.

**4. Poll the result**

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/posts/3
```

Watch `status` go `queued` → `published`. On `failed`, `error_reason` carries
the cause. A rendered image lands in `assets/generated_images/`, and the server
log prints the full LinkedIn request and response payloads.

---

## 10. Switching the agent to Pranav Kumar

Everything above, applied concretely. Do these in order on Pranav's laptop.

### Step 1 — LinkedIn app

Either add Pranav as a **Team member** on the existing app (`86npl3qgvcikkt`),
or register a new app under Pranav's company page. Either way, follow
[section 6.1](#61-prepare-the-linkedin-app): both products approved, and the
four redirect URLs present.

If Pranav uses a **new** app, note the new Client ID and Primary Client Secret.

### Step 2 — Mint Pranav's token and read his URN

Sign in **as Pranav** in the token generator ([6.2](#62-generate-the-token-easiest-path)),
scopes `openid profile email w_member_social`. Then run
[section 7](#7-getting-the-linkedin-person-urn) with that token to get `sub`.

Keep both values handy:

```
LINKEDIN_ACCESS_TOKEN = AQV...          (Pranav's)
LINKEDIN_PERSON_URN   = urn:li:person:<sub>
```

### Step 3 — `.env` on Pranav's machine

```env
# --- publishing identity ---------------------------------------------------
LINKEDIN_ACCESS_TOKEN=AQV...pranav-token...
LINKEDIN_PERSON_URN=urn:li:person:<pranav-sub>

# --- LinkedIn app (reference only; app doesn't read these at runtime) -------
LINKEDIN_CLIENT_ID=<pranav-client-id>
LINKEDIN_CLIENT_SECRET=<pranav-client-secret>

# --- which users row to attach posts to ------------------------------------
LINKEDIN_USER_EMAIL=pranavkumarpk0107@gmail.com
LINKEDIN_USER_NAME=Pranav Kumar
LINKEDIN_PROFILE_URL=https://linkedin.com/in/<pranav-vanity>

# --- branding: THIS is what selects the prebranded template -----------------
PRANAV_PERSON_URN=urn:li:person:<pranav-sub>     # same value as LINKEDIN_PERSON_URN
CHETAN_PERSON_URN=urn:li:person:qd_C3vqY6T       # leave; harmless when unused
```

Leave `DATABASE_URL`, `SUPABASE_*`, `GEMINI_API_KEY`, `GROQ_API_KEY` as they are
if reusing the existing project.

**`PRANAV_PERSON_URN` must equal `LINKEDIN_PERSON_URN` exactly.** That equality
is the entire branding switch: `image_rendering.py` looks up the posting URN in
the registry built by `app/branding/config.py`. Match → `Pranav_Linkedin_Template.jpeg`,
thought only. No match → blank template with `PROFILE_NAME` ("Chetan P") drawn on it.

Confirm the mapping registered at startup — the log must show:

```
Registered branding for Pranav kumar | urn=urn:li:person:… | template=assets/branding/Pranav_Linkedin_Template.jpeg (prebranded)
```

### Step 4 — Seed Pranav's `users` row

```sql
insert into users (email, full_name, linkedin_profile_url,
                   linkedin_access_token, linkedin_person_urn)
values ('pranavkumarpk0107@gmail.com',
        'Pranav Kumar',
        'https://linkedin.com/in/<pranav-vanity>',
        'AQV...pranav-token...',
        'urn:li:person:<pranav-sub>')
on conflict (email) do update set
  linkedin_access_token = excluded.linkedin_access_token,
  linkedin_person_urn   = excluded.linkedin_person_urn,
  updated_at            = now();
```

Skipping this produces `null value in column "user_id" violates not-null
constraint` on the very first generate call.

### Step 5 — Supabase (only if the browser login flow is needed)

Dashboard → **Authentication → Providers → LinkedIn (OIDC)** → set Pranav's
Client ID and Secret → save. Then make sure
`https://buubdwydkzjuetybicby.supabase.co/auth/v1/callback` is in the LinkedIn
app's redirect URLs.

Not needed for publishing — only for `/api/v1/auth/linkedin/login`.

### Step 6 — Verify before touching Render

Run locally and generate one post ([section 9](#9-run-and-verify-locally)).
Confirm on Pranav's feed that:

- the post appeared on **Pranav's** profile, and
- the image uses the prebranded template (no "Chetan P" text drawn on it).

Only then update production.

### Step 7 — Update Render

[Section 11](#11-rendercom-deployment).

### Checklist

- [ ] `w_member_social` + OpenID Connect approved on the LinkedIn app
- [ ] All four redirect URLs present
- [ ] Token minted while signed in **as Pranav**
- [ ] `LINKEDIN_ACCESS_TOKEN` replaced
- [ ] `LINKEDIN_PERSON_URN` = `urn:li:person:<sub>` (full prefix)
- [ ] `PRANAV_PERSON_URN` identical to `LINKEDIN_PERSON_URN`
- [ ] `LINKEDIN_USER_EMAIL` set to Pranav's email
- [ ] `users` row exists with non-NULL `linkedin_access_token`
- [ ] Startup log shows the prebranded template registered
- [ ] One test post verified on Pranav's feed
- [ ] Render env vars updated to match

---

## 11. Render.com deployment

The service is already live (`linkedin-post-agent-xyrp.onrender.com`), defined
by `render.yaml`: a `web` service plus a `cron` service on `0 9 * * 1,3,5`.

### Switching the live service to Pranav

Render Dashboard → **linkedin-agent** → **Environment**. Update:

| Key | Value |
|---|---|
| `LINKEDIN_ACCESS_TOKEN` | Pranav's token |
| `LINKEDIN_PERSON_URN` | `urn:li:person:<pranav-sub>` |
| `PRANAV_PERSON_URN` | same value again |
| `LINKEDIN_USER_EMAIL` | `pranavkumarpk0107@gmail.com` — **add this**, see below |

Then **Manual Deploy → Deploy latest commit** (env changes alone trigger a
restart, but a deploy is unambiguous).

> **`LINKEDIN_USER_EMAIL` is missing from `render.yaml`.** Because it is absent,
> production falls back to the hardcoded default in `app/core/config.py`. That
> default is stale, so this key **must** be set explicitly in the Render
> dashboard — to `chetuvinay08@gmail.com` today, to Pranav's email after the
> switch. Otherwise scheduled posts attach to the wrong user or fail outright.
>
> Consider adding it to `render.yaml` under the web service as `sync: false`
> so the next Blueprint deploy does not lose it.

Also confirm the LinkedIn app lists
`https://linkedin-post-agent-xyrp.onrender.com/api/v1/auth/linkedin/callback`
as an authorized redirect URL.

### Verify production

```powershell
Invoke-RestMethod https://linkedin-post-agent-xyrp.onrender.com/health
```

To force a post outside the schedule, run the same script the cron job runs:

```powershell
$env:APP_BASE_URL = 'https://linkedin-post-agent-xyrp.onrender.com'
python scripts/scheduled_post.py
```

It uses `scheduled-<UTC-date>` as the idempotency key, so a second run on the
same day is a no-op rather than a duplicate post.

### Cron job setup on Render

The recurring trigger is a **separate Render service** (`type: cron`), not a
thread inside the web app. It runs `scripts/scheduled_post.py`, which does one
thing: `POST /api/v1/posts/generate` against the web service. All intelligence —
topic choice, the 14-domain whitelist, weekly diversity — lives in the agent, so
the schedule stays dumb.

```
Render cron (0 9 * * 1,3,5 UTC)
   └─ python scripts/scheduled_post.py
        └─ POST https://<web-service>/api/v1/posts/generate
             body: {"idempotency_key": "scheduled-YYYY-MM-DD"}
```

#### Option A — Blueprint (recommended, already defined)

`render.yaml` declares both services. Render Dashboard → **New → Blueprint** →
point at this repo → Apply. The cron service is created automatically and
`APP_BASE_URL` is wired to the web service host by Render itself:

```yaml
- key: APP_BASE_URL
  fromService:
    type: web
    name: linkedin-agent
    property: host
```

`property: host` returns a bare hostname with no scheme; `_base_url()` in the
script prepends `https://`. Nothing to fill in by hand.

#### Option B — create the cron job manually in the dashboard

If the Blueprint was not used (e.g. the web service was created by hand):

1. Dashboard → **New +** → **Cron Job**
2. Connect the same repository, branch `main`
3. Fill in:

   | Field | Value |
   |---|---|
   | Name | `linkedin-agent-cron` |
   | Region | same as the web service (`oregon`) |
   | Runtime | Python 3 |
   | Build Command | `pip install --upgrade pip && pip install httpx` |
   | Command | `python scripts/scheduled_post.py` |
   | Schedule | `0 9 * * 1,3,5` |

4. **Environment** → add:

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.11.9` |
   | `APP_BASE_URL` | `https://linkedin-post-agent-xyrp.onrender.com` |
   | `REQUEST_TIMEOUT_SECONDS` | `60` |

5. **Create Cron Job**

The cron service needs **no** LinkedIn, Gemini, Supabase or database
credentials. It only makes an unauthenticated HTTP call; every secret lives on
the web service. Do not duplicate them here.

#### Schedule syntax

Standard 5-field cron, always **UTC** — Render has no timezone setting.

| Schedule | Meaning |
|---|---|
| `0 9 * * 1,3,5` | 09:00 UTC Mon/Wed/Fri (current — 2:30 PM IST) |
| `0 4 * * 1-5` | 04:00 UTC every weekday (9:30 AM IST) |
| `30 3 * * *` | 03:30 UTC daily (9:00 AM IST) |

IST is UTC+5:30, so subtract 5h30m from your desired local time. Changing the
cadence is safe: the agent enforces one distinct domain per post within a
calendar week regardless of when it fires.

To change it, edit `schedule` in `render.yaml` and redeploy the Blueprint, or
edit **Settings → Schedule** on the cron service directly.

#### Safety and verification

- **Double-fire protection is built in.** The key is
  `scheduled-<UTC-date>`, so a Render retry or a manual run on the same day
  returns the existing post instead of publishing twice
  (`_idempotency_key()` in the script).
- **Retries:** 3 attempts, 10s/20s backoff. It gives up immediately on any 4xx
  other than 429, since those never succeed on retry.
- **Cron jobs are a paid Render feature** — `plan: starter`. There is no free
  tier for `type: cron`.
- **Cold starts:** if the web service has spun down, the first request can take
  ~50s. That is why the timeout is 60s with retries.

Run it on demand without waiting for the schedule:

```powershell
$env:APP_BASE_URL = 'https://linkedin-post-agent-xyrp.onrender.com'
python scripts/scheduled_post.py
```

Or in the dashboard: cron service → **Trigger Run**. Check **Logs** for:

```
[cron] Triggering scheduled post
[cron]   target          : https://…/api/v1/posts/generate
[cron]   idempotency_key : scheduled-2026-08-07
[cron] SUCCESS (attempt 1) | status=202 post_id=51 state=queued
```

A `202` only means the job was *accepted*. The publish happens in the web
service's background task — confirm the outcome in the web service logs or via
`GET /api/v1/posts/<id>`.

### Rendered images are ephemeral

`image_rendering.py` writes to `assets/generated_images/` on local disk. Render's
filesystem is wiped on every deploy and restart. The image is uploaded to
LinkedIn immediately, so this does not affect posting — but `posts.image_url`
points at a path that will not exist later. Do not build anything that reads it
back.

---

## 12. Troubleshooting

**`null value in column "user_id" violates not-null constraint`**
The `users` row for `LINKEDIN_USER_EMAIL` is missing, or its
`linkedin_access_token` is NULL. See [section 8](#8-seeding-the-user-row-required).
This is by far the most common first-run failure.

**Post publishes but the image says "Chetan P"**
`PRANAV_PERSON_URN` does not exactly equal `LINKEDIN_PERSON_URN`, so the blank
template was used and `PROFILE_NAME` was drawn onto it. Compare both strings
including the `urn:li:person:` prefix, restart, and check the startup log for
`Registered branding for Pranav kumar`.

**LinkedIn `401 Unauthorized` on publish**
Token expired — member tokens last 2 months. Re-mint
([section 6.2](#62-generate-the-token-easiest-path)) and update `.env` *and*
Render. There is no auto-refresh for the publishing token.

**LinkedIn `403 ACCESS_DENIED`**
`w_member_social` was not granted. The "Share on LinkedIn" product must be
approved *and* the scope ticked when the token was created. Adding the product
later does not upgrade an already-issued token — mint a new one.

**Post published as text with no image**
Image upload failed and the code fell back to text-only, by design
(`posts.py`). Search the logs for `Image upload/publishing FAILED`. Usual
causes: the template file is missing, or `assets/fonts/Inter_18pt-SemiBold.ttf`
is absent.

**`ModuleNotFoundError` / `psycopg` errors on Windows**
Activate the venv. If the error mentions the event loop, the entry point is
missing the `WindowsSelectorEventLoopPolicy` call that `app/api/main.py` makes.

**`alembic upgrade head` hangs**
Supabase free-tier projects pause after inactivity — open the dashboard to wake
it. Also confirm the password in `DATABASE_URL` is quoted if it contains `$`.

**Status stuck at `queued`**
The background task died before writing a status. Check the server log for the
`[POST-<id>]` correlation-id trace; every node logs entry and exit under it.

**No LangSmith traces**
Expected — see [section 4](#keys-you-may-see-but-that-do-nothing). Tracing is
not wired up.

**Duplicate posts**
Always send an `idempotency_key`. Without one, every call publishes.

---

## Quick reference

```powershell
# run
uvicorn app.api.main:app --reload --port 8000

# migrate
alembic upgrade head

# generate one post
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/posts/generate `
  -ContentType 'application/json' -Body '{"idempotency_key":"test-1"}'

# check a post
Invoke-RestMethod http://localhost:8000/api/v1/posts/<id>

# read person URN from a token
Invoke-RestMethod -Uri 'https://api.linkedin.com/v2/userinfo' `
  -Headers @{ Authorization = "Bearer <TOKEN>" }
```

| Thing | Where |
|---|---|
| Env schema | `app/core/config.py` |
| Publish path | `app/api/routers/posts.py`, `app/services/linkedin.py` |
| Agent graph | `app/agent/graph.py` |
| Topic whitelist | `app/agent/nodes/topic_selection.py` |
| Branding map | `app/branding/config.py` |
| User resolution | `app/api/auth.py` |
| Deploy config | `render.yaml` |
| Prompts | `.prompts/SYSTEM_PROMPT.md` |
