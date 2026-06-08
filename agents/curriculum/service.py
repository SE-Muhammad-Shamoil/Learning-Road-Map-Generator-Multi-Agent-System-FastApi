import json

from app.agents.curriculum.prompt import CURRICULUM_PROMPT
from app.agents.curriculum.schema import CurriculumOutput
from app.agents.curriculum.validator import CurriculumValidator
from app.agents.planner.schema import PlannerOutput
from app.agents.validation.schema import LearnerProfile
from app.core.errors import AgentError
from app.llm.router import LLMProvider, LLMRouter
from app.schemas.roadmap import RoadmapEdge, RoadmapNode


class CurriculumAgent:
    name = "CurriculumAgent"

    def __init__(self, router: LLMRouter) -> None:
        self.router = router
        self.validator = CurriculumValidator()

    async def run(
        self,
        profile: LearnerProfile,
        plan: PlannerOutput,
    ) -> tuple[CurriculumOutput, object]:
        try:
            result, usage = await self.router.invoke_structured(
                agent_name=self.name,
                provider=LLMProvider.GEMINI,
                schema=CurriculumOutput,
                prompt=CURRICULUM_PROMPT.format(
                    profile=json.dumps(profile.model_dump()),
                    plan=json.dumps(plan.model_dump()),
                ),
            )
            if result is not None:
                validation = self.validator.validate(result)
                if validation.valid:
                    return result, usage
        except Exception as e:
            from app.core.observability import log_line
            log_line("CURRICULUM OUTPUT ERROR", error=str(e))
            usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)

        hours_per_node = max(12, plan.estimated_total_hours // max(len(plan.focus_areas), 1))
        titles = plan.focus_areas[:5]
        if not titles:
            titles = ["Core Fundamentals", "Intermediate Practice", "Advanced Concepts"]
            
        nodes = [
            RoadmapNode(
                id=f"n{i}",
                title=title,
                description=f"Build practical confidence in {title.lower()} for {profile.normalized_goal}.",
                difficulty=_difficulty(i),
                estimated_hours=hours_per_node,
                concepts=_concepts_for(title),
                deliverable=f"Complete a small portfolio artifact for {title}.",
                success_criteria=[
                    "Explain the main ideas clearly.",
                    "Complete an end-to-end exercise without step-by-step help.",
                    "Document tradeoffs and next steps.",
                ],
                milestone=plan.milestones[i - 1] if i - 1 < len(plan.milestones) else None,
            )
            for i, title in enumerate(titles, start=1)
        ]
        edges = [
            RoadmapEdge(
                source=f"n{i}",
                target=f"n{i + 1}",
                reason="Prerequisite knowledge feeds the next stage.",
            )
            for i in range(1, len(nodes))
        ]
        output = CurriculumOutput(nodes=nodes, edges=edges)
        validation = self.validator.validate(output)
        if not validation.valid:
            raise AgentError(self.name, "; ".join(validation.errors))
        return output, usage


def _difficulty(index: int) -> str:
    if index <= 2:
        return "Beginner"
    if index <= 4:
        return "Intermediate"
    return "Advanced"


def _concepts_for(title: str) -> list[str]:
    base = title.lower()
    if "langchain" in base or "langgraph" in base:
        return ["Chains", "tools", "state graphs", "agent orchestration"]
    if "llm" in base or "prompt" in base:
        return ["prompt design", "structured output", "function calling", "evaluation"]
    if "machine learning" in base:
        return ["supervised learning", "embeddings", "model evaluation", "data splits"]
    if "backend" in base or "python" in base:
        return ["Python typing", "FastAPI", "async APIs", "Pydantic"]
    return ["core concepts", "practice drills", "project structure", "review"]
