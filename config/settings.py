from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Learning Roadmap Generator"
    app_env: str = "development"
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    langsmith_api_key: str | None = Field(default=None, alias="LANGSMITH_API_KEY")
    # LLM configuration
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-3.1-flash-lite"
    use_llm: bool = True
    enable_external_tools: bool = True
    debug_mode: bool = True
    external_tool_timeout_seconds: float = 4.0
    reflection_max_iterations: int = 3
    checkpoint_namespace: str = "roadmap-generator"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
