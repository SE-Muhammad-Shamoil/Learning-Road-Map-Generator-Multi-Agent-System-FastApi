from pydantic import BaseModel, Field


class LearnerProfile(BaseModel):
    goal: str
    normalized_goal: str
    weekly_hours: int
    deadline_months: int
    experience_level: str
    experience_description: str
    interests: list[str] = Field(
        default_factory=list,
        description="List of interests extracted from the input string.",
    )
    learning_objectives: list[str] = Field(
        default_factory=list,
        description="List of learning objectives extracted from the input.",
    )


class ValidationOutput(BaseModel):
    valid: bool
    normalized_goal: str
    difficulty: str
    profile: LearnerProfile
    warnings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_duration_months: int
    confidence: float = Field(..., ge=0, le=1)
