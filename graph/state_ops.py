from app.core.observability import ExecutionTrace, LLMUsage, ToolTrace, TraceEvent, utc_now
from app.graph.state import RoadmapState


def append_trace(state: RoadmapState, message: str) -> list[str]:
    return [*state.get("execution_trace", []), message]


def append_structured_trace(
    state: RoadmapState,
    node: str,
    event_type: str,
    metadata: dict | None = None,
) -> list[ExecutionTrace]:
    return [
        *state.get("structured_trace", []),
        ExecutionTrace(node=node, event_type=event_type, metadata=metadata or {}),
    ]


def append_agent_trace(state: RoadmapState, event: TraceEvent) -> list[TraceEvent]:
    return [*state.get("agent_trace", []), event]


def append_provider_usage(state: RoadmapState, usage: LLMUsage) -> list[LLMUsage]:
    return [*state.get("provider_usage", []), usage]


def append_tool_trace(state: RoadmapState, traces: list[ToolTrace]) -> list[ToolTrace]:
    return [*state.get("tool_trace", []), *traces]


def stamp(state: RoadmapState, key: str) -> dict[str, str]:
    return {**state.get("timestamps", {}), key: utc_now()}
