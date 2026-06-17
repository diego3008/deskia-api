from pydantic import BaseModel


class IncomingMessage(BaseModel):
    """
    Normalized message sent to the agent service.
    Platform-agnostic — the agent never deals with raw Telegram objects.
    """
    platform: str
    chat_id: str
    user_id: str
    username: str | None = None
    metadata: dict = {}
    role: str = "user"
    content: str


class AgentResponse(BaseModel):
    """
    Expected response shape from the agent service.
    """
    text: str