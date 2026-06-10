from enum import StrEnum


class LLMProvider(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"
    GROQ = "groq"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
