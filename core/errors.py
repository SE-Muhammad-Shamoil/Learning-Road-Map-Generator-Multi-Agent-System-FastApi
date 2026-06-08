from pydantic import BaseModel, Field


class AgentError(Exception):
    def __init__(self, agent: str, message: str) -> None:
        super().__init__(message)
        self.agent = agent
        self.message = message


class ToolExecutionError(AgentError):
    pass


class AgentExecutionError(AgentError):
    pass


class ReflectionError(AgentError):
    pass


class ValidationError(AgentError):
    pass


class ProviderError(AgentError):
    pass


class RateLimitError(ProviderError):
    def __init__(self, agent: str, message: str = "Gemini API limit has been reached.") -> None:
        super().__init__(agent, message)


class GraphExecutionError(AgentError):
    pass


class ErrorState(BaseModel):
    error_type: str
    agent: str
    message: str
    retryable: bool = False
    details: dict = Field(default_factory=dict)


def to_error_state(error: Exception, agent: str) -> ErrorState:
    return ErrorState(
        error_type=error.__class__.__name__,
        agent=getattr(error, "agent", agent),
        message=str(error),
        retryable=isinstance(error, (ToolExecutionError, AgentExecutionError, ReflectionError)),
    )
