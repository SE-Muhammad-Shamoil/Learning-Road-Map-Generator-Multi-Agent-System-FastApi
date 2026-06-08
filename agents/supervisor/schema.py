from pydantic import BaseModel


class SupervisorDecision(BaseModel):
    next_node: str
    reason: str
