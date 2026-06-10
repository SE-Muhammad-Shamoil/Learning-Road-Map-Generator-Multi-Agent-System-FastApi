from datetime import UTC, datetime

from app.graph.state import RoadmapState
from app.schemas.response import DebugWorkflowResponse, FrontendRoadmap, RoadmapMetadata, RoadmapResponse


def to_public_response(state: RoadmapState) -> RoadmapResponse:
    resources = state.get("resources")
    curriculum = state.get("curriculum")
    validation = state.get("validation_result")
    roadmap = None
    if curriculum is not None:
        title = validation.normalized_goal if validation is not None else state["user_input"].goal
        roadmap = FrontendRoadmap(
            title=title,
            nodes=curriculum.nodes,
            edges=curriculum.edges,
            resources=resources.resources if resources is not None else {},
        )
    started = _parse_time(state.get("timestamps", {}).get("started"))
    finished = _parse_time(state.get("timestamps", {}).get("finished")) or datetime.now(UTC)
    duration = max(0.0, (finished - started).total_seconds()) if started else 0.0
    
    status = _public_status(state.get("status", "unknown"))
    message = None
    
    if status == "validation_failed" and validation:
        reasons = validation.warnings + validation.risks
        if reasons:
            message = "Validation Failed: " + " | ".join(reasons)
        else:
            message = "The requested goal is too broad or invalid. Please refine it."
            
    # Calculate used models and if any is a less powerful / economy model
    used_models = []
    is_less_powerful = False
    for usage in state.get("provider_usage", []):
        if usage.used_live_llm and usage.model:
            used_models.append(usage.model)
            if usage.model.lower() in {
                "gpt-4o-mini",
                "llama-3.1-8b-instant",
                "llama-3.3-70b-versatile",
                "codestral",
                "gemini-3.1-flash-lite",
            }:
                is_less_powerful = True

    # Deduplicate models
    seen = set()
    deduped_models = []
    for m in used_models:
        if m not in seen:
            seen.add(m)
            deduped_models.append(m)

    return RoadmapResponse(
        status=status,
        message=message,
        roadmap=roadmap,
        metadata=RoadmapMetadata(
            iterations=len(state.get("scores_by_iteration", [])),
            duration_seconds=round(duration, 3),
            generated_at=finished.isoformat(),
            is_less_powerful_model_used=is_less_powerful,
            used_models=deduped_models,
        ),
    )


def to_debug_response(state: RoadmapState) -> DebugWorkflowResponse:
    return DebugWorkflowResponse(
        request_id=state["request_id"],
        execution_id=state["execution_id"],
        status=state.get("status", "unknown"),
        execution_trace=state.get("execution_trace", []),
        structured_trace=state.get("structured_trace", []),
        reasoning_trace=state.get("reasoning_trace", []),
        tool_calls=state.get("tool_calls", []),
        tool_results=state.get("tool_results", []),
        tool_reasoning=state.get("tool_reasoning", []),
        tool_trace=state.get("tool_trace", []),
        agent_trace=state.get("agent_trace", []),
        provider_usage=state.get("provider_usage", []),
        reflection_history=state.get("reflection_history", []),
        revision_history=state.get("revision_history", []),
        improvement_summary=state.get("improvement_summary", {}),
        warnings=state.get("warnings", []),
        error=state.get("error_state"),
    )


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _public_status(status: str) -> str:
    if status == "completed":
        return "success"
    if status == "validation_failed":
        return "validation_failed"
    if status == "failed":
        return "error"
    return status
