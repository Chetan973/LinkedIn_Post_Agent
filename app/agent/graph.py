from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.agent.state import AgentState
from app.agent.nodes import draft_post, revise_post
from app.agent.edges import route_post_state


def get_agent_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Create and compile the LinkedIn content agent graph.

    This is a factory function that builds the StateGraph with optional
    dynamic checkpointer injection. It includes human-in-the-loop interrupts
    to pause before revision nodes for user approval.

    Args:
        checkpointer: Optional AsyncPostgresSaver for state persistence.
                     If None, creates one from DATABASE_URL.

    Returns:
        Compiled StateGraph with human-in-the-loop interrupts enabled.
    """
    # Initialize checkpoint saver if not provided
    if checkpointer is None:
        checkpointer = AsyncPostgresSaver(settings.DATABASE_URL)

    # Create the state graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("draft_post", draft_post)
    graph.add_node("revise_post", revise_post)

    # Set entry point
    graph.set_entry_point("draft_post")

    # Add conditional edges for routing based on status
    graph.add_conditional_edges(
        "draft_post",
        route_post_state,
        {
            "draft_post": "draft_post",
            "revise_post": "revise_post",
            "__end__": END,
        },
    )

    graph.add_conditional_edges(
        "revise_post",
        route_post_state,
        {
            "draft_post": "draft_post",
            "revise_post": "revise_post",
            "__end__": END,
        },
    )

    # Compile with checkpointer and human-in-the-loop interrupts
    # interrupt_before pauses BEFORE executing revise_post node
    # This ensures user can review the draft before any revisions are applied
    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["revise_post"],
    )

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
