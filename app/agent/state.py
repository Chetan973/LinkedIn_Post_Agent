from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph state for the LinkedIn content automation agent."""

    messages: Annotated[list[AnyMessage], add_messages]
    post_id: int
    topic: str
    draft_content: str
    feedback: str
    status: str
