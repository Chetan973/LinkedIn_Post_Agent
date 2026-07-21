from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings
from app.agent.state import AgentState
from app.agent.nodes import draft_post


def get_agent_graph(checkpointer: Optional[AsyncPostgresSaver] = None):
    """Create and compile the LinkedIn content agent graph.

    Fully automated workflow: draft_post → end
    No human-in-the-loop, no conditional routing, no pauses.

    Args:
        checkpointer: Optional AsyncPostgresSaver for state persistence.
                     If None, creates one from DATABASE_URL.

    Returns:
        Compiled StateGraph for fully automated content generation.
    """
    # Initialize checkpoint saver if not provided
    if checkpointer is None:
        checkpointer = AsyncPostgresSaver(settings.DATABASE_URL)

    # Create the state graph
    graph = StateGraph(AgentState)

    # Add single node for content generation
    graph.add_node("draft_post", draft_post)

    # Set entry point
    graph.set_entry_point("draft_post")

    # Direct edge from draft to end (fully automated, no branching)
    graph.add_edge("draft_post", END)

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
