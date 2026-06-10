from langchain_google_genai import ChatGoogleGenerativeAI

from app.config.settings import get_settings


def build_gemini_llm() -> ChatGoogleGenerativeAI | None:
    settings = get_settings()
    key = settings.gemini_api_key
    if not settings.use_llm or not key or not key.strip():
        return None
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=key.strip(),
        temperature=0.2,
        max_tokens=3000,
        max_retries=0,
    )
