#!/usr/bin/env python3
"""
INSTRUMENTATION-ONLY TRACE - Dry run to capture logs WITHOUT calling production APIs.

This is a DRY RUN that:
1. Creates a test post in database
2. Instruments the workflow to capture all logs
3. Does NOT actually call LinkedIn API
4. Does NOT upload real images
5. Shows where execution WOULD stop

SAFE TO RUN - No production API calls, no real posts created.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, AsyncMock

print("\n" + "="*80)
print("DRY RUN EXECUTION TRACE - Instrumentation Analysis")
print("="*80)
print("\nWARNING: This is a DRY RUN with mocked HTTP calls")
print("To see ACTUAL execution with real API calls, run without mocks\n")

# Setup enhanced logging to capture EVERYTHING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('instrumentation_trace.log'),
    ]
)

# Also capture structured logs
structured_logs = []

class LogCapture(logging.Handler):
    """Capture all logs for analysis."""
    def emit(self, record):
        structured_logs.append({
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'function': record.funcName,
            'line': record.lineno,
        })


logging.getLogger().addHandler(LogCapture())

async def mock_linkedin_api(*args, **kwargs):
    """Mock LinkedIn API responses."""
    # Simulate successful API responses
    response = AsyncMock()
    response.status_code = 200
    response.text = '{"value": {"image": "urn:li:image:12345", "status": "AVAILABLE"}}'
    response.headers = {}
    response.json = AsyncMock(return_value={"value": {"image": "urn:li:image:12345", "status": "AVAILABLE"}})
    return response

async def main():
    """Run trace."""
    try:
        # Import after logging is configured
        from app.db import get_session_maker, Post, PostStatus
        from app.api.routers.posts import run_agent
        from app.core.instrumentation import set_correlation_id

        print("[1/4] Creating test post in database...")
        session_maker = get_session_maker()

        async with session_maker() as db:
            test_post = Post(
                topic="DRY RUN: Instrumentation trace",
                draft_content="",
                status=PostStatus.QUEUED.value,
                user_id=1,
            )
            db.add(test_post)
            await db.commit()
            await db.refresh(test_post)
            post_id = test_post.post_id

        print(f"    OK - Post {post_id} created in database\n")

        # Set correlation ID
        cid = f"TRACE-{post_id}"
        set_correlation_id(cid)
        print(f"[2/4] Correlation ID: {cid}\n")

        # Run the agent WITH mocked HTTP calls
        print(f"[3/4] Running run_agent({post_id}) with mocked HTTP...\n")
        print("-" * 80)

        # Mock httpx.AsyncClient to prevent real API calls
        with patch('app.Services.linkedin_media.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            # Mock all HTTP responses
            mock_client.post.return_value = await mock_linkedin_api()
            mock_client.put.return_value = await mock_linkedin_api()
            mock_client.put.return_value.status_code = 204  # Binary upload returns 204
            mock_client.get.return_value = await mock_linkedin_api()
            mock_client.get.return_value.text = '{"value": {"image": "urn:li:image:12345", "status": "AVAILABLE"}}'

            try:
                await run_agent(post_id)
                print("\n" + "-" * 80)
                print(f"OK - run_agent() completed\n")
            except Exception as e:
                print("\n" + "-" * 80)
                print(f"ERROR - run_agent() raised exception:\n{e}\n")
                import traceback
                traceback.print_exc()

        # Check final status
        print("[4/4] Checking final post status...\n")

        async with session_maker() as db:
            from sqlalchemy import select
            stmt = select(Post).where(Post.post_id == post_id)
            post = (await db.execute(stmt)).scalars().first()

            if post:
                print(f"    Status: {post.status}")
                print(f"    Image URL: {post.image_url}")
                print(f"    LinkedIn Post ID: {post.linkedin_post_id}")
                print(f"    Error Reason: {post.error_reason}")
            else:
                print("    ERROR - Post not found in database!")

        print("\n" + "="*80)
        print("EXECUTION TRACE ANALYSIS")
        print("="*80 + "\n")

        # Find where execution stopped
        print(f"Total log entries: {len(structured_logs)}\n")

        if structured_logs:
            print("Last 30 log entries:\n")
            for log in structured_logs[-30:]:
                level = log['level']
                msg = log['message'][:100]
                print(f"[{level:8s}] {msg}")

            print("\n" + "-" * 80)
            print(f"\nLast log entry:")
            last_log = structured_logs[-1]
            print(f"  Logger: {last_log['logger']}")
            print(f"  Function: {last_log['function']}")
            print(f"  Line: {last_log['line']}")
            print(f"  Level: {last_log['level']}")
            print(f"  Message: {last_log['message']}")

        # Check for specific patterns
        print("\n" + "-" * 80)
        print("Execution flow:\n")

        has_run_agent = any('run_agent' in log['logger'] or 'run_agent' in log['message'] for log in structured_logs)
        has_image_rendering = any('image_rendering' in log['logger'].lower() for log in structured_logs)
        has_image_upload = any('upload_image' in log['message'].lower() for log in structured_logs)
        has_image_poll = any('wait_for_image' in log['message'].lower() or 'AVAILABLE' in log['message'] for log in structured_logs)
        has_linkedin_http = any('http request' in log['message'].lower() or 'http response' in log['message'].lower() for log in structured_logs)
        has_publish = any('publish' in log['message'].lower() and 'rest/posts' in log['message'].lower() for log in structured_logs)

        print(f"  1. run_agent() executed: {'✓' if has_run_agent else '✗'}")
        print(f"  2. Image rendering: {'✓' if has_image_rendering else '✗'}")
        print(f"  3. Image upload: {'✓' if has_image_upload else '✗'}")
        print(f"  4. Image polling (wait_for_image_available): {'✓' if has_image_poll else '✗'}")
        print(f"  5. HTTP calls made: {'✓' if has_linkedin_http else '✗'}")
        print(f"  6. POST /rest/posts: {'✓' if has_publish else '✗'}")

        print("\n" + "="*80)

        # Save structured logs
        import json
        with open('instrumentation_trace.json', 'w') as f:
            json.dump(structured_logs, f, indent=2)
        print("\nLogs saved to:")
        print("  - instrumentation_trace.log (text format)")
        print("  - instrumentation_trace.json (structured format)")
        print("\nDRY RUN COMPLETE - No real LinkedIn posts created")

    except Exception as e:
        print(f"\n[FATAL] Trace failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
