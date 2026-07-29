"""Trigger one scheduled LinkedIn post. Entry point for the Render.com cron job.

Runs three times per week (Mon/Wed/Fri per render.yaml). Each invocation POSTs
to /api/v1/posts/generate; topic selection, domain-whitelist enforcement and
intra-week diversity all happen inside the agent graph.

Idempotency: the request carries `scheduled-<UTC date>` as its idempotency_key,
so a Render retry - or an accidental double-trigger on the same day - returns
the existing post instead of publishing twice.

Usage:
    python scripts/scheduled_post.py

Environment:
    APP_BASE_URL   Base URL of the running web service, e.g.
                   https://linkedin-agent.onrender.com
                   Falls back to RENDER_EXTERNAL_URL, then localhost:8000.
    REQUEST_TIMEOUT_SECONDS  Optional, default 60.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx

GENERATE_PATH = "/api/v1/posts/generate"
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 10


def _base_url() -> str:
    """Resolve the target service URL from the environment.

    Render's `fromService: property: host` injects a bare hostname with no
    scheme, so add https:// when one is missing.
    """
    url = (
        os.getenv("APP_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or "http://localhost:8000"
    ).strip().rstrip("/")

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    return url


def _idempotency_key() -> str:
    """One key per UTC calendar day, so same-day retries never double-post."""
    return f"scheduled-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


async def trigger_post() -> int:
    """POST to the generate endpoint with retries.

    Returns:
        Process exit code: 0 on success, 1 on failure
    """
    url = f"{_base_url()}{GENERATE_PATH}"
    key = _idempotency_key()
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))

    print(f"[cron] Triggering scheduled post")
    print(f"[cron]   target          : {url}")
    print(f"[cron]   idempotency_key : {key}")
    print(f"[cron]   utc time        : {datetime.now(timezone.utc).isoformat()}")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json={"idempotency_key": key})

            if response.status_code in (200, 202):
                body = response.json()
                print(
                    f"[cron] SUCCESS (attempt {attempt}) | "
                    f"status={response.status_code} "
                    f"post_id={body.get('post_id')} "
                    f"state={body.get('status')}"
                )
                print(f"[cron]   {body.get('message', '')}")
                return 0

            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            print(f"[cron] Attempt {attempt}/{MAX_ATTEMPTS} failed | {last_error}")

            # 4xx other than 429 will not succeed on retry
            if 400 <= response.status_code < 500 and response.status_code != 429:
                print("[cron] Client error - not retrying.")
                break

        except (httpx.TimeoutException, httpx.RequestError) as e:
            last_error = f"{type(e).__name__}: {str(e)}"
            print(f"[cron] Attempt {attempt}/{MAX_ATTEMPTS} failed | {last_error}")

        if attempt < MAX_ATTEMPTS:
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"[cron] Retrying in {wait}s...")
            await asyncio.sleep(wait)

    print(f"[cron] FAILED after {MAX_ATTEMPTS} attempt(s). Last error: {last_error}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(trigger_post()))
    except KeyboardInterrupt:
        print("[cron] Interrupted.")
        sys.exit(130)
