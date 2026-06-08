from collections import defaultdict, deque

from app.agents.curriculum.schema import CurriculumValidationResult
from app.schemas.roadmap import Roadmap


class CurriculumValidator:
    def validate(self, roadmap: Roadmap) -> CurriculumValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        node_ids = roadmap.node_ids()

        if not roadmap.nodes:
            errors.append("Roadmap must contain at least one node.")
        for edge in roadmap.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge source {edge.source} does not exist.")
            if edge.target not in node_ids:
                errors.append(f"Edge target {edge.target} does not exist.")

        if self._has_cycle(roadmap):
            errors.append("Roadmap DAG contains a cycle.")

        connected = {edge.source for edge in roadmap.edges} | {edge.target for edge in roadmap.edges}
        orphans = node_ids - connected
        if len(roadmap.nodes) > 1 and orphans:
            errors.append(f"Roadmap has orphan nodes: {sorted(orphans)}")

        difficulty_order = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
        levels = [difficulty_order.get(node.difficulty, 0) for node in roadmap.nodes]
        if levels != sorted(levels):
            warnings.append("Difficulty progression is not strictly non-decreasing.")

        for node in roadmap.nodes:
            if node.estimated_hours <= 0:
                errors.append(f"Node {node.id} must have positive estimated hours.")
            if not node.concepts:
                errors.append(f"Node {node.id} must include concepts.")
            if not node.success_criteria:
                errors.append(f"Node {node.id} must include success criteria.")

        return CurriculumValidationResult(valid=not errors, errors=errors, warnings=warnings)

    def _has_cycle(self, roadmap: Roadmap) -> bool:
        graph: dict[str, list[str]] = defaultdict(list)
        indegree = {node.id: 0 for node in roadmap.nodes}
        for edge in roadmap.edges:
            if edge.source in indegree and edge.target in indegree:
                graph[edge.source].append(edge.target)
                indegree[edge.target] += 1

        queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
        visited = 0
        while queue:
            node_id = queue.popleft()
            visited += 1
            for target in graph[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        return visited != len(indegree)
