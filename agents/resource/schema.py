from pydantic import BaseModel, Field

from app.schemas.roadmap import LearningResource, Roadmap


class ResourceOutput(BaseModel):
    curriculum: Roadmap
    resources: dict[str, list[LearningResource]] = Field(default_factory=dict)
    tool_calls: list[dict] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list)
    tool_reasoning: list[str] = Field(default_factory=list)


class ResourceToolDecision(BaseModel):
    thought: str
    tools: list[str] = Field(default_factory=list)
    quality_threshold: float = 0.6
    retry_with: list[str] = Field(default_factory=list)
