import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.logging import configure_logging, get_request_id

logger = logging.getLogger("roadmap_generator")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def short_id(value: str, length: int = 8) -> str:
    if "_" in value:
        value = value.rsplit("_", 1)[-1]
    return value[:length]


def clean_value(value: object) -> str:
    text = str(value)
    return " ".join(text.split())


def log_line(title: str, **fields: object) -> None:
    fields.pop("req", None)
    fields.pop("exec", None)
    
    if "error" in fields:
        err_msg = fields.pop("error")
        msg = f"✖ [{title}] Error: {err_msg}"
        if fields:
            msg += f" (Context: {fields})"
        logger.error(msg)
    else:
        extra = f" | {fields}" if fields else ""
        logger.info(f"▶ [{title}]{extra}")


def log_step_start(request_id: str, agent: str) -> None:
    logger.info(f"▶ [{agent.upper()}] Starting execution...")


def log_step_end(
    request_id: str,
    agent: str,
    *,
    status: str,
    latency_ms: float | None = None,
    **fields: object,
) -> None:
    ms_text = f" in {latency_ms:.1f}ms" if latency_ms is not None else ""
    fields.pop("req", None)
    fields.pop("exec", None)
    extra = f" | Context: {fields}" if fields else ""
    
    if status.lower() == "success":
        logger.info(f"✔ [{agent.upper()}] Completed{ms_text}{extra}")
    else:
        logger.warning(f"⚠ [{agent.upper()}] Finished with status: {status}{ms_text}{extra}")


def log_step_error(
    request_id: str,
    agent: str,
    *,
    message: str,
    latency_ms: float | None = None,
) -> None:
    ms_text = f" after {latency_ms:.1f}ms" if latency_ms is not None else ""
    logger.error(f"✖ [{agent.upper()}] Failed{ms_text}: {message}")


class TraceEvent(BaseModel):
    request_id: str
    execution_id: str
    agent: str
    event: str
    message: str
    timestamp: str = Field(default_factory=utc_now)
    latency_ms: float | None = None
    metadata: dict = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    timestamp: str = Field(default_factory=utc_now)
    node: str
    event_type: str
    metadata: dict = Field(default_factory=dict)


class ToolTrace(BaseModel):
    tool_name: str
    arguments: dict
    result_summary: str
    execution_time_ms: float
    success: bool
    timestamp: str = Field(default_factory=utc_now)
    error: str | None = None


class ToolExecutionLog(ToolTrace):
    pass


class AgentExecutionLog(TraceEvent):
    pass


class ReflectionLog(BaseModel):
    request_id: str
    execution_id: str
    iteration: int
    score: int = Field(..., ge=0, le=100)
    approved: bool
    weaknesses: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_now)


class LLMUsage(BaseModel):
    agent: str
    provider: str
    model: str
    used_live_llm: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0


class Timer:
    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


def trace(
    *,
    request_id: str,
    execution_id: str,
    agent: str,
    event: str,
    message: str,
    latency_ms: float | None = None,
    metadata: dict | None = None,
) -> TraceEvent:
    entry = TraceEvent(
        request_id=request_id,
        execution_id=execution_id,
        agent=agent,
        event=event,
        message=message,
        latency_ms=latency_ms,
        metadata=metadata or {},
    )
    return entry
