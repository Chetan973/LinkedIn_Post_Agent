# 🔐 Supabase LinkedIn OAuth2 Setup Guide

## Overview

This guide walks you through configuring LinkedIn OAuth2 authentication in Supabase Auth, then connecting it to your FastAPI application.

**Architecture**:
- Frontend → Supabase Auth (LinkedIn OAuth) → JWT token
- Frontend → FastAPI API + Bearer JWT
- FastAPI → Verify JWT + Auto-provision user in PostgreSQL

---

## Part 1: Configure Supabase Auth (Dashboard)

### Step 1: Get Supabase Credentials

1. Log in to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Settings → API**
4. Copy:
   - **Project URL** (e.g., `https://your-project.supabase.co`)
   - **JWT Secret** (under "JWT Settings" - this is critical!)
   - **Anon Key** and **Service Role Key** (if needed for client)

### Step 2: Enable LinkedIn Provider

1. Go to **Authentication → Providers**
2. Click **LinkedIn**
3. Enable the provider
4. Copy the **LinkedIn OAuth Credentials**:
   - **Client ID**: From LinkedIn app console
   - **Client Secret**: From LinkedIn app console

   > **How to get LinkedIn credentials:**
   > 1. Go to [LinkedIn Developer Console](https://www.linkedin.com/developers/apps)
   > 2. Create a new app (or select existing)
   > 3. Go to **Auth** tab
   > 4. Copy **Client ID** and **Client secret**
   > 5. Add Redirect URI: `https://your-project.supabase.co/auth/v1/callback`

5. Paste into Supabase LinkedIn provider settings
6. Save

### Step 3: Configure Redirect URLs

1. In **Authentication → URL Configuration**
2. Set **Redirect URLs**:
   ```
   http://localhost:3000/auth/callback
   https://yourdomain.com/auth/callback
   ```

3. Set **Site URL**:
   ```
   http://localhost:3000
   ```
   (or your production domain)

### Step 4: Copy JWT Secret for FastAPI

This is **critical** for FastAPI to verify tokens:

1. Go to **Authentication → Providers → JWT Settings**
2. Copy the **JWT secret** value (NOT the JWT token - the secret key)
3. Add to your `.env` file (see Part 2 below)

---

## Part 2: Configure FastAPI (.env)

### Update Your `.env` File

Add these variables (get values from Supabase dashboard):

```env
# Supabase Authentication
SUPABASE_JWT_SECRET=your_jwt_secret_from_supabase_here

# Supabase Database Connection (if using Supabase Postgres)
DATABASE_URL=postgresql+psycopg_async://postgres:your_password@your-project.supabase.co:5432/postgres

# Other existing config...
GEMINI_API_KEY=...
LINKEDIN_ACCESS_TOKEN=...
```

**Important**: The `SUPABASE_JWT_SECRET` is the signing secret, NOT a token. It looks like a random string (~50 chars).

---

## Part 3: Frontend Integration

### Using Supabase Client (React/Vue/etc)

```javascript
// Install: npm install @supabase/supabase-js

import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://your-project.supabase.co',
  'your_anon_key'
)

// Trigger LinkedIn OAuth
async function signInWithLinkedIn() {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'linkedin'
  })
}

// Get JWT token after login
async function getToken() {
  const { data } = await supabase.auth.getSession()
  return data.session.access_token  // This is the JWT
}

// Send to FastAPI with Bearer token
async function generatePost() {
  const token = await getToken()
  
  const response = await fetch('http://localhost:8000/api/v1/posts/generate', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})  // Empty payload - topic selected autonomously
  })
  
  return response.json()
}
```

---

## Part 4: JWT Payload Structure

When a user logs in via LinkedIn, Supabase creates a JWT with this structure:

```json
{
  "sub": "user-uuid-here",
  "email": "user@example.com",
  "email_confirmed_at": "2024-01-01T00:00:00Z",
  "phone_verified_at": null,
  "user_metadata": {
    "avatar_url": "https://...",
    "email": "user@example.com",
    "name": "User Name",
    "linkedin_profile_url": "https://linkedin.com/in/username"  // From LinkedIn
  },
  "aud": "authenticated",
  "iss": "https://your-project.supabase.co/auth/v1",
  "iat": 1704067200,
  "exp": 1704153600,  // 24 hours later
  "iss": "https://your-project.supabase.co"
}
```

**FastAPI extracts**:
- `email` → Creates/updates User record
- `user_metadata.linkedin_profile_url` → Stores LinkedIn URL

---

## Part 5: How FastAPI Authentication Works

### Endpoint Flow

```
1. Frontend sends POST /api/v1/posts/generate
   Header: Authorization: Bearer {supabase_jwt_token}

2. FastAPI auth.py:
   a) Extracts token from Authorization header
   b) Verifies signature using SUPABASE_JWT_SECRET
   c) Checks audience = "authenticated"
   d) Extracts email and LinkedIn URL
   e) Queries User table for existing user
   f) If NOT found → Auto-creates User record
   g) Returns User object

3. posts.py endpoint:
   - Receives User object
   - Creates Post with user_id=current_user.user_id
   - Launches background task (unchanged)
```

---

## Part 6: Testing Authentication

### Test 1: Get JWT Token (via CLI)

```bash
# Install Supabase CLI
npm install -g supabase

# List users in your Supabase project
supabase auth users list --project-ref your-project-ref
```

### Test 2: Test FastAPI Endpoint

```bash
# Get a valid JWT from your frontend, then:

curl -X POST http://localhost:8000/api/v1/posts/generate \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Test 3: Verify User Auto-Creation

```bash
# Check database for the auto-created user
psql $DATABASE_URL << 'SQL'
SELECT user_id, email, linkedin_profile_url, created_at 
FROM users 
ORDER BY created_at DESC LIMIT 5;
SQL
```

---

## Part 7: Environment Variables Reference

| Variable | Source | Example | Required |
|----------|--------|---------|----------|
| `SUPABASE_JWT_SECRET` | Supabase → Auth → JWT Settings | `abc123...xyz` | ✅ Yes |
| `DATABASE_URL` | Supabase → Settings → Database | `postgresql+psycopg_async://...` | ✅ Yes |
| `LINKEDIN_ACCESS_TOKEN` | For publishing posts (separate from auth) | `AQXxxx...` | ✅ Yes |
| `LINKEDIN_PERSON_URN` | For publishing posts | `urn:li:person:xxx` | ✅ Yes |
| `GEMINI_API_KEY` | For LLM | From Google AI Studio | ✅ Yes |

---

## Part 8: Troubleshooting

### Error: "Token has expired"

**Cause**: JWT token is older than 24 hours

**Fix**: Frontend needs to refresh token:
```javascript
const { data } = await supabase.auth.refreshSession()
const newToken = data.session.access_token
```

### Error: "Invalid token: Invalid audience claim"

**Cause**: JWT audience is not "authenticated"

**Fix**: Verify you're using the correct `SUPABASE_JWT_SECRET` from Auth settings (not API key)

### Error: "SUPABASE_JWT_SECRET not configured"

**Cause**: Environment variable not set

**Fix**: 
```bash
# Check .env file
grep SUPABASE_JWT_SECRET .env

# If missing, add it
echo "SUPABASE_JWT_SECRET=your_secret_here" >> .env
```

### Error: "Email not found in token"

**Cause**: LinkedIn provider not sending email

**Fix**: 
1. Check Supabase LinkedIn provider settings
2. Verify LinkedIn app has email permission
3. Ask user to re-authorize

### User Not Auto-Created

**Debug**: Check logs
```bash
# Look for "Auto-creating user from JWT" in logs
grep "Auto-creating" app.log

# Verify database connection works
psql $DATABASE_URL -c "SELECT 1"
```

---

## Part 9: Production Checklist

- [ ] `SUPABASE_JWT_SECRET` set in production .env
- [ ] Database URL points to production Supabase
- [ ] LinkedIn OAuth redirect URLs include production domain
- [ ] Supabase URL configuration includes production domain
- [ ] HTTPS enforced for all OAuth flows
- [ ] JWT expiration monitored (default 24 hours)
- [ ] Token refresh implemented in frontend
- [ ] Error handling for expired tokens
- [ ] User auto-creation logged for audit trail
- [ ] Database backups enabled

---

## Part 10: Architecture Diagram

```
┌─────────────┐
│  Frontend   │
│  (React)    │
└──────┬──────┘
       │
       │ 1. User clicks "Sign in with LinkedIn"
       │
       ▼
┌──────────────────────┐
│  Supabase Auth       │
│  - LinkedIn OAuth2   │
│  - JWT generation    │
└──────┬───────────────┘
       │
       │ 2. Returns JWT token + redirect
       │
       ▼
┌──────────────────────────────┐
│  Frontend Stores JWT          │
│  (localStorage/cookie)        │
└──────┬───────────────────────┘
       │
       │ 3. POST /api/v1/posts/generate
       │    + Bearer JWT
       │
       ▼
┌──────────────────────────────────┐
│  FastAPI app/api/auth.py         │
│  - Decode JWT                    │
│  - Verify signature              │
│  - Extract email + LinkedIn URL  │
└──────┬───────────────────────────┘
       │
       │ 4. Query User table
       │    email = extracted email
       │
       ▼
┌──────────────────────┐
│  PostgreSQL/Supabase │
│  User Table          │
│  (auto-create if     │
│   not found)         │
└──────┬───────────────┘
       │
       │ 5. Return User object
       │
       ▼
┌──────────────────────────────────┐
│  FastAPI posts.py endpoint       │
│  - Receive User object           │
│  - Create Post with user_id      │
│  - Launch background task        │
│  (unchanged!)                    │
└──────────────────────────────────┘
```

---

## Summary

✅ **You now have**:
- LinkedIn OAuth authentication via Supabase Auth
- JWT verification in FastAPI
- Automatic user provisioning from LinkedIn metadata
- Fully authenticated `/api/v1/posts/generate` endpoint

🚀 **Next steps**:
1. Configure LinkedIn app in Supabase dashboard
2. Copy JWT secret to `.env`
3. Implement frontend login flow with Supabase client
4. Test end-to-end authentication
5. Deploy to production

