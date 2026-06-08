from collections.abc import Awaitable, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.agents.curriculum.service import CurriculumAgent
from app.agents.planner.service import PlannerAgent
from app.agents.reflection.service import ReflectionAgent
from app.agents.resource.service import ResourceAgent
from app.agents.revision.service import RevisionAgent
from app.agents.supervisor.service import Supervisor
from app.agents.validation.service import ValidationAgent
from app.config.settings import Settings, get_settings
from app.core.errors import to_error_state
from app.core.observability import Timer, log_line, log_step_end, log_step_error, log_step_start, trace
from app.graph.state import RoadmapState
from app.graph.state_ops import (
    append_agent_trace,
    append_provider_usage,
    append_structured_trace,
    append_tool_trace,
    append_trace,
    stamp,
)
from app.llm.router import LLMRouter

NodeFn = Callable[[RoadmapState], Awaitable[RoadmapState]]


NODE_CONTRACTS: dict[str, dict[str, set[str]]] = {
    "ValidationAgent": {"inputs": {"user_input"}, "outputs": {"validation_result", "status"}},
    "Supervisor": {"inputs": {"validation_result"}, "outputs": {"next_node"}},
    "PlannerAgent": {"inputs": {"validation_result"}, "outputs": {"plan"}},
    "CurriculumAgent": {"inputs": {"validation_result", "plan"}, "outputs": {"curriculum"}},
    "ReflectionAgent": {"inputs": {"validation_result", "curriculum"}, "outputs": {"reflection", "quality_score"}},
    "RevisionAgent": {"inputs": {"validation_result", "curriculum", "reflection"}, "outputs": {"revision_result", "curriculum"}},
    "ResourceAgent": {"inputs": {"curriculum"}, "outputs": {"resources"}},
}


def _event(state: RoadmapState, agent: str, event: str, message: str, latency_ms: float | None = None):
    return trace(
        request_id=state["request_id"],
        execution_id=state["execution_id"],
        agent=agent,
        event=event,
        message=message,
        latency_ms=latency_ms,
    )


def _safe(agent_name: str, func: NodeFn) -> NodeFn:
    async def wrapped(state: RoadmapState) -> RoadmapState:
        log_step_start(state["request_id"], agent_name)
        with Timer() as timer:
            try:
                _validate_contract(agent_name, state, "inputs")
                state = {
                    **state,
                    "structured_trace": append_structured_trace(
                        state,
                        agent_name,
                        "node_started",
                        {"required_inputs": sorted(NODE_CONTRACTS.get(agent_name, {}).get("inputs", set()))},
                    ),
                }
                update = await func(state)
                _validate_contract(agent_name, update, "outputs")
                log_step_end(
                    state["request_id"],
                    agent_name,
                    status=update.get("status", state.get("status", "ok")),
                    latency_ms=timer.elapsed_ms,
                )
                event = _event(state, agent_name, "completed", f"{agent_name} completed", timer.elapsed_ms)
                return {
                    **update,
                    "agent_trace": append_agent_trace(update, event),
                    "structured_trace": append_structured_trace(
                        update,
                        agent_name,
                        "node_completed",
                        {"generated_outputs": sorted(NODE_CONTRACTS.get(agent_name, {}).get("outputs", set()))},
                    ),
                    "timestamps": stamp(update, agent_name),
                }
            except Exception as error:
                error_state = to_error_state(error, agent_name)
                failed_state: RoadmapState = {
                    **state,
                    "status": "failed",
                    "error_state": error_state,
                    "execution_trace": append_trace(state, f"{agent_name} failed: {error_state.message}"),
                    "structured_trace": append_structured_trace(
                        state,
                        agent_name,
                        "node_failed",
                        {"error": error_state.message, "error_type": error_state.error_type},
                    ),
                    "timestamps": stamp(state, f"{agent_name}_failed"),
                }
                log_step_error(
                    state["request_id"],
                    agent_name,
                    message=error_state.message,
                    latency_ms=timer.elapsed_ms,
                )
                event = _event(failed_state, agent_name, "failed", error_state.message, timer.elapsed_ms)
                return {
                    **failed_state,
                    "agent_trace": append_agent_trace(failed_state, event),
                }

    return wrapped


def _validate_contract(agent_name: str, state: RoadmapState, direction: str) -> None:
    required = NODE_CONTRACTS.get(agent_name, {}).get(direction, set())
    missing = [field for field in required if state.get(field) is None]
    if missing:
        from app.core.errors import AgentExecutionError

        raise AgentExecutionError(agent_name, f"{direction} contract missing fields: {', '.join(sorted(missing))}")


