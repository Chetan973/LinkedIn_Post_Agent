from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.agent.state import AgentState
from app.agent.nodes.topic_selection import topic_selection_node
from app.agent.nodes.draft import draft_post_node
from app.agent.nodes.thought_generation import thought_generation_node
from app.agent.nodes.validation import validate_content_node
from app.agent.nodes.image_rendering import image_rendering_node


def get_agent_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Create fully autonomous LinkedIn content agent workflow.

    Complete pipeline:
    1. Topic Selection (autonomous, deduplicated, category-diverse)
    2. Content Drafting (3000-3500 chars, technical depth)
    3. Thought Generation (20-35 words, image overlay)
    4. Validation (char count, formatting, dedup)
    5. Image Rendering (PIL template + text overlay)
    6. END

    Zero human intervention. All nodes are independent and stateless.
    Checkpointer enables state persistence and recovery.

    Args:
        checkpointer: Optional AsyncPostgresSaver for state persistence.
                     If None, creates one from DATABASE_URL.

    Returns:
        Compiled StateGraph for fully autonomous content generation.
    """
    if checkpointer is None:
        from app.db.database import _get_libpq_url
        libpq_url = _get_libpq_url()
        checkpointer = AsyncPostgresSaver.from_conn_string(libpq_url)

    # Create the state graph
    graph = StateGraph(AgentState)

    # Add all workflow nodes (each is independent and testable)
    graph.add_node("select_topic", topic_selection_node)
    graph.add_node("draft", draft_post_node)
    graph.add_node("generate_thought", thought_generation_node)
    graph.add_node("validate", validate_content_node)
    graph.add_node("render_image", image_rendering_node)

    # Define workflow edges (strictly linear, no conditionals for simplicity)
    graph.add_edge(START, "select_topic")
    graph.add_edge("select_topic", "draft")
    graph.add_edge("draft", "generate_thought")
    graph.add_edge("generate_thought", "validate")
    graph.add_edge("validate", "render_image")
    graph.add_edge("render_image", END)

    # Compile with checkpointer (no interrupts, fully automated)
    compiled_graph = graph.compile(checkpointer=checkpointer)

    return compiled_graph


# Backward compatibility aliases
async def get_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Async wrapper for get_agent_graph.

    For compatibility with async contexts and existing code.
    """
    return get_agent_graph(checkpointer=checkpointer)


def get_graph_sync(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Synchronous wrapper to get the compiled graph.

    For compatibility with sync contexts or testing.
    """
    return get_agent_graph(checkpointer=checkpointer)
