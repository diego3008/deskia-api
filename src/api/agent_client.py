import logging
import httpx
from src.config import settings
from src.db import _async_session_factory
from src.models.conversation import Conversation
from src.schemas import IncomingMessage, AgentResponse
from src.api.thread_helper import get_context_from_langgraph, get_or_rotate_thread, increment_message_count

logger = logging.getLogger(__name__)

async def forward_to_agent(message: IncomingMessage) -> AgentResponse | None:
    try:
        thread, isNew = await get_or_rotate_thread(
            chat_id=message.chat_id,
        )

        if thread is None:
            return None
        
        input_payload = {"messages": [message.model_dump()], "business_id": str(thread.business_id)}

        if isNew and thread.parent_thread_id:
            context_messages = await get_context_from_langgraph(thread.parent_thread_id)
            if context_messages:
                input_payload = {
                    "messages": context_messages + [message.model_dump()],
                    "business_id": str(thread.business_id)
                }
        


        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.AGENT_SERVICE_URL}/threads/{thread.thread_id}/runs/wait",
                json={
                    "assistant_id": settings.LANGGRAPH_ASSISTANT_ID,
                    "input": input_payload
                },
            )
            response.raise_for_status()
            result = response.json()

        messages = result.get("messages", [])
        ai_message = next(
            (m for m in reversed(messages) if m["type"] == "ai"), None
        )

        if ai_message is None:
            return None

    

        await increment_message_count(
            conversation_id=thread.id,
        )
        content = ai_message.get("content", "")

        if isinstance(content, list):
            content = " ".join(block.get("text", "") for block in content if isinstance(block, dict))

        return AgentResponse(text=content or "Gracias, ya se tienen tus datos en el sistema. En qué fecha te gustaría agendar?")

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