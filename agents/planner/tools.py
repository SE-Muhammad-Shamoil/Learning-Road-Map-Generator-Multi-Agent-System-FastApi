from app.agents.validation.schema import LearnerProfile


class PlannerTools:
    def domain_classifier(self, profile: LearnerProfile) -> dict:
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

    def skill_gap_analysis(self, profile: LearnerProfile, domain: str) -> dict:
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

    def difficulty_estimator(self, profile: LearnerProfile, gaps: list[str]) -> dict:
        pressure = profile.weekly_hours * profile.deadline_months
        if len(gaps) > 4 or pressure < 30:
            difficulty = "Beginner"
        elif profile.experience_level.lower() == "advanced":
            difficulty = "Advanced"
        else:
            difficulty = "Intermediate"
        return {"difficulty": difficulty, "gap_count": len(gaps), "time_pressure": pressure}

    def roadmap_template_lookup(self, domain: str, difficulty: str) -> dict:
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