def build_graph(settings: Settings | None = None, interrupt_before: list[str] | None = None):
    settings = settings or get_settings()
    router = LLMRouter()
    supervisor_agent = Supervisor(settings)
    validation = ValidationAgent(router)
    planner = PlannerAgent(router)
    curriculum = CurriculumAgent(router)
    reflection = ReflectionAgent(router)
    revision = RevisionAgent(router)
    resource = ResourceAgent(router, settings)

    async def validate(state: RoadmapState) -> RoadmapState:
        output, usage = await validation.run(state["user_input"])
        status = "validated" if output.valid else "validation_failed"
        log_line(
            "VALIDATION",
            req=state["request_id"],
            valid=output.valid,
            goal=output.normalized_goal,
            difficulty=output.difficulty,
            confidence=f"{output.confidence:.2f}",
            warnings=len(output.warnings),
            risks=len(output.risks),
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        return {
            **state,
            "validation_result": output,
            "user_profile": output.profile.model_dump(),
            "status": status,
            "warnings": [*state.get("warnings", []), *output.warnings, *output.risks],
            "provider_usage": append_provider_usage(state, usage),
            "execution_trace": append_trace(state, "Validation Agent completed"),
        }

    async def supervisor(state: RoadmapState) -> RoadmapState:
        decision = supervisor_agent.decide(state)
        log_line(
            "ROUTE     ",
            req=state["request_id"],
            next=decision.next_node,
            reason=decision.reason,
        )
        return {
            **state,
            "next_node": decision.next_node,
            "execution_trace": append_trace(state, f"Supervisor routed to {decision.next_node}: {decision.reason}"),
        }

    async def plan(state: RoadmapState) -> RoadmapState:
        output, usage = await planner.run(state["validation_result"].profile)
        log_line(
            "PLANNER   ",
            req=state["request_id"],
            domain=output.domain,
            actions=", ".join(output.actions),
            focus_areas=len(output.focus_areas),
            gaps=len(output.skill_gaps),
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        return {
            **state,
            "plan": output,
            "reasoning_trace": [*state.get("reasoning_trace", []), *output.reasoning_trace],
            "provider_usage": append_provider_usage(state, usage),
            "status": "planned",
            "execution_trace": append_trace(state, "Planner Agent completed ReAct loop"),
        }

    async def build_curriculum(state: RoadmapState) -> RoadmapState:
        output, usage = await curriculum.run(state["validation_result"].profile, state["plan"])
        log_line(
            "CURRICULUM",
            req=state["request_id"],
            nodes=len(output.nodes),
            edges=len(output.edges),
            hours=sum(node.estimated_hours for node in output.nodes),
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        return {
            **state,
            "curriculum": output,
            "provider_usage": append_provider_usage(state, usage),
            "status": "curriculum_created",
            "execution_trace": append_trace(state, "Curriculum Agent produced validated DAG"),
        }

    async def reflect(state: RoadmapState) -> RoadmapState:
        output, usage = await reflection.review(state["validation_result"].profile, state["curriculum"])
        scores = [*state.get("scores_by_iteration", []), output.score]
        iteration = len(scores)
        reflection_entry = {
            "iteration": iteration,
            "score": output.score,
            "feedback": {
                "strengths": output.strengths,
                "weaknesses": output.weaknesses,
                "missing_topics": output.missing_topics,
                "dependency_issues": output.dependency_issues or output.dependency_problems,
                "revision_instructions": output.revision_instructions,
            },
            "changes_applied": None,
        }
        log_line(
            "REFLECTION",
            req=state["request_id"],
            approved=output.approved,
            score=output.score,
            severity=output.severity,
            weaknesses="; ".join(output.weaknesses[:3]),
            issues=len(output.issues),
            missing=len(output.missing_topics),
            iteration=iteration,
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        log_line(
            "REFLECTION LOOP",
            req=state["request_id"],
            iteration=iteration,
            score=output.score,
            approved=output.approved,
            weaknesses="; ".join(output.weaknesses[:3]),
        )
        return {
            **state,
            "reflection": output,
            "quality_score": output.score,
            "scores_by_iteration": scores,
            "reflection_history": [*state.get("reflection_history", []), reflection_entry],
            "provider_usage": append_provider_usage(state, usage),
            "status": "reflection_approved" if output.approved else "reflection_needs_revision",
            "execution_trace": append_trace(state, f"Reflection Agent scored roadmap {output.score}"),
        }

    async def revise(state: RoadmapState) -> RoadmapState:
        output, usage = await revision.run(
            state["validation_result"].profile,
            state["curriculum"],
            state["reflection"],
        )
        history_entry = {
            "iteration": state.get("revision_count", 0) + 1,
            "improvements": output.improvements,
            "consumed_instructions": output.consumed_instructions,
            "diff": output.diff.model_dump(),
            "score_before": state.get("quality_score", 0),
        }
        reflection_history = [*state.get("reflection_history", [])]
        if reflection_history:
            reflection_history[-1] = {
                **reflection_history[-1],
                "changes_applied": output.diff.model_dump(),
            }
        log_line(
            "REVISION  ",
            req=state["request_id"],
            iteration=history_entry["iteration"],
            improvements=len(output.improvements),
            instructions=len(output.consumed_instructions),
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        return {
            **state,
            "curriculum": output.curriculum,
            "revision_result": output,
            "revision_count": state.get("revision_count", 0) + 1,
            "revision_history": [*state.get("revision_history", []), history_entry],
            "reflection_history": reflection_history,
            "reflection": None,
            "provider_usage": append_provider_usage(state, usage),
            "status": "revised",
            "execution_trace": append_trace(state, "Revision Agent consumed reflection instructions"),
        }

    async def add_resources(state: RoadmapState) -> RoadmapState:
        output, usage, tool_traces = await resource.run(state["curriculum"])
        successful_tools = sum(1 for item in tool_traces if item.success)
        failed_tools = sum(1 for item in tool_traces if not item.success)
        resource_count = sum(len(items) for items in output.resources.values())
        log_line(
            "RESOURCES ",
            req=state["request_id"],
            nodes=len(output.resources),
            resources=resource_count,
            tools_ok=successful_tools,
            tools_failed=failed_tools,
            provider=usage.provider,
            live_llm=usage.used_live_llm,
        )
        return {
            **state,
            "curriculum": output.curriculum,
            "resources": output,
            "provider_usage": append_provider_usage(state, usage),
            "tool_trace": append_tool_trace(state, tool_traces),
            "tool_calls": [*state.get("tool_calls", []), *output.tool_calls],
            "tool_results": [*state.get("tool_results", []), *output.tool_results],
            "tool_reasoning": [*state.get("tool_reasoning", []), *output.tool_reasoning],
            "improvement_summary": _improvement_summary(state),
            "status": "completed" if state.get("error_state") is None else "completed_with_warnings",
            "execution_trace": append_trace(state, "Resource Agent attached tool results"),
        }

    async def end_node(state: RoadmapState) -> RoadmapState:
        log_line("WORKFLOW END", req=state["request_id"], status=state.get("status", "completed"))
        return {
            **state,
            "status": state.get("status", "completed"),
            "execution_trace": append_trace(state, "Workflow ended"),
        }

    async def error_node(state: RoadmapState) -> RoadmapState:
        error_state = state.get("error_state")
        log_line(
            "WORKFLOW ERROR",
            req=state["request_id"],
            agent=error_state.agent if error_state else "unknown",
            message=error_state.message if error_state else "unknown error",
        )
        return {
            **state,
            "status": "failed",
            "execution_trace": append_trace(state, "Workflow routed to error terminal"),
        }

    def route(state: RoadmapState) -> str:
        return state.get("next_node", "error")

    def _improvement_summary(state: RoadmapState) -> dict:
        scores = state.get("scores_by_iteration", [])
        revisions = state.get("revision_history", [])
        cycles = []
        for index, revision_entry in enumerate(revisions, start=1):
            before = scores[index - 1] if index - 1 < len(scores) else revision_entry.get("score_before", 0)
            after = scores[index] if index < len(scores) else before
            revision_entry["score_after"] = after
            cycles.append(
                {
                    "iteration": index,
                    "score_before": before,
                    "score_after": after,
                    "delta": after - before,
                    "changes_applied": revision_entry.get("diff", {}),
                }
            )
        return {
            "initial_score": scores[0] if scores else 0,
            "final_score": scores[-1] if scores else state.get("quality_score", 0),
            "total_delta": (scores[-1] - scores[0]) if len(scores) > 1 else 0,
            "cycles": cycles,
        }

    retry = RetryPolicy(max_attempts=2, retry_on=Exception)
    graph = StateGraph(RoadmapState)
    graph.add_node("validation", _safe("ValidationAgent", validate), retry_policy=retry)
    graph.add_node("supervisor", _safe("Supervisor", supervisor), retry_policy=retry)
    graph.add_node("planner", _safe("PlannerAgent", plan), retry_policy=retry)
    graph.add_node("curriculum", _safe("CurriculumAgent", build_curriculum), retry_policy=retry)
    graph.add_node("reflection", _safe("ReflectionAgent", reflect), retry_policy=retry)
    graph.add_node("revision", _safe("RevisionAgent", revise), retry_policy=retry)
    graph.add_node("resource", _safe("ResourceAgent", add_resources), retry_policy=retry)
    graph.add_node("end", end_node)
    graph.add_node("error", error_node)

    graph.add_edge(START, "validation")
    graph.add_edge("validation", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route,
        {
            "planner": "planner",
            "curriculum": "curriculum",
            "reflection": "reflection",
            "revision": "revision",
            "resource": "resource",
            "end": "end",
            "error": "error",
        },
    )
    graph.add_edge("planner", "supervisor")
    graph.add_edge("curriculum", "supervisor")
    graph.add_edge("reflection", "supervisor")
    graph.add_edge("revision", "supervisor")
    graph.add_edge("resource", END)
    graph.add_edge("end", END)
    graph.add_edge("error", END)

    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        name="roadmap_generator_supervisor_graph",
    )
