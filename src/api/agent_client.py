import logging
import httpx
from src.config import settings
from src.db import _async_session_factory
from src.models.conversation import Conversation
from src.schemas import IncomingMessage, AgentResponse
from src.api.thread_helper import get_thread_id

logger = logging.getLogger(__name__)

async def forward_to_agent(message: IncomingMessage) -> AgentResponse | None:
    try:
        thread, business = await get_thread_id(
            chat_id=message.chat_id,
        )

        if thread is None:
            return None
        
        input_payload = {"messages": [message.model_dump()], "business_id": str(business)}
        

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AGENT_SERVICE_URL}/threads/{thread}/runs/wait",
                json={
                    "assistant_id": settings.LANGGRAPH_ASSISTANT_ID,
                    "input": input_payload
                }
            )
            response.raise_for_status()
            result = response.json()

        messages = result.get("messages", [])
        ai_message = next(
            (m for m in reversed(messages) if m["type"] == "ai"), None
        )

        if ai_message is None:
            return None

        content = ai_message.get("content", "")

        if isinstance(content, list):
            content = " ".join(block.get("text", "") for block in content if isinstance(block, dict))

        return AgentResponse(text=content)

    except httpx.HTTPStatusError as e:
        logger.error("Agent service error: %s", e.response.text)
        return None
    except httpx.RequestError as e:
        logger.error("Agent service unreachable: %s", e)
        return None
                
        return None
 
    except httpx.TimeoutException:
        logger.error("Agent service timed out for chat_id=%s", message.chat_id)
    except httpx.HTTPStatusError as e:
        logger.error("Agent service returned %s: %s", e.response.status_code, e.response.text)
    except Exception:
        logger.exception("Unexpected error forwarding to agent service")
 
    return None