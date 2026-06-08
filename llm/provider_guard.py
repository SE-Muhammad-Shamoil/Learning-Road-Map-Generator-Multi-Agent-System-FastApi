from app.core.errors import ProviderError
from app.llm.providers import LLMProvider


AGENT_PROVIDER_MAP: dict[str, LLMProvider] = {
    "ValidationAgent": LLMProvider.GEMINI,
    "ReflectionAgent": LLMProvider.GEMINI,
    "PlannerAgent": LLMProvider.GEMINI,
    "CurriculumAgent": LLMProvider.GEMINI,
    "RevisionAgent": LLMProvider.GEMINI,
    "ResourceAgent": LLMProvider.GEMINI,
}


class ProviderGuard:
    def assert_provider(self, agent_name: str, provider: LLMProvider) -> None:
        expected = AGENT_PROVIDER_MAP.get(agent_name)
        if expected is None:
            raise ProviderError(agent_name, f"No provider policy exists for {agent_name}")
        if provider != expected:
            raise ProviderError(
                agent_name,
                f"{agent_name} must use {expected.value}, not {provider.value}",
            )
