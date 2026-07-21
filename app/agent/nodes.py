import asyncio
import logging
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.state import AgentState
from app.core.config import settings
from app.Services.llm_fallback import FallbackLLM

logger = logging.getLogger(__name__)

llm_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM_CALLS)

SYSTEM_PROMPT = """You are a world-class backend engineer and technical thought leader specializing in:
- Cloud infrastructure, distributed systems, and scalability patterns
- RESTful APIs, microservices architecture, and system design
- Generative AI, LLMs, and advanced ML systems
- Database optimization, performance engineering, and reliability

Your task is to write HIGHLY TECHNICAL content with TECHNICAL MOTIVE THOUGHTS suited for advanced backend engineering audiences. Each post should:

1. Demonstrate deep technical expertise and insights
2. Share lessons learned from real-world backend engineering challenges
3. Provide actionable technical knowledge and best practices
4. Use precise technical terminology while remaining clear
5. Include practical examples, architectural patterns, or technical decisions

Writing style:
- 2-3 well-crafted paragraphs
- Lead with the core technical insight
- Include specific technical details (not generic)
- Reference relevant systems, patterns, or technologies
- End with a thought-provoking question or call-to-action
- Use relevant hashtags (#backend #engineering #systems etc.)
- Professional, authoritative, yet approachable tone

Focus on:
- Technical depth over breadth
- Real-world applicability
- Advanced audience (not entry-level)
- Original perspectives and insights
- Problem-solving and innovation"""


async def draft_post(state: AgentState) -> dict:
    """Draft a highly technical LinkedIn post based on the given topic.

    Produces original, deep technical content with technical motive thoughts
    suited for advanced backend engineering audiences.
    Enforces max concurrent LLM calls to prevent rate limit exhaustion.
    Uses Gemini 2.5 Flash with automatic Ollama fallback.
    """
    async with llm_semaphore:
        llm = FallbackLLM(temperature=0.7)

        user_message = f"""Write a HIGHLY TECHNICAL LinkedIn post about the following topic.
Focus on TECHNICAL MOTIVE THOUGHTS and deep engineering insights.

Topic: {state['topic']}

Requirements:
- Write for an ADVANCED backend engineering audience
- Include specific technical details and engineering principles
- Share lessons learned or insights from real-world systems
- Use precise technical terminology
- 2-3 well-crafted paragraphs
- Include hashtags and a call-to-action
- Professional, authoritative tone

Make this a standout technical post that demonstrates deep expertise and original thinking."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            response = await llm.ainvoke(messages)
            draft_text = response.content
            logger.info(f"Draft post created successfully for topic: {state['topic'][:50]}")
        except Exception as e:
            logger.error(f"Error drafting post for topic {state['topic']}: {str(e)}")
            raise

        return {
            "draft_content": draft_text,
            "messages": [
                HumanMessage(content=user_message),
                AIMessage(content=draft_text),
            ],
        }


async def revise_post(state: AgentState) -> dict:
    """Revise the draft post based on user feedback.

    Applies human feedback while maintaining technical depth and professional quality.
    Enforces max concurrent LLM calls to prevent rate limit exhaustion.
    Uses Gemini 2.5 Flash with automatic Ollama fallback.
    """
    async with llm_semaphore:
        llm = FallbackLLM(temperature=0.7)

        revision_prompt = f"""Please revise the following LinkedIn post based on the feedback provided.
Maintain the highly technical nature and technical motive thoughts.

Original Post:
{state['draft_content']}

User Feedback:
{state['feedback']}

Revise the post to address the feedback while:
- Preserving technical depth and accuracy
- Maintaining the advanced audience focus
- Keeping the professional, authoritative tone
- Ensuring the post remains engaging and actionable"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": revision_prompt},
        ]

        try:
            response = await llm.ainvoke(messages)
            revised_text = response.content
            logger.info("Post revision completed successfully")
        except Exception as e:
            logger.error(f"Error revising post: {str(e)}")
            raise

        return {
            "draft_content": revised_text,
            "messages": [
                HumanMessage(content=revision_prompt),
                AIMessage(content=revised_text),
            ],
        }