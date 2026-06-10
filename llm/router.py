import asyncio
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.errors import RateLimitError
from app.core.observability import LLMUsage, Timer
from app.llm.gemini import build_gemini_llm
from app.llm.provider_guard import ProviderGuard
from app.llm.providers import LLMProvider

from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_mistralai import ChatMistralAI

T = TypeVar("T", bound=BaseModel)


def is_rate_limit_or_quota(e: BaseException) -> bool:
    # Do not treat async cancellations as rate limits
    if isinstance(e, asyncio.CancelledError):
        return False
    error_str = str(e).lower()
    error_type = type(e).__name__.lower()
    return any(
        term in error_str or term in error_type
        for term in ["429", "quota", "limit", "resourceexhausted", "ratelimit"]
    )


class LLMRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.guard = ProviderGuard()
        self._gemini = build_gemini_llm()
        self._openai = self._build_openai()
        self._groq = self._build_groq()
        self._mistral = self._build_mistral()
        self._deepseek = self._build_deepseek()

    def _build_openai(self) -> ChatOpenAI | None:
        if not self.settings.use_llm or not self.settings.openai_api_key:
            return None
        return ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            temperature=0.2,
        )

    def _build_groq(self) -> ChatGroq | None:
        if not self.settings.use_llm or not self.settings.groq_api_key:
            return None
        return ChatGroq(
            model=self.settings.groq_model,
            api_key=self.settings.groq_api_key,
            temperature=0.2,
        )

    def _build_mistral(self) -> ChatOpenAI | None:
        if not self.settings.use_llm or not self.settings.mistral_api_key:
            return None
        return ChatOpenAI(
            model=self.settings.mistral_model,
            api_key=self.settings.mistral_api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.2,
        )

    def _build_deepseek(self) -> ChatOpenAI | None:
        if not self.settings.use_llm or not self.settings.deepseek_api_key:
            return None
        return ChatOpenAI(
            model=self.settings.deepseek_model,
            api_key=self.settings.deepseek_api_key,
            base_url="https://api.deepseek.com/v1",
            temperature=0.2,
        )

    def get(self, agent_name: str, provider: LLMProvider) -> Any | None:
        self.guard.assert_provider(agent_name, provider)
        if provider == LLMProvider.GEMINI:
            return self._gemini
        if provider == LLMProvider.OPENAI:
            return self._openai
        if provider == LLMProvider.GROQ:
            return self._groq
        if provider == LLMProvider.MISTRAL:
            return self._mistral
        if provider == LLMProvider.DEEPSEEK:
            return self._deepseek
        return None

    def structured(self, agent_name: str, provider: LLMProvider, schema: type[T]) -> Any | None:
        llm = self.get(agent_name, provider)
        if llm is None:
            return None
        return llm.with_structured_output(schema)

    def usage(self, agent_name: str, provider: LLMProvider, used_live_llm: bool, latency_ms: float = 0) -> LLMUsage:
        self.guard.assert_provider(agent_name, provider)
        model = self._model_name_for(provider)
        return LLMUsage(
            agent=agent_name,
            provider=provider.value,
            model=model,
            used_live_llm=used_live_llm,
            latency_ms=latency_ms,
        )

    def _model_name_for(self, provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return self.settings.gemini_model
        if provider == LLMProvider.OPENAI:
            return self.settings.openai_model
        if provider == LLMProvider.GROQ:
            return self.settings.groq_model
        if provider == LLMProvider.MISTRAL:
            return self.settings.mistral_model
        if provider == LLMProvider.DEEPSEEK:
            return self.settings.deepseek_model
        return "unknown"

    async def invoke_structured(
        self,
        *,
        agent_name: str,
        provider: LLMProvider,
        schema: type[T],
        prompt: str,
    ) -> tuple[T | None, LLMUsage]:
        from app.llm.provider_guard import AGENT_PROVIDER_CHAIN
        chain = AGENT_PROVIDER_CHAIN.get(agent_name, [provider])

        last_exception = None
        used_provider = None
        used_model = None
        result = None
        elapsed_ms = 0.0

        for current_provider in chain:
            llm = self.get(agent_name, current_provider)
            if llm is None:
                continue

            structured_llm = llm.with_structured_output(schema)
            if structured_llm is None:
                continue

            # Determine retry strategy for this provider
            # Groq: retry up to 5 times with 2-second wait if rate limited
            max_attempts = 5 if current_provider == LLMProvider.GROQ else 3
            wait_seconds = 2

            with Timer() as timer:
                for attempt in range(max_attempts):
                    try:
                        result = await structured_llm.ainvoke(prompt)
                        used_provider = current_provider
                        used_model = self._model_name_for(current_provider)
                        break
                    except Exception as e:
                        last_exception = e
                        if is_rate_limit_or_quota(e):
                            if attempt < max_attempts - 1:
                                await asyncio.sleep(wait_seconds)
                                continue
                        else:
                            if attempt < max_attempts - 1:
                                await asyncio.sleep(0.5)
                                continue

                if result is not None:
                    elapsed_ms = timer.elapsed_ms
                    break

        if result is not None:
            usage = LLMUsage(
                agent=agent_name,
                provider=used_provider.value,
                model=used_model,
                used_live_llm=True,
                latency_ms=elapsed_ms,
            )
            return result, usage

        if last_exception is None:
            # Offline/mock mode
            return None, self.usage(agent_name, provider, used_live_llm=False)

        if is_rate_limit_or_quota(last_exception):
            raise RateLimitError(
                agent=agent_name,
                message="Groq Req per min reached, gemini quota reached."
            )
        raise last_exception
