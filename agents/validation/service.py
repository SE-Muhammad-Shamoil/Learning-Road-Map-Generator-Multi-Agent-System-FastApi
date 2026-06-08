from app.agents.validation.prompt import VALIDATION_PROMPT
from app.agents.validation.schema import LearnerProfile, ValidationOutput
from app.llm.router import LLMProvider, LLMRouter
from app.schemas.request import RoadmapRequest


class ValidationAgent:
    name = "ValidationAgent"

    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    async def run(self, user_input: RoadmapRequest) -> tuple[ValidationOutput, object]:
        try:
            result, usage = await self.router.invoke_structured(
                agent_name=self.name,
                provider=LLMProvider.GEMINI,
                schema=ValidationOutput,
                prompt=VALIDATION_PROMPT.format(user_input=user_input.model_dump()),
            )
            if result is not None:
                return result, usage
        except Exception:
            # Fall back to heuristic validation
            pass
        
        from app.core.observability import LLMUsage
        usage = LLMUsage(agent=self.name, provider=LLMProvider.GEMINI.value, model="fallback", used_live_llm=False)

        interests = [
            item.strip()
            for item in user_input.interests.replace(";", ",").split(",")
            if item.strip()
        ]
        normalized_goal = " ".join(user_input.goal.strip().split()).title()
        warnings: list[str] = []
        risks: list[str] = []
        valid = True

        if len(user_input.goal.strip()) < 4:
            valid = False
            risks.append("Goal is too vague to generate a useful roadmap.")
        if user_input.weekly_hours < 3:
            warnings.append("Weekly hours are low; progress will be slow.")
        total_hours = user_input.weekly_hours * user_input.deadline_months * 4
        if total_hours < 80:
            risks.append("Timeline may be too compressed for the requested goal.")
        if user_input.experience_level.lower() not in {"beginner", "intermediate", "advanced"}:
            warnings.append("Experience level was normalized from a custom value.")

        difficulty = _difficulty(user_input.experience_level, total_hours)
        recommended = max(user_input.deadline_months, 4 if difficulty == "Beginner" else 6)
        output = ValidationOutput(
            valid=valid,
            normalized_goal=normalized_goal,
            difficulty=difficulty,
            profile=LearnerProfile(
                goal=user_input.goal,
                normalized_goal=normalized_goal,
                weekly_hours=user_input.weekly_hours,
                deadline_months=user_input.deadline_months,
                experience_level=user_input.experience_level,
                experience_description=user_input.experience_description,
                interests=interests,
                learning_objectives=user_input.learning_objectives,
            ),
            warnings=warnings,
            risks=risks,
            recommended_duration_months=recommended,
            confidence=0.9 if valid else 0.35,
        )
        return output, usage


def _difficulty(experience_level: str, total_hours: int) -> str:
    level = experience_level.lower()
    if level == "advanced" and total_hours >= 120:
        return "Advanced"
    if level == "intermediate" or total_hours >= 160:
        return "Intermediate"
    return "Beginner"
