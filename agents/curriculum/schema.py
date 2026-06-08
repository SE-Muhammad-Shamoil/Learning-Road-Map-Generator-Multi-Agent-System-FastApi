from pydantic import BaseModel, Field

from app.schemas.roadmap import Roadmap


class CurriculumOutput(Roadmap):
    pass


class CurriculumValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
