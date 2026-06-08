from collections.abc import AsyncIterator

from app.config.settings import get_settings
from app.core.observability import log_line, new_id, short_id, utc_now
from app.graph.builder import build_graph
from app.graph.response_mapper import to_public_response
from app.graph.state import RoadmapState
from app.schemas.request import RoadmapRequest
from app.schemas.response import RoadmapResponse


WORKFLOW_STORE: dict[str, RoadmapState] = {}


class RoadmapWorkflow:
    def __init__(self, interrupt_before: list[str] | None = None) -> None:
        self.settings = get_settings()
        self.graph = build_graph(self.settings, interrupt_before=interrupt_before)

    async def run(self, request: RoadmapRequest, request_id: str | None = None) -> RoadmapResponse:
        request_id = request_id or new_id("req")
        execution_id = new_id("exec")
        log_line(
            "WORKFLOW START",
            req=short_id(request_id),
            exec=short_id(execution_id),
            goal=request.goal,
            hours_per_week=request.weekly_hours,
            deadline_months=request.deadline_months,
        )
        initial_state: RoadmapState = {
            "request_id": request_id,
            "execution_id": execution_id,
            "user_input": request,
            "execution_trace": [],
            "structured_trace": [],
            "agent_trace": [],
            "tool_trace": [],
            "reasoning_trace": [],
            "tool_calls": [],
            "tool_results": [],
            "tool_reasoning": [],
            "revision_count": 0,
            "quality_score": 0,
            "status": "started",
            "timestamps": {"started": utc_now()},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "provider_usage": [],
            "revision_history": [],
            "reflection_history": [],
            "improvement_summary": {},
            "scores_by_iteration": [],
            "warnings": [],
        }
        state = await self.graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": request_id, "checkpoint_ns": self.settings.checkpoint_namespace}},
        )
        state = {
            **state,
            "timestamps": {**state.get("timestamps", {}), "finished": utc_now()},
        }
        nodes_generated = len(state.get("curriculum").nodes) if state.get("curriculum") is not None else 0
        resources_generated = 0
        if state.get("resources") is not None:
            resources_generated = sum(len(items) for items in state["resources"].resources.values())
        log_line(
            "WORKFLOW DONE ",
            req=short_id(request_id),
            exec=short_id(execution_id),
            status=state.get("status", "unknown"),
            duration_seconds=to_public_response(state).metadata.duration_seconds,
            iterations=len(state.get("scores_by_iteration", [])),
            nodes=nodes_generated,
            resources=resources_generated,
            revisions=state.get("revision_count", 0),
            score=state.get("quality_score", 0),
        )
        WORKFLOW_STORE[request_id] = state
        return to_public_response(state)

    async def stream(self, request: RoadmapRequest, request_id: str | None = None) -> AsyncIterator[dict]:
        request_id = request_id or new_id("req")
        execution_id = new_id("exec")
        log_line(
            "STREAM START",
            req=short_id(request_id),
            exec=short_id(execution_id),
            goal=request.goal,
        )
        initial_state: RoadmapState = {
            "request_id": request_id,
            "execution_id": execution_id,
            "user_input": request,
            "execution_trace": [],
            "structured_trace": [],
            "agent_trace": [],
            "tool_trace": [],
            "reasoning_trace": [],
            "tool_calls": [],
            "tool_results": [],
            "tool_reasoning": [],
            "revision_count": 0,
            "quality_score": 0,
            "status": "started",
            "timestamps": {"started": utc_now()},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "provider_usage": [],
            "revision_history": [],
            "reflection_history": [],
            "improvement_summary": {},
            "scores_by_iteration": [],
            "warnings": [],
        }
        async for event in self.graph.astream(
            initial_state,
            config={"configurable": {"thread_id": request_id, "checkpoint_ns": self.settings.checkpoint_namespace}},
        ):
            node_name = next(iter(event.keys()), "workflow") if isinstance(event, dict) and event else "workflow"
            yield {"status": "running", "node": node_name}
            
        state_tuple = await self.graph.aget_state({"configurable": {"thread_id": request_id}})
        state_values = dict(state_tuple.values)
        state_values = {
            **state_values,
            "timestamps": {**state_values.get("timestamps", {}), "finished": utc_now()},
        }
        
        nodes_generated = len(state_values.get("curriculum").nodes) if state_values.get("curriculum") is not None else 0
        resources_generated = 0
        if state_values.get("resources") is not None:
            resources_generated = sum(len(items) for items in state_values["resources"].resources.values())
            
        log_line(
            "STREAM DONE ",
            req=short_id(request_id),
            exec=short_id(execution_id),
            status=state_values.get("status", "unknown"),
            duration_seconds=to_public_response(state_values).metadata.duration_seconds,
            iterations=len(state_values.get("scores_by_iteration", [])),
            nodes=nodes_generated,
            resources=resources_generated,
            revisions=state_values.get("revision_count", 0),
            score=state_values.get("quality_score", 0),
        )
        WORKFLOW_STORE[request_id] = state_values
        yield to_public_response(state_values).model_dump()
