from typing import Any, TypeVar

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from app.core.observability import LLMUsage, Timer
from app.config.settings import get_settings
from app.llm.gemini import build_gemini_llm
from app.llm.provider_guard import ProviderGuard
from app.llm.providers import LLMProvider
from app.core.errors import RateLimitError

T = TypeVar("T", bound=BaseModel)


import asyncio

def is_retryable_exception(e: BaseException) -> bool:
    # Do not retry on system exits, keyboard interrupts, or async cancellations
    if not isinstance(e, Exception) or isinstance(e, asyncio.CancelledError):
        return False
        
    error_str = str(e).lower()
    error_type = type(e).__name__.lower()
    # If the exception indicates quota exhaustion or rate limits, don't retry
    if "resourceexhausted" in error_type or "429" in error_str or "quota" in error_str or "limit" in error_str:
        return False
    return True


class LLMRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.guard = ProviderGuard()
        self._gemini = build_gemini_llm()

    def get(self, agent_name: str, provider: LLMProvider) -> Any | None:
        self.guard.assert_provider(agent_name, provider)
        return self._gemini

    def structured(self, agent_name: str, provider: LLMProvider, schema: type[T]) -> Any | None:
        llm = self.get(agent_name, provider)
        if llm is None:
            return None
        return llm.with_structured_output(schema)

    def usage(self, agent_name: str, provider: LLMProvider, used_live_llm: bool, latency_ms: float = 0) -> LLMUsage:
        self.guard.assert_provider(agent_name, provider)
        model = self.settings.gemini_model
        return LLMUsage(
            agent=agent_name,
            provider=provider.value,
            model=model,
            used_live_llm=used_live_llm,
            latency_ms=latency_ms,
        )

    async def invoke_structured(
        self,
        *,
        agent_name: str,
        provider: LLMProvider,
        schema: type[T],
        prompt: str,
    ) -> tuple[T | None, LLMUsage]:
        chain = self.structured(agent_name, provider, schema)
        if chain is None:
            return None, self.usage(agent_name, provider, used_live_llm=False)
            
        @retry(
            wait=wait_fixed(2),
            stop=stop_after_attempt(20),
            retry=retry_if_exception(is_retryable_exception),
            reraise=True,
        )
        async def _invoke() -> T | None:
            return await chain.ainvoke(prompt)

        with Timer() as timer:
            try:
                result = await _invoke()
            except Exception as e:
                if not is_retryable_exception(e):
                    raise RateLimitError(agent=agent_name) from e
                raise
                
        return result, self.usage(agent_name, provider, used_live_llm=True, latency_ms=timer.elapsed_ms)
