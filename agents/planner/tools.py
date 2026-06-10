from pydantic import BaseModel, Field
from app.agents.validation.schema import LearnerProfile
from app.llm.router import LLMProvider, LLMRouter


class DomainClassifierOutput(BaseModel):
    domain: str = Field(description="A clean, lowercase slug representing the career/learning domain (e.g., 'culinary_arts', 'generative_ai', 'music_production', 'frontend_development').")
    signals: list[str] = Field(description="List of specific key terms, interests, or objectives from the profile that support this domain classification.")


class SkillGapAnalysisOutput(BaseModel):
    gaps: list[str] = Field(description="List of specific, concrete skill gaps based on the user's career goal and their current experience description. Gaps should be highly relevant to the goal. For non-technical or vocational fields (e.g., cooking, baking, digital marketing, learning an instrument), do NOT recommend technical software engineering skills like Python or FastAPI unless the profile explicitly requires it.")


class RoadmapTemplateLookupOutput(BaseModel):
    stages: list[str] = Field(description="A sequential list of 4 to 6 logical sequential stages/phases for a learning roadmap, customized to the domain and target difficulty level.")
    difficulty: str = Field(description="The difficulty level (Beginner, Intermediate, Advanced).")


DOMAIN_CLASSIFIER_PROMPT = """
You are a domain classifier helper.
Classify the learning goal into a highly descriptive, lowercase domain slug (e.g., 'culinary_arts', 'generative_ai', 'music_production', 'frontend_development').
Identify which signals (key terms, interests, or objectives) from the profile support this domain.

Profile:
Goal: {goal}
Interests: {interests}
Learning Objectives: {learning_objectives}
"""

SKILL_GAP_ANALYSIS_PROMPT = """
You are an expert career skills analyst.
Analyze the learner's profile and identify exactly what gaps they need to bridge to achieve their goal.
Compare the target goal/domain with the learner's current experience level and experience description.
Generate a list of 2 to 5 highly relevant, concrete skill gaps.
Do NOT suggest generic or irrelevant technical skills (e.g., do not suggest 'Python fluency' if the goal is cooking, baking, digital marketing, or playing guitar, unless they specifically mention wanting to use programming in that context).

Profile:
Goal: {goal}
Domain: {domain}
Experience Level: {experience_level}
Experience Description: {experience_description}
"""

ROADMAP_TEMPLATE_LOOKUP_PROMPT = """
You are a master curriculum strategist.
Create a standard set of 4 to 6 logical sequential stages/phases for a learning roadmap in the given domain, tailored for the target difficulty level.
Example stages for backend engineering might be: "Python service design", "FastAPI and async APIs", "Testing and observability", "Data and integration patterns", "Production hardening".
Example stages for culinary arts might be: "Kitchen safety and knife fundamentals", "Dry and moist heat cooking techniques", "Sauce prep and flavor profiling", "Advanced menu execution", "Kitchen management and menu planning".

Provide a high-quality, customized progression of stages for:
Domain: {domain}
Difficulty: {difficulty}
"""


class PlannerTools:
    def __init__(self, router: LLMRouter) -> None:
        self.router = router

    async def domain_classifier(self, profile: LearnerProfile) -> dict:
        try:
            prompt = DOMAIN_CLASSIFIER_PROMPT.format(
                goal=profile.normalized_goal,
                interests=", ".join(profile.interests),
                learning_objectives=", ".join(getattr(profile, "learning_objectives", []) or []),
            )
            result, _ = await self.router.invoke_structured(
                agent_name="PlannerAgent",
                provider=LLMProvider.GEMINI,
                schema=DomainClassifierOutput,
                prompt=prompt,
            )
            if result is not None:
                return {
                    "domain": result.domain,
                    "signals": result.signals,
                }
        except Exception:
            pass

        # Fallback to local heuristic
        goal = profile.normalized_goal.lower()
        if any(term in goal for term in ["ai", "llm", "generative", "agent"]):
            domain = "generative_ai"
        elif any(term in goal for term in ["backend", "api", "fastapi"]):
            domain = "backend_engineering"
        else:
            domain = "general_technology"
        return {
            "domain": domain,
            "signals": [profile.normalized_goal, *profile.interests],
        }

    async def skill_gap_analysis(self, profile: LearnerProfile, domain: str) -> dict:
        try:
            prompt = SKILL_GAP_ANALYSIS_PROMPT.format(
                goal=profile.normalized_goal,
                domain=domain,
                experience_level=profile.experience_level,
                experience_description=profile.experience_description,
            )
            result, _ = await self.router.invoke_structured(
                agent_name="PlannerAgent",
                provider=LLMProvider.GEMINI,
                schema=SkillGapAnalysisOutput,
                prompt=prompt,
            )
            if result is not None:
                return {"gaps": result.gaps}
        except Exception:
            pass

        # Fallback to local heuristic
        known = profile.experience_description.lower()
        gaps = []
        if "python" not in known:
            gaps.append("Python fluency")
        if domain == "generative_ai":
            for skill in ["LLM fundamentals", "agent orchestration", "evaluation", "deployment"]:
                if skill.lower().split()[0] not in known:
                    gaps.append(skill)
        if domain == "backend_engineering" and "fastapi" not in known:
            gaps.append("FastAPI application architecture")
        return {"gaps": gaps or ["Portfolio-grade capstone depth"]}

    async def difficulty_estimator(self, profile: LearnerProfile, gaps: list[str]) -> dict:
        pressure = profile.weekly_hours * profile.deadline_months
        if len(gaps) > 4 or pressure < 30:
            difficulty = "Beginner"
        elif profile.experience_level.lower() == "advanced":
            difficulty = "Advanced"
        else:
            difficulty = "Intermediate"
        return {"difficulty": difficulty, "gap_count": len(gaps), "time_pressure": pressure}

    async def roadmap_template_lookup(self, domain: str, difficulty: str) -> dict:
        try:
            prompt = ROADMAP_TEMPLATE_LOOKUP_PROMPT.format(
                domain=domain,
                difficulty=difficulty,
            )
            result, _ = await self.router.invoke_structured(
                agent_name="PlannerAgent",
                provider=LLMProvider.GEMINI,
                schema=RoadmapTemplateLookupOutput,
                prompt=prompt,
            )
            if result is not None:
                return {
                    "stages": result.stages,
                    "difficulty": result.difficulty,
                }
        except Exception:
            pass

        # Fallback to local templates
        templates = {
            "generative_ai": [
                "Python and API foundations",
                "Machine learning and embeddings",
                "LLM application patterns",
                "LangChain and LangGraph agents",
                "Evaluation, safety, and deployment",
            ],
            "backend_engineering": [
                "Python service design",
                "FastAPI and async APIs",
                "Testing and observability",
                "Data and integration patterns",
                "Production hardening",
            ],
            "general_technology": [
                "Foundations",
                "Core tools",
                "Applied practice",
                "Project development",
                "Portfolio readiness",
            ],
        }
        return {"stages": templates.get(domain, templates["general_technology"]), "difficulty": difficulty}

