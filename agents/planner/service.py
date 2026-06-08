import json

from app.agents.planner.prompt import PLANNER_ACTION_PROMPT, PLANNER_PROMPT
from app.agents.planner.schema import PlannerAction, PlannerObservation, PlannerOutput
from app.agents.planner.tools import PlannerTools
from app.agents.validation.schema import LearnerProfile
from app.core.observability import log_line
from app.llm.router import LLMProvider, LLMRouter


class PlannerAgent:
    name = "PlannerAgent"

    def __init__(self, router: LLMRouter) -> None:
        self.router = router
        self.tools = PlannerTools()

    async def run(self, profile: LearnerProfile, max_steps: int = 6) -> tuple[PlannerOutput, object]:
        observations, decision_usage = await self._react(profile, max_steps=max_steps)
        try:
            result, usage = await self.router.invoke_structured(
                agent_name=self.name,
                provider=LLMProvider.GEMINI,
                schema=PlannerOutput,
                prompt=PLANNER_PROMPT.format(
                    profile=json.dumps(profile.model_dump()),
                    observations=json.dumps([item.model_dump() for item in observations]),
                ),
            )
            usage.prompt_tokens += decision_usage.prompt_tokens
            usage.completion_tokens += decision_usage.completion_tokens
            usage.latency_ms += decision_usage.latency_ms
            usage.used_live_llm = usage.used_live_llm or decision_usage.used_live_llm
            if result is not None and result.observations:
                return result, usage
        except Exception as e:
            log_line("PLANNER OUTPUT ERROR", error=str(e))
            usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)

        tool_results = {item.action: item.observation for item in observations}
        domain = tool_results.get("domain_classifier", {}).get("domain", "general_technology")
        gaps = tool_results.get("skill_gap_analysis", {}).get("gaps", ["Portfolio-grade capstone depth"])
        difficulty = tool_results.get("difficulty_estimator", {}).get("difficulty", "Intermediate")
        stages = tool_results.get("roadmap_template_lookup", {}).get(
            "stages",
            self.tools.roadmap_template_lookup(domain, difficulty)["stages"],
        )
        trace = []
        for item in observations:
            trace.extend(
                [
                    f"Thought: {item.thought}",
                    f"Action: {item.action}({item.action_input})",
                    f"Observation: {item.observation}",
                ]
            )
        output = PlannerOutput(
            domain=domain,
            learning_path=f"{profile.normalized_goal} {difficulty} path",
            starting_level=profile.experience_level,
            focus_areas=stages,
            skill_gaps=gaps,
            milestones=[f"Milestone: demonstrate {stage.lower()}" for stage in stages],
            estimated_total_hours=profile.weekly_hours * profile.deadline_months * 4,
            thoughts=[item.thought for item in observations],
            actions=[item.action for item in observations],
            observations=[item.observation for item in observations],
            reasoning_trace=trace,
            tool_results=tool_results,
            max_steps=max_steps,
            final_plan={
                "domain": domain,
                "difficulty": difficulty,
                "stages": stages,
                "gaps": gaps,
            },
        )
        return output, usage

    async def _react(self, profile: LearnerProfile, max_steps: int) -> tuple[list[PlannerObservation], object]:
        steps: list[PlannerObservation] = []
        usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)
        for _ in range(max_steps):
            action, action_usage = await self._choose_action(profile, steps)
            usage.used_live_llm = usage.used_live_llm or action_usage.used_live_llm
            usage.latency_ms += action_usage.latency_ms
            if action.action == "Finish":
                break
            observation = self._execute_action(profile, action.action, action.action_input, steps)
            log_line(
                "PLANNER REACT",
                step=len(steps) + 1,
                thought=action.thought,
                action=action.action,
                observation=observation,
            )
            steps.append(
                PlannerObservation(
                    thought=action.thought,
                    action=action.action,
                    action_input=action.action_input,
                    observation=observation,
                )
            )
            if {step.action for step in steps} >= {
                "domain_classifier",
                "skill_gap_analysis",
                "difficulty_estimator",
                "roadmap_template_lookup",
            }:
                finish, finish_usage = await self._choose_action(profile, steps)
                usage.used_live_llm = usage.used_live_llm or finish_usage.used_live_llm
                usage.latency_ms += finish_usage.latency_ms
                if finish.action == "Finish":
                    break
        return steps, usage

    async def _choose_action(
        self,
        profile: LearnerProfile,
        steps: list[PlannerObservation],
    ) -> tuple[PlannerAction, object]:
        try:
            result, usage = await self.router.invoke_structured(
                agent_name=self.name,
                provider=LLMProvider.GEMINI,
                schema=PlannerAction,
                prompt=PLANNER_ACTION_PROMPT.format(
                    profile=json.dumps(profile.model_dump()),
                    observations=json.dumps([step.model_dump() for step in steps]),
                ),
            )
            if result is not None and result.action in {
                "domain_classifier",
                "skill_gap_analysis",
                "difficulty_estimator",
                "roadmap_template_lookup",
                "Finish",
            }:
                return result, usage
        except Exception as e:
            log_line("PLANNER ACTION ERROR", error=str(e))
            usage = self.router.usage(self.name, LLMProvider.GEMINI, used_live_llm=False)
            
        return self._fallback_action(profile, steps), usage

    def _fallback_action(self, profile: LearnerProfile, steps: list[PlannerObservation]) -> PlannerAction:
        completed = {step.action for step in steps}
        observations = {step.action: step.observation for step in steps}
        if "domain_classifier" not in completed:
            return PlannerAction(
                thought="Need to determine the learner domain before planning.",
                action="domain_classifier",
                action_input={"goal": profile.normalized_goal, "interests": profile.interests},
            )
        if "skill_gap_analysis" not in completed:
            return PlannerAction(
                thought="Need prerequisite and skill-gap evidence for this domain.",
                action="skill_gap_analysis",
                action_input={
                    "domain": observations["domain_classifier"]["domain"],
                    "experience": profile.experience_description,
                },
            )
        if "difficulty_estimator" not in completed:
            return PlannerAction(
                thought="Need difficulty and time-pressure estimate before selecting stages.",
                action="difficulty_estimator",
                action_input={
                    "weekly_hours": profile.weekly_hours,
                    "deadline_months": profile.deadline_months,
                    "gap_count": len(observations["skill_gap_analysis"]["gaps"]),
                },
            )
        if "roadmap_template_lookup" not in completed:
            return PlannerAction(
                thought="Need a domain-specific roadmap template to ground the curriculum.",
                action="roadmap_template_lookup",
                action_input={
                    "domain": observations["domain_classifier"]["domain"],
                    "difficulty": observations["difficulty_estimator"]["difficulty"],
                },
            )
        return PlannerAction(
            thought="All required observations are available; finish with the final plan.",
            action="Finish",
            action_input={},
        )

    def _execute_action(
        self,
        profile: LearnerProfile,
        action: str,
        action_input: dict,
        steps: list[PlannerObservation],
    ) -> dict:
        observations = {step.action: step.observation for step in steps}
        if action == "domain_classifier":
            return self.tools.domain_classifier(profile)
        if action == "skill_gap_analysis":
            domain = action_input.get("domain") or observations.get("domain_classifier", {}).get("domain")
            return self.tools.skill_gap_analysis(profile, domain or "general_technology")
        if action == "difficulty_estimator":
            gaps = observations.get("skill_gap_analysis", {}).get("gaps", [])
            return self.tools.difficulty_estimator(profile, gaps)
        if action == "roadmap_template_lookup":
            domain = action_input.get("domain") or observations.get("domain_classifier", {}).get("domain")
            difficulty = action_input.get("difficulty") or observations.get("difficulty_estimator", {}).get("difficulty")
            return self.tools.roadmap_template_lookup(domain or "general_technology", difficulty or "Intermediate")
        return {}
