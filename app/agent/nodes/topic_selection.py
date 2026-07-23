"""Topic selection node for autonomous LinkedIn content generation.

Selects topics autonomously while preventing duplicates and maintaining
category diversity across engineering domains.
"""

import logging
import random
from sqlalchemy import select, desc
from app.db import Post
from app.db.database import get_session_maker

logger = logging.getLogger(__name__)

# Curated topics organized by category for diversity
TOPIC_CATEGORIES = {
    "java_spring": [
        "Spring Boot transaction management at scale",
        "Optimizing JVM garbage collection for low-latency systems",
        "Building reactive microservices with Project Reactor",
        "Java concurrency patterns in distributed systems",
        "Spring Cloud Stream for event-driven architectures",
        "Understanding Java memory model and happens-before relationships",
        "Virtual threads: the future of Java concurrency",
        "Spring Boot actuator for production observability",
    ],
    "python_async": [
        "Async/await patterns for high-throughput services",
        "Building FastAPI applications at production scale",
        "Python asyncio internals and event loop optimization",
        "Concurrent.futures vs asyncio: trade-offs and use cases",
        "FastAPI WebSockets for real-time applications",
        "Async context managers and resource management",
        "Error handling in async/await code",
        "Debugging async Python applications effectively",
    ],
    "system_design": [
        "Database connection pooling strategies",
        "Distributed cache coherence in microservices",
        "Load balancing algorithms and sticky sessions",
        "Zero-downtime deployments with minimal data loss",
        "Consensus algorithms: Paxos vs Raft vs PBFT",
        "CAP theorem in practice: trade-offs at scale",
        "Designing idempotent APIs",
        "Circuit breaker pattern for resilient systems",
    ],
    "genai_llms": [
        "Building resilient LLM applications with fallbacks",
        "Token counting and context window management",
        "Prompt engineering for production LLM systems",
        "Fine-tuning vs retrieval-augmented generation",
        "Monitoring and observability for AI systems",
        "Handling LLM hallucinations in production",
        "Cost optimization for LLM APIs",
        "Structured outputs from language models",
    ],
    "devops_infra": [
        "Kubernetes resource requests and limits optimization",
        "Container networking: CNI plugins and service meshes",
        "Infrastructure as Code patterns and anti-patterns",
        "Observability: logs vs metrics vs traces",
        "GitOps workflows for multi-cluster deployments",
        "Secrets management in cloud-native applications",
        "Container image optimization and security scanning",
        "Disaster recovery and backup strategies",
    ],
    "databases": [
        "PostgreSQL query optimization and EXPLAIN analysis",
        "Write amplification in LSM-tree databases",
        "ACID vs BASE trade-offs in distributed systems",
        "Index selection strategies for complex queries",
        "Row-level security and multi-tenancy in PostgreSQL",
        "Database sharding strategies and consistency",
        "Connection pooling with PgBouncer or pgpool",
        "Monitoring PostgreSQL performance in production",
    ],
}


async def select_topic_autonomously() -> tuple[str, str]:
    """Select topic autonomously, avoiding recent duplicates.

    Queries recent posts from database to build a set of excluded topics,
    then randomly selects from remaining topics to maintain diversity.

    Returns:
        Tuple of (selected_topic, category)

    Raises:
        Exception if database query fails
    """
    session_maker = get_session_maker()

    try:
        async with session_maker() as db:
            # Get last 100 posts to avoid recent duplicates
            stmt = (
                select(Post.topic)
                .where(Post.status.in_(["published", "queued"]))
                .order_by(desc(Post.created_at))
                .limit(100)
            )
            recent_posts = (await db.execute(stmt)).scalars().all()
            recent_topics = set(recent_posts) if recent_posts else set()

    except Exception as e:
        logger.error(f"Failed to query recent topics: {str(e)}. Proceeding without dedup.")
        recent_topics = set()

    logger.info(f"Excluded {len(recent_topics)} recent topics from selection")

    # Find candidate topics not in recent posts
    for attempt in range(20):  # Try up to 20 times to find a unique topic
        category = random.choice(list(TOPIC_CATEGORIES.keys()))
        topics = TOPIC_CATEGORIES[category]
        topic = random.choice(topics)

        if topic not in recent_topics:
            logger.info(
                f"Selected topic (attempt {attempt + 1}): '{topic}' "
                f"from category '{category}'"
            )
            return topic, category

    # Fallback: all topics are recent (should be very rare)
    category = random.choice(list(TOPIC_CATEGORIES.keys()))
    topic = random.choice(TOPIC_CATEGORIES[category])
    logger.warning(
        f"Could not find unique topic after 20 attempts. "
        f"Selected: '{topic}' from '{category}' (may be recent)"
    )
    return topic, category


async def topic_selection_node(state: dict) -> dict:
    """LangGraph node for autonomous topic selection.

    Runs at workflow start. Selects a topic and category, then returns
    updated state with both fields. This node is independent and can be
    tested in isolation.

    Args:
        state: LangGraph state (may be empty on first invocation)

    Returns:
        Updated state dict with:
            - topic: Selected topic string
            - selected_category: Category string (java_spring, python_async, etc.)
    """
    topic, category = await select_topic_autonomously()

    return {
        "topic": topic,
        "selected_category": category,
    }
