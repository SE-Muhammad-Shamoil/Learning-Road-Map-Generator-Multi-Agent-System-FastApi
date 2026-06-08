from pydantic import BaseModel, Field


class RoadmapRequest(BaseModel):
    goal: str = Field(..., min_length=2, examples=["Generative AI Engineer"])
    weekly_hours: int = Field(..., ge=1, le=80, examples=[15])
    deadline_months: int = Field(..., ge=1, le=60, examples=[6])
    experience_level: str = Field(..., examples=["Intermediate"])
    experience_description: str = Field(
        default="",
        examples=["I know Python and FastAPI."],
    )
    interests: str = Field(default="", examples=["LLMs, agents, backend systems"])
    learning_objectives: list[str] = Field(default_factory=list)
