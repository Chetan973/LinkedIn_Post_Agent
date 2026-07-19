# LinkedIn_Post_Agent
FastAPI handles HTTP, Celery handles scheduling and queueing, PostgreSQL stores both business data and LangGraph's memory (checkpoints), and the agent directory isolates AI logic.  LangGraph manages the multi-step reasoning flow (Draft → Human Review → Edit → Finalize). Celery manages the system-level asynchronous execution.
