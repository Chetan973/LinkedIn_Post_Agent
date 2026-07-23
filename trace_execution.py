#!/usr/bin/env python3
"""
Production execution trace tool.

Instruments the image posting pipeline and traces one real execution
to find the exact stopping point.
"""

import asyncio
import logging
import sys
import json
from datetime import datetime
from pathlib import Path

# Configure logging with detailed instrumentation
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('trace_execution.log'),
    ]
)

# Create execution trace class to capture all logs
class ExecutionTracer:
    """Captures all execution events in JSON format for analysis."""

    def __init__(self):
        self.events = []
        self.start_time = datetime.now()

    def record(self, event_type, **kwargs):
        """Record an execution event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_ms': int((datetime.now() - self.start_time).total_seconds() * 1000),
            'type': event_type,
            **kwargs
        }
        self.events.append(event)
        print(f"\n📍 [{event['elapsed_ms']}ms] {event_type}: {kwargs}")

    def save(self, filename='trace.json'):
        """Save all events to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.events, f, indent=2)
        print(f"\n📁 Trace saved to {filename}")

    def print_summary(self):
        """Print summary of execution."""
        print("\n" + "=" * 80)
        print("EXECUTION TRACE SUMMARY")
        print("=" * 80)

        # Find function entry/exit pairs
        stack = []
        for event in self.events:
            if event['type'] in ['ASYNC ENTER', 'ENTER']:
                stack.append(event)
            elif event['type'] in ['ASYNC EXIT', 'EXIT', 'ASYNC EXCEPTION', 'EXCEPTION']:
                if stack:
                    entry = stack.pop()
                    elapsed = event['elapsed_ms'] - entry['elapsed_ms']
                    status = '✓' if 'EXIT' in event['type'] else '✗'
                    print(f"{status} {entry.get('function', 'unknown')} ({elapsed}ms)")

        # Find last event before stop
        print("\nLast 10 events:")
        for event in self.events[-10:]:
            print(f"  [{event['elapsed_ms']:5d}ms] {event['type']:20s} {event}")

        if self.events:
            last = self.events[-1]
            if 'EXCEPTION' in last['type']:
                print(f"\n🔴 STOPPED AT: {last['type']}")
                print(f"   Function: {last.get('function', 'unknown')}")
                print(f"   Error: {last.get('exception_message', 'unknown')}")
            elif 'EXIT' in last['type'] or 'COMPLETE' in last['type']:
                print(f"\n✓ EXECUTION COMPLETED")
                print(f"   Last event: {last['type']}")
            else:
                print(f"\n⚠️  UNKNOWN STATE")
                print(f"   Last event: {last['type']}")


tracer = ExecutionTracer()


async def main():
    """Trace one image post execution end-to-end."""
    tracer.record('TRACE_START', description='Starting execution trace')

    try:
        # Import after instrumentation is set up
        from app.api.routers.posts import run_agent
        from app.db import get_session_maker, Post, PostStatus
        from app.core.instrumentation import set_correlation_id

        tracer.record('IMPORTS_COMPLETE', modules=['posts.py', 'db'])

        # Create test post in database
        session_maker = get_session_maker()
        tracer.record('DB_SESSION_CREATED')

        async with session_maker() as db:
            test_post = Post(
                topic="Testing image post pipeline",
                draft_content="",
                status=PostStatus.QUEUED.value,
                user_id=1,  # Test user
            )
            db.add(test_post)
            await db.commit()
            await db.refresh(test_post)
            post_id = test_post.post_id
            tracer.record('DB_POST_CREATED', post_id=post_id)

        # Set correlation ID for trace
        cid = f"TRACE-{post_id}"
        set_correlation_id(cid)
        tracer.record('CORRELATION_ID_SET', correlation_id=cid)

        # Run agent with full tracing
        tracer.record('RUN_AGENT_START', post_id=post_id)
        await run_agent(post_id)
        tracer.record('RUN_AGENT_COMPLETE', post_id=post_id)

        # Check final status
        async with session_maker() as db:
            from sqlalchemy import select
            stmt = select(Post).where(Post.post_id == post_id)
            post = (await db.execute(stmt)).scalars().first()
            if post:
                tracer.record(
                    'FINAL_STATUS',
                    post_id=post_id,
                    status=post.status,
                    error_reason=post.error_reason,
                    image_url=post.image_url,
                    linkedin_post_id=post.linkedin_post_id
                )

    except Exception as e:
        tracer.record('EXCEPTION', exception=str(e), type=type(e).__name__)
        import traceback
        tracer.record('TRACEBACK', tb=traceback.format_exc())

    finally:
        tracer.record('TRACE_END')
        tracer.print_summary()
        tracer.save()


if __name__ == "__main__":
    asyncio.run(main())
