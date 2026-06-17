import logging
import httpx
 
from src.config import settings
from src.schemas import IncomingMessage, AgentResponse
 
logger = logging.getLogger(__name__)

async def forward_to_agent(message: IncomingMessage) -> AgentResponse | None:
    """
    POSTs the normalized message to the agent service and returns its response.
    Returns None if the agent service is unreachable or returns an error.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AGENT_SERVICE_URL}/runs/wait",
                json= {
                    "assistant_id": settings.LANGGRAPH_ASSISTANT_ID,
                    "input": {"messages": message.model_dump()},
                },
            )
            result = response.json()
            messages = result["messages"]
            ai_message = next(m for m in reversed(messages) if m["type"] == "ai")
            return AgentResponse(text=ai_message["content"])
 
    except httpx.TimeoutException:
        logger.error("Agent service timed out for chat_id=%s", message.chat_id)
    except httpx.HTTPStatusError as e:
        logger.error("Agent service returned %s: %s", e.response.status_code, e.response.text)
    except Exception:
        logger.exception("Unexpected error forwarding to agent service")
 
    return None