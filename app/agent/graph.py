from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import AsyncPostgresSaver
from app.core.config import settings
from app.agent.state import AgentState
from app.agent.nodes import draft_post, revise_post
from app.agent.edges import route_post_state


async def get_graph():
    """Create and compile the LinkedIn content agent graph with PostgreSQL checkpointing.

    Returns:
        Compiled StateGraph with AsyncPostgresSaver for state persistence in Supabase.
    """
    # Initialize checkpoint saver for Supabase
    saver = AsyncPostgresSaver(settings.DATABASE_URL)

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

    # Compile with AsyncPostgresSaver for secure checkpointing in Supabase
    compiled_graph = graph.compile(checkpointer=saver)

    return compiled_graph


def get_graph_sync():
    """Synchronous wrapper to get the compiled graph.

    Note: For async contexts, use `await get_graph()` directly.
    This is provided for compatibility with sync contexts.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(get_graph())
    finally:
        loop.close()
