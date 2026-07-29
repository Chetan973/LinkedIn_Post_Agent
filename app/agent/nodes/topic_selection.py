"""Topic selection node for autonomous LinkedIn content generation.

Selects topics autonomously from a strict domain whitelist while preventing
duplicates and enforcing intra-week domain diversity.

Every topic MUST belong to one of the 14 approved domains defined in
.prompts/SYSTEM_PROMPT.md. Topics outside the whitelist are unreachable by
construction - the selector can only choose from ALLOWED_DOMAINS.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, desc
from app.db import Post
from app.db.database import get_session_maker

logger = logging.getLogger(__name__)

# The ONLY 14 approved domains. Mirrors the whitelist in
# .prompts/SYSTEM_PROMPT.md. Nothing outside this tuple may ever be posted.
ALLOWED_DOMAINS = (
    "generative_ai",
    "devops",
    "cloud",
    "mlops",
    "rag",
    "embeddings",
    "chunking",
    "vector_databases",
    "ai_cloud_architecture",
    "cost_optimization",
    "performance_optimization",
    "microservices",
    "software_engineering_best_practices",
    "ai_application_development",
)

# Human-readable domain labels, used for entropy injection and logging
DOMAINS = [
    "Generative AI",
    "DevOps",
    "Cloud",
    "MLOps",
    "RAG",
    "Embeddings",
    "Chunking",
    "Vector Databases",
    "AI/Cloud Architecture",
    "Cost Optimization",
    "Performance Optimization",
    "Microservices",
    "Software Engineering Best Practices",
    "AI Application Development",
]

# Curated production-focused topics, keyed by approved domain.
# Every topic must be practical engineering content: architecture patterns,
# cost-saving techniques, performance improvements, coding best practices,
# cloud-native design, deployment strategies, or real-world implementation.
TOPIC_CATEGORIES = {
    "generative_ai": [
        "Structured outputs as a reliability contract for LLM services",
        "Designing deterministic fallback chains across LLM providers",
        "Token budgeting strategies for long-running agent workflows",
        "Guardrail patterns that catch hallucinations before they ship",
        "Streaming LLM responses without breaking downstream validation",
        "Prompt versioning and rollback in production systems",
        "Evaluating LLM output quality with automated scoring harnesses",
        "Handling provider rate limits with backpressure and queuing",
    ],
    "devops": [
        "Progressive delivery with canary analysis and automated rollback",
        "GitOps reconciliation loops for multi-cluster fleets",
        "Secrets rotation without redeploying running workloads",
        "Building reproducible CI pipelines with layer-aware caching",
        "Blue-green deployments for stateful services",
        "Infrastructure drift detection and automated remediation",
        "Trunk-based development at scale with feature flags",
        "Cutting CI runtime with dependency graph aware test selection",
    ],
    "cloud": [
        "Multi-region failover design without cross-region write conflicts",
        "VPC endpoint patterns that eliminate NAT gateway egress cost",
        "Right-sizing compute with workload-aware autoscaling policies",
        "Designing for graceful degradation during zonal outages",
        "Managed service lock-in: where abstraction actually pays off",
        "Object storage lifecycle policies for hot and cold tiering",
        "Serverless cold start mitigation in latency-sensitive paths",
        "Cloud-native networking: service mesh versus native load balancing",
    ],
    "mlops": [
        "Model registry patterns for safe promotion across environments",
        "Detecting training-serving skew before it reaches production",
        "Shadow deployments for validating model changes on live traffic",
        "Feature store consistency between batch and online inference",
        "Automated retraining triggers driven by drift metrics",
        "Reproducible training pipelines with data and code versioning",
        "Inference batching strategies that balance latency and throughput",
        "Rollback strategies when a deployed model silently degrades",
    ],
    "rag": [
        "Hybrid retrieval: combining dense vectors with keyword search",
        "Reranking pipelines that measurably improve answer precision",
        "Handling stale context in continuously updated knowledge bases",
        "Query rewriting to recover recall on ambiguous user questions",
        "Citation and provenance tracking through a RAG pipeline",
        "Evaluating retrieval quality independently from generation quality",
        "Multi-tenant RAG with strict document-level access control",
        "Caching strategies for repeated retrieval across similar queries",
    ],
    "embeddings": [
        "Choosing embedding dimensionality against recall and cost tradeoffs",
        "Migrating an embedding model without full corpus re-indexing",
        "Normalization and distance metric selection in production search",
        "Detecting embedding drift as source content evolves",
        "Batch embedding pipelines that survive partial failure",
        "Domain adaptation: when fine-tuned embeddings beat general models",
        "Quantized embeddings for memory-constrained retrieval",
        "Versioning embeddings alongside the documents they represent",
    ],
    "chunking": [
        "Semantic chunking versus fixed-window splitting in real corpora",
        "Chunk overlap tuning and its measurable effect on retrieval",
        "Preserving table and code structure through document chunking",
        "Hierarchical chunking for long technical documentation",
        "Metadata enrichment at chunk boundaries for better filtering",
        "Chunk size selection driven by evaluation, not intuition",
        "Handling multi-format ingestion in a single chunking pipeline",
        "Incremental re-chunking when source documents change",
    ],
    "vector_databases": [
        "HNSW parameter tuning for recall versus query latency",
        "Index rebuild strategies without taking search offline",
        "Metadata filtering performance in high-cardinality workloads",
        "Sharding vector indexes across nodes for horizontal scale",
        "Choosing between IVF, HNSW, and flat indexes by workload shape",
        "Hybrid search implementation inside a single vector store",
        "Backup and disaster recovery for vector index state",
        "Memory versus disk-backed indexes and the cost implications",
    ],
    "ai_cloud_architecture": [
        "Designing GPU scheduling for bursty inference workloads",
        "Isolating AI workloads from transactional systems by blast radius",
        "Async orchestration patterns for long-running generation jobs",
        "Building resilient AI pipelines with checkpointing and replay",
        "Queue-based inference architectures under unpredictable load",
        "Observability design for non-deterministic AI systems",
        "Data residency constraints in distributed AI architectures",
        "Circuit breakers around third-party model provider dependencies",
    ],
    "cost_optimization": [
        "Cutting inference spend with semantic caching and dedup",
        "Spot and preemptible capacity for fault-tolerant batch workloads",
        "Model tiering: routing simple requests to cheaper models",
        "Storage cost reduction via compression and lifecycle policies",
        "Identifying idle and orphaned cloud resources at scale",
        "Reserved capacity planning against real utilization data",
        "Egress cost as an architectural constraint, not an afterthought",
        "Measuring cost per request as a first-class service metric",
    ],
    "performance_optimization": [
        "Connection pool sizing under real concurrency, not guesswork",
        "Eliminating N+1 query patterns in service boundaries",
        "Cache invalidation strategies that avoid thundering herds",
        "Profiling tail latency instead of optimizing the average",
        "Async I/O boundaries: where blocking calls silently cost you",
        "Index selection driven by actual query plan analysis",
        "Payload size reduction and its effect on end-to-end latency",
        "Backpressure design for services under sustained overload",
    ],
    "microservices": [
        "Service boundary design driven by data ownership",
        "Saga patterns versus distributed transactions in practice",
        "Idempotency keys as a prerequisite for safe retries",
        "Contract testing to catch breaking changes before deploy",
        "Event-driven choreography versus central orchestration",
        "Handling partial failure without cascading across services",
        "API versioning strategies that avoid coordinated releases",
        "Observability across service hops with correlation IDs",
    ],
    "software_engineering_best_practices": [
        "Designing for deletability: code that is cheap to remove",
        "Test pyramids that actually catch regressions worth catching",
        "Error handling as an API design decision, not an afterthought",
        "Refactoring under load without stopping feature delivery",
        "Dependency injection boundaries that keep tests fast",
        "Code review practices that scale past small teams",
        "Structured logging conventions that survive incident response",
        "Migration patterns for changing schemas on live systems",
    ],
    "ai_application_development": [
        "Designing human-in-the-loop checkpoints in agentic workflows",
        "State management for multi-step LLM applications",
        "Tool calling reliability: validation before execution",
        "Building AI features that degrade gracefully without the model",
        "Latency budgets for user-facing generative features",
        "Session and memory design in conversational applications",
        "Testing non-deterministic AI features in CI",
        "Rollout strategies for AI features with unclear success metrics",
    ],
}

# Fail fast at import time if the topic table and the whitelist ever diverge
assert set(TOPIC_CATEGORIES.keys()) == set(ALLOWED_DOMAINS), (
    "TOPIC_CATEGORIES keys must exactly match ALLOWED_DOMAINS. "
    f"Extra: {set(TOPIC_CATEGORIES) - set(ALLOWED_DOMAINS)}, "
    f"Missing: {set(ALLOWED_DOMAINS) - set(TOPIC_CATEGORIES)}"
)


def _current_week_start() -> datetime:
    """Get the most recent Monday at 00:00 UTC.

    Used to scope the intra-week diversity check. The agent publishes three
    times per week and each post must cover a different domain within that
    calendar week.

    Returns:
        Timezone-aware datetime for Monday 00:00 UTC of the current week
    """
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def select_topic_autonomously() -> tuple[str, str]:
    """Select a topic from the approved whitelist with intra-week diversity.

    Selection rules, in priority order:
    1. Only domains in ALLOWED_DOMAINS are eligible (hard constraint).
    2. Domains already used this calendar week are excluded (diversity).
    3. Topics already used in the last 100 posts are excluded (dedup).

    If every approved domain has been used this week, falls back to the
    least-recently-used domain and logs a warning rather than failing.

    Returns:
        Tuple of (selected_topic, category) where category is always a member
        of ALLOWED_DOMAINS

    Raises:
        Never raises on database failure - degrades to unfiltered selection
    """
    session_maker = get_session_maker()
    recent_topics: set[str] = set()
    used_this_week: set[str] = set()
    category_last_used: dict[str, datetime] = {}

    try:
        async with session_maker() as db:
            # Recent topics for cross-week deduplication
            stmt = (
                select(Post.topic)
                .where(Post.status.in_(["published", "queued"]))
                .order_by(desc(Post.created_at))
                .limit(100)
            )
            recent_posts = (await db.execute(stmt)).scalars().all()
            recent_topics = set(recent_posts) if recent_posts else set()

            # Domains already covered in the current calendar week
            week_start = _current_week_start()
            week_stmt = (
                select(Post.category, Post.created_at)
                .where(Post.status.in_(["published", "queued"]))
                .where(Post.created_at >= week_start)
                .where(Post.category.is_not(None))
            )
            week_rows = (await db.execute(week_stmt)).all()
            used_this_week = {row[0] for row in week_rows if row[0]}

            # Last-used timestamp per category, for the exhausted-week fallback
            lru_stmt = (
                select(Post.category, Post.created_at)
                .where(Post.category.is_not(None))
                .order_by(desc(Post.created_at))
                .limit(200)
            )
            for cat, created in (await db.execute(lru_stmt)).all():
                if cat and cat not in category_last_used:
                    category_last_used[cat] = created

    except Exception as e:
        logger.error(
            f"Failed to query post history: {str(e)}. "
            f"Proceeding without dedup or diversity filtering."
        )

    logger.info(
        f"Excluded {len(recent_topics)} recent topics | "
        f"Domains already used this week: {sorted(used_this_week) or 'none'}"
    )

    # Eligible domains: approved, and not already covered this week
    eligible = [d for d in ALLOWED_DOMAINS if d not in used_this_week]

    if not eligible:
        # Every approved domain used this week - pick least-recently-used
        eligible = sorted(
            ALLOWED_DOMAINS,
            key=lambda d: category_last_used.get(d, datetime.min.replace(tzinfo=timezone.utc)),
        )[:1]
        logger.warning(
            f"All {len(ALLOWED_DOMAINS)} approved domains already used this week. "
            f"Falling back to least-recently-used domain: {eligible[0]}"
        )

    # ENTROPY INJECTION: bias logging toward a random sample of eligible domains
    entropy_sample = random.sample(eligible, min(3, len(eligible)))
    logger.info(f"Entropy injection: eligible domain sample {entropy_sample}")

    # Find a topic not already used recently
    for attempt in range(20):
        category = random.choice(eligible)
        topic = random.choice(TOPIC_CATEGORIES[category])

        if topic not in recent_topics:
            logger.info(
                f"Selected topic (attempt {attempt + 1}): '{topic}' "
                f"from approved domain '{category}'"
            )
            return topic, category

    # Fallback: every sampled topic was recent (rare). Still whitelist-bound.
    category = random.choice(eligible)
    topic = random.choice(TOPIC_CATEGORIES[category])
    logger.warning(
        f"Could not find unique topic after 20 attempts. "
        f"Selected: '{topic}' from '{category}' (may be recent)"
    )
    return topic, category


async def topic_selection_node(state: dict) -> dict:
    """LangGraph node for autonomous topic selection.

    Runs at workflow start. Selects a topic and category from the approved
    domain whitelist, then returns updated state with both fields. This node
    is independent and can be tested in isolation.

    Args:
        state: LangGraph state (may be empty on first invocation)

    Returns:
        Updated state dict with:
            - topic: Selected topic string
            - selected_category: Approved domain key (member of ALLOWED_DOMAINS)
    """
    topic, category = await select_topic_autonomously()

    return {
        "topic": topic,
        "selected_category": category,
    }
