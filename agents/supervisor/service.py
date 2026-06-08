from app.agents.supervisor.schema import SupervisorDecision
from app.config.settings import Settings
from app.graph.state import RoadmapState


class Supervisor:
    name = "Supervisor"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(self, state: RoadmapState) -> SupervisorDecision:
        if state.get("error_state") is not None:
            return SupervisorDecision(next_node="error", reason="Error state present.")
        validation = state.get("validation_result")
        if validation is not None and not validation.valid:
            return SupervisorDecision(next_node="end", reason="Validation rejected request.")
        if validation is None:
            return SupervisorDecision(next_node="end", reason="Validation result missing.")
        if state.get("plan") is None:
            return SupervisorDecision(next_node="planner", reason="Plan has not been created.")
        if state.get("curriculum") is None:
            return SupervisorDecision(next_node="curriculum", reason="Curriculum has not been created.")

        reflection = state.get("reflection")
        if reflection is None:
            return SupervisorDecision(next_node="reflection", reason="Curriculum needs quality review.")

        revision_count = state.get("revision_count", 0)
        if reflection.approved:
            return SupervisorDecision(next_node="resource", reason="Reflection approved roadmap.")
        if revision_count >= self.settings.reflection_max_iterations:
            return SupervisorDecision(
                next_node="resource",
                reason="Reflection max iterations reached; returning best attempt with warnings.",
            )
        return SupervisorDecision(next_node="revision", reason="Reflection requested revision.")
