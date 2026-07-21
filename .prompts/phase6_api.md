**Role:** You are an expert Python Backend Developer and FastAPI Engineer.

**Context:** Phase 5 is complete. Our LangGraph engine is highly technical, has a `StateGraph` wrapped in `get_agent_graph(checkpointer)`, and interrupts before the `revise_post` node. We are now building the FastAPI presentation layer using `BackgroundTasks` for asynchronous execution.

**Your Task:**
1. **app/api/schemas.py:** Create Pydantic DTOs:
   - `PostGenerateRequest`: `topic` (str)
   - `PostReviewRequest`: `feedback` (str), `status` (Literal["approved", "rejected", "needs_revision"])
   - `PostResponse`: `post_id` (int), `topic` (str), `status` (str), `draft_content` (Optional[str])

2. **app/api/dependencies.py:** 
   - `get_db()`: Async generator yielding our SQLAlchemy `AsyncSession`.
   - `get_checkpointer()`: Async generator yielding LangGraph's `AsyncPostgresSaver` initialized via `.from_conn_string(DATABASE_URL)`. 

3. **app/api/routers/posts.py:** Create the router with three endpoints:
   - `POST /generate`: Accepts `PostGenerateRequest`. Creates a new `Post` record in the database. Uses `BackgroundTasks` to trigger an async helper function `run_agent(post_id, topic, checkpointer)` and immediately returns `202 Accepted` with the `post_id`.
   - `POST /{post_id}/review`: Accepts `PostReviewRequest`. Updates the `Post` record in the database. Uses `BackgroundTasks` to trigger `resume_agent(post_id, feedback, status, checkpointer)` and returns `202 Accepted`.
   - `GET /{post_id}`: Returns the current `Post` database record as a `PostResponse`.
   - *Helper Note:* The `run_agent` and `resume_agent` background functions must instantiate the graph via `get_agent_graph(checkpointer)`, configure the `thread_id` to be the `post_id` (e.g., `{"configurable": {"thread_id": str(post_id)}}`), and invoke the graph state appropriately. Ensure they update the `Post` record's `draft_content` and `status` in the database when the graph yields.

4. **app/api/main.py:**
   - Initialize the `FastAPI` app instance.
   - Include the `posts` router with a `/api/v1/posts` prefix.

Execute these file creations cleanly. Ensure proper SQLAlchemy async patterns are used in the endpoints to avoid blocking the event loop.