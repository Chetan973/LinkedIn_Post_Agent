Please implement the Request Idempotency layer for my FastAPI and LangGraph LinkedIn Post Agent backend to prevent duplicate post generation when users double-click or retry requests.

Here are the specific requirements:
1. Update the `PostGenerateRequest` Pydantic schema in `app/api/schemas.py` to optionally accept an `idempotency_key` (as a string or UUID).
2. Update the `Post` database model in `app/db.py` to include columns for:
   - `idempotency_key` (Indexed, unique, nullable/string)
   - `linkedin_post_id` (String, nullable, to store the external LinkedIn post reference)
3. Modify the `generate_post` endpoint in `app/api/routers/posts.py`:
   - Check if an incoming request includes an `idempotency_key`.
   - Query the database to see if a post with that `idempotency_key` already exists.
   - If it already exists, gracefully return the existing post record and its current status instead of spawning a duplicate background task.
   - If it does not exist, create the new post record storing the `idempotency_key`, commit it to Supabase, and proceed with triggering the `run_agent` background task.

Please provide the exact file updates and code changes needed.