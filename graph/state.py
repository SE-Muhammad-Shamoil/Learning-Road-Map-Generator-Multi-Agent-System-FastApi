from typing import TypedDict

from app.agents.curriculum.schema import CurriculumOutput
from app.agents.planner.schema import PlannerOutput
from app.agents.reflection.schema import ReflectionOutput
from app.agents.revision.schema import RevisionOutput
from app.agents.resource.schema import ResourceOutput
from app.agents.validation.schema import ValidationOutput
from app.core.errors import ErrorState
from app.core.observability import ExecutionTrace, LLMUsage, ToolTrace, TraceEvent
from app.schemas.request import RoadmapRequest


class RoadmapState(TypedDict, total=False):
    request_id: str
    execution_id: str
    user_input: RoadmapRequest
    user_profile: dict
    validation_result: ValidationOutput
    plan: PlannerOutput
    curriculum: CurriculumOutput
    reflection: ReflectionOutput
    resources: ResourceOutput
    revision_result: RevisionOutput
    execution_trace: list[str]
    structured_trace: list[ExecutionTrace]
    agent_trace: list[TraceEvent]
    tool_trace: list[ToolTrace]
    reasoning_trace: list[str]
    tool_calls: list[dict]
    tool_results: list[dict]
    tool_reasoning: list[str]
    reflection_history: list[dict]
    improvement_summary: dict
    error_state: ErrorState
    revision_count: int
    quality_score: int
    status: str
    next_node: str
    timestamps: dict[str, str]
    token_usage: dict[str, int]
    provider_usage: list[LLMUsage]
    revision_history: list[dict]
    scores_by_iteration: list[int]
    warnings: list[str]
