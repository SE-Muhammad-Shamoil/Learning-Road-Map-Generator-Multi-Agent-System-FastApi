from pydantic import BaseModel, Field


class ReflectionOutput(BaseModel):
    approved: bool
    score: int = Field(..., ge=0, le=100)
    reflection_score: int | None = Field(default=None, ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    severity: str = "low"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    missing_topics: list[str] = Field(default_factory=list)
    dependency_issues: list[str] = Field(default_factory=list)
    dependency_problems: list[str] = Field(default_factory=list)
    timeline_problems: list[str] = Field(default_factory=list)
    structural_critique: list[str] = Field(default_factory=list)
    educational_critique: list[str] = Field(default_factory=list)
    personalization_critique: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
