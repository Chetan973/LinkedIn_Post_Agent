**Role:** You are an expert Python Backend Developer and LangGraph Engineer.

**Context:** Phase 4 is complete, and our Supabase database is ready. We are now building the LangGraph AI Engine. We will deploy this as a stateless service, so the Postgres checkpointer is critical.

**Your Task:**
1. **app/agent/state.py:** Define `AgentState` as a `TypedDict` containing:
   - `messages` (using `Annotated[list[AnyMessage], add_messages]`)
   - `post_id` (int)
   - `topic` (str)
   - `draft_content` (str)
   - `feedback` (str)
   - `status` (str)

2. **app/agent/nodes.py:** Create the core async nodes. Use `ChatGoogleGenerativeAI` or `ChatOpenAI`.
   - `draft_post(state: AgentState)`: A function that looks at `state["topic"]` and drafts a post. The system prompt MUST instruct the LLM to write "highly technical content and technical motive thoughts" in the voice of a Senior Software Engineer specializing in scalable Azure, Devops, AWS infrastructure, Langchain agent, Langraph Multiagentic AI, RAG Models and GenAI integration. The tone should be authoritative but accessible. The node must return the updated `draft_content` AND set `status` to `"pending_review"`.
   - `revise_post(state: AgentState)`: Takes `state["draft_content"]` and `state["feedback"]`. Instruct the LLM to apply the human feedback to revise the draft. Return the updated `draft_content` and set `status` to `"pending_review"`.

3. **app/agent/edges.py:** Create a routing function `route_post_state(state: AgentState)`:
   - If `state["status"] == "approved"`, return `END` (from `langgraph.graph`).
   - If `state["status"] == "rejected"`, return `"draft_post"`.
   - If `state["status"] == "needs_revision"`, return `"revise_post"`.
   - Otherwise, return `END`.

4. **app/agent/graph.py:** Compile the `StateGraph`.
   - Initialize a `StateGraph(AgentState)`.
   - Add nodes: `draft_post` and `revise_post`.
   - Add conditional edges from `draft_post` and `revise_post` using `route_post_state`.
   - Wrap the compilation in a factory function `def get_agent_graph(checkpointer=None):` so we can dynamically inject the `AsyncPostgresSaver` from FastAPI. 
   - Ensure the graph compiles with `interrupt_after=["draft_post", "revise_post"]` to strictly enforce our Human-in-the-Loop pause before posting.

Execute these file creations cleanly. Do not modify the database models or FastAPI files yet.