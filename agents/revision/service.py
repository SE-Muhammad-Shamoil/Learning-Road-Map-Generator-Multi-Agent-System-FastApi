from copy import deepcopy

from app.agents.reflection.schema import ReflectionOutput
from app.agents.revision.prompt import REVISION_PROMPT
from app.agents.revision.schema import RevisionDiff, RevisionOutput
from app.agents.validation.schema import LearnerProfile
from app.llm.router import LLMProvider, LLMRouter
from app.schemas.roadmap import Roadmap, RoadmapEdge, RoadmapNode


class RevisionAgent:
    name = "RevisionAgent"

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    async def run(
        self,
        profile: LearnerProfile,
        curriculum: Roadmap,
        reflection: ReflectionOutput,
    ) -> tuple[RevisionOutput, object]:
        result, usage = await self.router.invoke_structured(
            agent_name=self.name,
            provider=LLMProvider.GEMINI,
            schema=RevisionOutput,
            prompt=REVISION_PROMPT.format(
                reflection=reflection.model_dump(),
                curriculum=curriculum.model_dump(),
            ),
        )
        if result is not None:
            if result.diff is None:
                result.diff = self._diff(curriculum, result.curriculum)
            return result, usage

        revised = deepcopy(curriculum)
        improvements: list[str] = []
        instructions = reflection.revision_instructions

        for node in revised.nodes:
            node.description = f"For {profile.normalized_goal}: {node.description}"

        existing_text = " ".join(
            [node.title.lower() for node in revised.nodes]
            + [concept.lower() for node in revised.nodes for concept in node.concepts]
        )
        for missing in reflection.missing_topics:
            if missing.lower().split()[0] not in existing_text:
                new_id = f"n{len(revised.nodes) + 1}"
                previous_id = revised.nodes[-1].id if revised.nodes else "n1"
                revised.nodes.append(
                    RoadmapNode(
                        id=new_id,
                        title=missing,
                        description=f"Close missing coverage for {profile.normalized_goal}.",
                        difficulty="Intermediate",
                        estimated_hours=max(8, profile.weekly_hours),
                        concepts=[missing, "hands-on practice", "evaluation checklist"],
                        deliverable=f"Mini-project demonstrating {missing.lower()}.",
                        success_criteria=[
                            f"Explain {missing.lower()} tradeoffs.",
                            "Produce a tested, documented artifact.",
                        ],
                        milestone=f"Milestone: demonstrate {missing.lower()}",
                    )
                )
                if previous_id != new_id:
                    revised.edges.append(
                        RoadmapEdge(
                            source=previous_id,
                            target=new_id,
                            reason="Added from reflection missing-topic instruction.",
                        )
                    )
                revised.nodes[-1].milestone = f"Milestone: demonstrate {missing.lower()}"
                improvements.append(f"Added missing topic node: {missing}")

        if reflection.timeline_problems:
            for node in revised.nodes:
                before = node.estimated_hours
                node.estimated_hours = max(6, int(node.estimated_hours * 0.9))
                if before != node.estimated_hours:
                    improvements.append(f"Adjusted {node.id} from {before}h to {node.estimated_hours}h.")
            improvements.append("Reduced estimated node hours for timeline realism.")

        if reflection.dependency_problems and len(revised.nodes) > 1 and not revised.edges:
            for index in range(len(revised.nodes) - 1):
                revised.edges.append(
                    RoadmapEdge(
                        source=revised.nodes[index].id,
                        target=revised.nodes[index + 1].id,
                        reason="Added to restore prerequisite sequencing from reflection feedback.",
                    )
                )
            improvements.append("Added dependency edges to restore DAG sequencing.")

        if not improvements and instructions:
            improvements.append("Rewrote node descriptions to strengthen goal alignment.")

        return RevisionOutput(
            curriculum=revised,
            improvements=improvements,
            consumed_instructions=instructions,
            diff=self._diff(curriculum, revised),
        ), usage

    def _diff(self, before: Roadmap, after: Roadmap) -> RevisionDiff:
        before_nodes = {node.id: node for node in before.nodes}
        after_nodes = {node.id: node for node in after.nodes}
        before_edges = {f"{edge.source}->{edge.target}" for edge in before.edges}
        after_edges = {f"{edge.source}->{edge.target}" for edge in after.edges}
        timeline_changes = []
        for node_id, after_node in after_nodes.items():
            before_node = before_nodes.get(node_id)
            if before_node and before_node.estimated_hours != after_node.estimated_hours:
                timeline_changes.append(
                    f"{node_id}: {before_node.estimated_hours}h -> {after_node.estimated_hours}h"
                )
        return RevisionDiff(
            added_nodes=sorted(set(after_nodes) - set(before_nodes)),
            removed_nodes=sorted(set(before_nodes) - set(after_nodes)),
            added_edges=sorted(after_edges - before_edges),
            removed_edges=sorted(before_edges - after_edges),
            timeline_changes=timeline_changes,
        )
