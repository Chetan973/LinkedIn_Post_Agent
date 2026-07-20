from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from app.agent.state import AgentState

SYSTEM_PROMPT = """You are an expert LinkedIn content strategist and backend engineer specializing in:
- Cloud infrastructure and distributed systems
- RESTful APIs and microservices architecture
- Generative AI and LLM applications
- Database optimization and scalability

Your task is to write highly technical, engaging, and professional LinkedIn posts that:
1. Educate and inspire the technical community
2. Share practical insights and lessons learned
3. Demonstrate expertise and thought leadership
4. Maintain a professional yet personable tone
5. Include relevant hashtags and call-to-action where appropriate

Write posts that are:
- Concise yet substantive (2-3 paragraphs)
- Technical but accessible
- Thought-provoking and actionable
- Professionally engaging"""


async def draft_post(state: AgentState) -> dict:
    """Draft a LinkedIn post based on the given topic."""
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)

    user_message = f"""Please write a technical LinkedIn post about the following topic:

Topic: {state['topic']}

Write a professional, engaging post that demonstrates expertise in backend engineering, cloud infrastructure, and/or Generative AI."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    response = await llm.ainvoke(messages)
    draft_text = response.content

    return {
        "draft_content": draft_text,
        "messages": [
            HumanMessage(content=user_message),
            AIMessage(content=draft_text),
        ],
        "status": "drafted",
    }


async def revise_post(state: AgentState) -> dict:
    """Revise the draft post based on user feedback."""
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)

    revision_prompt = f"""Please revise the following LinkedIn post based on the feedback provided:

Original Post:
{state['draft_content']}

User Feedback:
{state['feedback']}

Please incorporate the feedback and provide a revised version that maintains the technical quality and professional tone."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": revision_prompt},
    ]

    response = await llm.ainvoke(messages)
    revised_text = response.content

    return {
        "draft_content": revised_text,
        "messages": [
            HumanMessage(content=revision_prompt),
            AIMessage(content=revised_text),
        ],
        "status": "revised",
    }
