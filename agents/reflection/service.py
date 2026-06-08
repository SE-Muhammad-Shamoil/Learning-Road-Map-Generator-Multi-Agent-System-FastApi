from app.agents.reflection.prompt import REFLECTION_PROMPT
from app.agents.reflection.schema import ReflectionOutput
from app.agents.validation.schema import LearnerProfile
from app.llm.router import LLMProvider, LLMRouter
from app.schemas.roadmap import Roadmap


class ReflectionAgent:
    name = "ReflectionAgent"

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    async def review(
        self,
        profile: LearnerProfile,
        roadmap: Roadmap,
    ) -> tuple[ReflectionOutput, object]:
        result, usage = await self.router.invoke_structured(
            agent_name=self.name,
            provider=LLMProvider.GEMINI,
            schema=ReflectionOutput,
            prompt=REFLECTION_PROMPT.format(
                profile=profile.model_dump(),
                roadmap=roadmap.model_dump(),
            ),
        )
        if result is not None:
            if result.reflection_score is None:
                result.reflection_score = result.score
            if not result.dependency_issues:
                result.dependency_issues = result.dependency_problems
            return result, usage

        issues: list[str] = []
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommendations: list[str] = []
        missing_topics: list[str] = []
        dependency_problems: list[str] = []
        timeline_problems: list[str] = []
        structural_critique: list[str] = []
        educational_critique: list[str] = []
        personalization_critique: list[str] = []
        titles = [node.title.lower() for node in roadmap.nodes]
        concepts = " ".join(" ".join(node.concepts).lower() for node in roadmap.nodes)
        node_ids = roadmap.node_ids()
        invalid_edges = [
            f"{edge.source}->{edge.target}"
            for edge in roadmap.edges
            if edge.source not in node_ids or edge.target not in node_ids or edge.source == edge.target
        ]
        if roadmap.nodes:
            strengths.append("Roadmap is decomposed into explicit learning nodes.")
        if roadmap.edges:
            strengths.append("Roadmap includes dependency edges for sequencing.")
        if len(titles) != len(set(titles)):
            issues.append("Duplicate roadmap node titles detected.")
            dependency_problems.append("Duplicate nodes reduce DAG clarity.")
            structural_critique.append("Duplicate titles weaken node identity.")
        if invalid_edges:
            issues.append("Invalid dependency edges detected.")
            dependency_problems.extend([f"Invalid edge {edge}." for edge in invalid_edges])
            structural_critique.append("Some dependencies point to missing or identical nodes.")
        if not roadmap.edges and len(roadmap.nodes) > 1:
            issues.append("Roadmap has multiple nodes but no dependency edges.")
            dependency_problems.append("Missing dependency edges.")
            structural_critique.append("DAG sequencing is underspecified.")
        if profile.normalized_goal.split()[0].lower() not in " ".join(titles + [concepts]):
            issues.append("Goal alignment could be made more explicit.")
            recommendations.append("Reference the target role in node descriptions or milestones.")
            personalization_critique.append("Goal language is not visible enough in the roadmap.")
        total_hours = sum(node.estimated_hours for node in roadmap.nodes)
        available_hours = profile.weekly_hours * profile.deadline_months * 4
        if total_hours > available_hours * 1.25:
            issues.append("Estimated workload exceeds available timeline.")
            timeline_problems.append("Reduce hours or extend duration.")
            personalization_critique.append("Timeline is too ambitious for the learner availability.")
        if "generative" in profile.normalized_goal.lower():
            required = {
                "llm": "LLM application design",
                "agent": "Agent orchestration",
                "evaluation": "Evaluation",
            }
            for signal, topic in required.items():
                if signal not in " ".join(titles) and signal not in concepts:
                    missing_topics.append(topic)

        if missing_topics:
            issues.append("Missing required topics for the requested goal.")
            recommendations.append("Add or revise nodes to cover missing target topics.")
            educational_critique.append("Coverage is missing required generative AI topics.")
        else:
            strengths.append("Core target topics are represented.")
        if len(roadmap.nodes) < 4:
            weaknesses.append("Roadmap may be too coarse for semester-level evaluation.")
            educational_critique.append("Add more granular learning milestones.")
        weaknesses.extend(issues)

        score = max(70, 96 - len(issues) * 10)
        return ReflectionOutput(
            approved=score >= 80,
            score=score,
            reflection_score=score,
            issues=issues,
            severity="high" if score < 75 else "medium" if issues else "low",
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            missing_topics=missing_topics,
            dependency_issues=dependency_problems,
            dependency_problems=dependency_problems,
            timeline_problems=timeline_problems,
            structural_critique=structural_critique or ["DAG structure is valid for current nodes."],
            educational_critique=educational_critique or ["Sequencing and coverage are acceptable."],
            personalization_critique=personalization_critique or ["Difficulty and timeline align with the learner profile."],
            revision_instructions=[
                *recommendations,
                *[f"Add coverage for {topic}." for topic in missing_topics],
                *dependency_problems,
                *timeline_problems,
            ],
        ), usage
