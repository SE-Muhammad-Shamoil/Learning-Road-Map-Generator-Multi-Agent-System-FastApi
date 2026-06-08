from pydantic import BaseModel, Field


class PlannerObservation(BaseModel):
    thought: str
    action: str
    action_input: dict
    observation: dict


class PlannerAction(BaseModel):
    thought: str
    action: str
    action_input: dict = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    domain: str
    learning_path: str
    starting_level: str
    focus_areas: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
    estimated_total_hours: int
    thoughts: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    observations: list[dict] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    tool_results: dict[str, dict] = Field(default_factory=dict)
    max_steps: int = 6
    final_plan: dict = Field(default_factory=dict)
