from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph state for the fully automated LinkedIn content agent.

    No status field needed - the workflow is linear: draft → publish → done.
    All error handling occurs at the background task level in posts.py.
    """
    messages: Annotated[list[AnyMessage], add_messages]
    post_id: int
    topic: str
    draft_content: str
    feedback: str
