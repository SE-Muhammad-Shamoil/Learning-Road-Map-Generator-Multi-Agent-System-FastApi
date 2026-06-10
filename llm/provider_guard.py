from app.core.errors import ProviderError
from app.llm.providers import LLMProvider


AGENT_PROVIDER_CHAIN: dict[str, list[LLMProvider]] = {
    "ValidationAgent": [LLMProvider.GROQ, LLMProvider.MISTRAL, LLMProvider.OPENAI],
    "ReflectionAgent": [LLMProvider.GEMINI, LLMProvider.OPENAI],
    "PlannerAgent": [LLMProvider.GEMINI, LLMProvider.DEEPSEEK, LLMProvider.OPENAI],
    "CurriculumAgent": [LLMProvider.GEMINI, LLMProvider.DEEPSEEK, LLMProvider.OPENAI],
    "RevisionAgent": [LLMProvider.GEMINI, LLMProvider.OPENAI],
    "ResourceAgent": [LLMProvider.GEMINI, LLMProvider.OPENAI],
}


class ProviderGuard:
    def assert_provider(self, agent_name: str, provider: LLMProvider) -> None:
        chain = AGENT_PROVIDER_CHAIN.get(agent_name)
        if chain is None:
            raise ProviderError(agent_name, f"No provider policy exists for {agent_name}")
        if provider not in chain:
            raise ProviderError(
                agent_name,
                f"{agent_name} must use one of {[p.value for p in chain]}, not {provider.value}",
            )

