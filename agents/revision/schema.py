from pydantic import BaseModel, Field

from app.schemas.roadmap import Roadmap


class RevisionDiff(BaseModel):
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    timeline_changes: list[str] = Field(default_factory=list)


class RevisionOutput(BaseModel):
    curriculum: Roadmap
    improvements: list[str] = Field(default_factory=list)
    consumed_instructions: list[str] = Field(default_factory=list)
    diff: RevisionDiff = Field(default_factory=RevisionDiff)
