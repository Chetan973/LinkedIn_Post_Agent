from typing import Literal
from app.agent.state import AgentState


def route_post_state(state: AgentState) -> Literal["__end__", "draft_post", "revise_post"]:
    """Route the agent based on post approval status.

    Args:
        state: Current agent state containing status field

    Returns:
        Next node to execute:
        - "__end__": Post approved, workflow complete
        - "draft_post": Post rejected, start fresh draft
        - "revise_post": Post needs revision, apply feedback
    """
    status = state.get("status", "").lower()

    if status == "approved":
        return "__end__"
    elif status == "rejected":
        return "draft_post"
    elif status == "needs_revision":
        return "revise_post"
    else:
        return "draft_post"
