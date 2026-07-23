"""Production instrumentation for execution tracing.

Provides:
- Correlation IDs for request tracing
- Structured logging for all functions
- HTTP request/response logging
- Elapsed time tracking
- Exception capture with full context
"""

import logging
import time
import uuid
import json
from functools import wraps
from typing import Any, Callable, Optional
from contextlib import asynccontextmanager
import contextvars

logger = logging.getLogger(__name__)

# Context variable for correlation ID (thread-safe)
correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    current_id = correlation_id.get()
    if not current_id:
        current_id = str(uuid.uuid4())[:8]
        correlation_id.set(current_id)
    return current_id


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for request tracking."""
    correlation_id.set(cid)


def create_context_logger(name: str) -> logging.LoggerAdapter:
    """Create logger with automatic correlation ID injection."""
    base_logger = logging.getLogger(name)

    class CorrelationLoggerAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            cid = get_correlation_id()
            if "extra" not in kwargs:
                kwargs["extra"] = {}
            kwargs["extra"]["correlation_id"] = cid
            return f"[{cid}] {msg}", kwargs

    return CorrelationLoggerAdapter(base_logger, {})


def instrument_function(func: Callable) -> Callable:
    """Decorator to instrument synchronous functions with logging.

    Logs:
    - Function entry with parameters
    - Elapsed time
    - Return value
    - Exceptions with full traceback
    """
    logger_inst = create_context_logger(func.__module__)

    @wraps(func)
    def wrapper(*args, **kwargs):
        cid = get_correlation_id()
        func_name = f"{func.__module__}.{func.__name__}"

        # Sanitize kwargs for logging (remove auth tokens)
        logged_kwargs = {
            k: v if not _is_sensitive(k) else "***"
            for k, v in kwargs.items()
        }

        logger_inst.info(
            f"ENTER: {func_name}",
            extra={
                "function": func_name,
                "args_count": len(args),
                "kwargs": logged_kwargs,
            }
        )

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Log return value (but not large objects)
            result_preview = _preview_value(result)
            logger_inst.info(
                f"EXIT: {func_name}",
                extra={
                    "function": func_name,
                    "return_value": result_preview,
                    "elapsed_ms": int(elapsed * 1000),
                }
            )
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger_inst.error(
                f"EXCEPTION: {func_name}",
                exc_info=True,
                extra={
                    "function": func_name,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "elapsed_ms": int(elapsed * 1000),
                }
            )
            raise

    return wrapper


def instrument_async_function(func: Callable) -> Callable:
    """Decorator to instrument async functions with logging.

    Logs:
    - Async function entry with parameters
    - Elapsed time
    - Return value
    - Exceptions with full traceback
    """
    logger_inst = create_context_logger(func.__module__)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        cid = get_correlation_id()
        func_name = f"{func.__module__}.{func.__name__}"

        # Sanitize kwargs for logging
        logged_kwargs = {
            k: v if not _is_sensitive(k) else "***"
            for k, v in kwargs.items()
        }

        logger_inst.info(
            f"ASYNC ENTER: {func_name}",
            extra={
                "function": func_name,
                "args_count": len(args),
                "kwargs": logged_kwargs,
            }
        )

        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time

            result_preview = _preview_value(result)
            logger_inst.info(
                f"ASYNC EXIT: {func_name}",
                extra={
                    "function": func_name,
                    "return_value": result_preview,
                    "elapsed_ms": int(elapsed * 1000),
                }
            )
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger_inst.error(
                f"ASYNC EXCEPTION: {func_name}",
                exc_info=True,
                extra={
                    "function": func_name,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                    "elapsed_ms": int(elapsed * 1000),
                }
            )
            raise

    return async_wrapper


@asynccontextmanager
async def log_async_operation(operation_name: str, **extra_context):
    """Context manager for logging async operations.

    Usage:
        async with log_async_operation("image_upload", image_size=12345):
            # do async work
    """
    logger_inst = create_context_logger(__name__)
    start_time = time.time()

    logger_inst.info(
        f"START: {operation_name}",
        extra={"operation": operation_name, **extra_context}
    )

    try:
        yield
    except Exception as e:
        elapsed = time.time() - start_time
        logger_inst.error(
            f"FAILED: {operation_name}",
            exc_info=True,
            extra={
                "operation": operation_name,
                "elapsed_ms": int(elapsed * 1000),
                "exception": str(e),
            }
        )
        raise
    else:
        elapsed = time.time() - start_time
        logger_inst.info(
            f"COMPLETE: {operation_name}",
            extra={
                "operation": operation_name,
                "elapsed_ms": int(elapsed * 1000),
            }
        )


def log_http_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    payload: Optional[Any] = None,
    **extra
) -> None:
    """Log HTTP request details."""
    logger_inst = create_context_logger(__name__)

    # Sanitize headers (remove auth)
    safe_headers = {}
    if headers:
        for k, v in headers.items():
            if not _is_sensitive(k):
                safe_headers[k] = v

    # Truncate large payloads
    payload_preview = _preview_value(payload)

    logger_inst.info(
        f"HTTP REQUEST: {method} {url}",
        extra={
            "http_method": method,
            "http_url": url[:100],
            "http_headers": safe_headers,
            "http_payload": payload_preview,
            **extra,
        }
    )


def log_http_response(
    status_code: int,
    headers: Optional[dict] = None,
    body: Optional[str] = None,
    elapsed_ms: int = 0,
    **extra
) -> None:
    """Log HTTP response details."""
    logger_inst = create_context_logger(__name__)

    # Sanitize headers
    safe_headers = {}
    if headers:
        for k, v in headers.items():
            if not _is_sensitive(k):
                safe_headers[k] = str(v)

    body_preview = body[:500] if body else None

    logger_inst.info(
        f"HTTP RESPONSE: {status_code}",
        extra={
            "http_status": status_code,
            "http_headers": safe_headers,
            "http_body_preview": body_preview,
            "http_elapsed_ms": elapsed_ms,
            **extra,
        }
    )


def _is_sensitive(key: str) -> bool:
    """Check if a key contains sensitive data."""
    sensitive_keywords = [
        "auth", "token", "password", "secret", "key",
        "credential", "bearer", "api_key", "access_token"
    ]
    return any(kw in key.lower() for kw in sensitive_keywords)


def _preview_value(value: Any, max_length: int = 200) -> Any:
    """Get a preview of a value for logging."""
    if value is None:
        return None

    if isinstance(value, (str, bytes)):
        s = str(value)
        if len(s) > max_length:
            return f"{s[:max_length]}... ({len(s)} chars)"
        return s

    if isinstance(value, (dict, list)):
        try:
            s = json.dumps(value, default=str)
            if len(s) > max_length:
                return f"<{type(value).__name__} {len(s)} chars>"
            return value
        except Exception as json_error:
            # JSON serialization failed - return type info instead
            return f"<{type(value).__name__} (json error: {type(json_error).__name__})>"

    return f"<{type(value).__name__}>"
