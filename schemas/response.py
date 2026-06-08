from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ErrorState
from app.core.observability import ExecutionTrace, LLMUsage, ToolTrace, TraceEvent
from app.schemas.roadmap import LearningResource, RoadmapEdge, RoadmapNode


class RoadmapMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iterations: int = 0
    duration_seconds: float = 0
    generated_at: str


class FrontendRoadmap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    nodes: list[RoadmapNode] = Field(default_factory=list)
    edges: list[RoadmapEdge] = Field(default_factory=list)
    resources: dict[str, list[LearningResource]] = Field(default_factory=dict)


class RoadmapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message: str | None = None
    roadmap: FrontendRoadmap | None = None
    metadata: RoadmapMetadata


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "error"
    error_code: str
    message: str
    request_id: str


class DebugWorkflowResponse(BaseModel):
    request_id: str
    execution_id: str
    status: str
    execution_trace: list[str] = Field(default_factory=list)
    structured_trace: list[ExecutionTrace] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list)
    tool_reasoning: list[str] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    agent_trace: list[TraceEvent] = Field(default_factory=list)
    provider_usage: list[LLMUsage] = Field(default_factory=list)
    reflection_history: list[dict] = Field(default_factory=list)
    revision_history: list[dict] = Field(default_factory=list)
    improvement_summary: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: ErrorState | None = None


class HealthResponse(BaseModel):
    status: str


class MetricsResponse(BaseModel):
    status: str
    checkpointing: str
    external_tools_enabled: bool
    completed_workflows: int = 0
