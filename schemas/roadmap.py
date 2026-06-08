from pydantic import BaseModel, Field


class LearningResource(BaseModel):
    title: str
    url: str
    source: str
    summary: str
    resource_type: str
    confidence: float = Field(default=0.75, ge=0, le=1)


class YouTubeResource(BaseModel):
    title: str
    url: str
    channel: str
    duration_minutes: int


class NodeResources(BaseModel):
    youtube: list[LearningResource] = Field(default_factory=list)
    articles: list[LearningResource] = Field(default_factory=list)
    papers: list[LearningResource] = Field(default_factory=list)
    documentation: list[LearningResource] = Field(default_factory=list)


class RoadmapNode(BaseModel):
    id: str
    title: str
    description: str
    difficulty: str
    estimated_hours: int
    concepts: list[str] = Field(default_factory=list)
    deliverable: str
    success_criteria: list[str] = Field(default_factory=list)
    milestone: str | None = None


class RoadmapEdge(BaseModel):
    source: str
    target: str
    reason: str


class Roadmap(BaseModel):
    nodes: list[RoadmapNode]
    edges: list[RoadmapEdge]

    def node_ids(self) -> set[str]:
        return {node.id for node in self.nodes}
