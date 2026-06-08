from langchain_google_genai import ChatGoogleGenerativeAI

from app.config.settings import get_settings


def build_gemini_llm() -> ChatGoogleGenerativeAI | None:
    settings = get_settings()
    if not settings.use_llm or not settings.gemini_api_key:
        return None
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
        max_tokens=3000,
        max_retries=0,
    )
