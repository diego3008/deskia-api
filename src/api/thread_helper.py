from datetime import datetime
from typing import Union
from uuid import UUID, uuid4

import httpx
from sqlalchemy import Date
from sqlmodel import select
import logging

from src.db import _async_session_factory
from src.models.conversation import Conversation
from src.config import settings

logger = logging.getLogger(__name__)

MAX_MESSAGES = 30


async def get_or_rotate_thread(chat_id: str) -> Union[Conversation, bool] | None:
    # get existing conversation from db
    async with _async_session_factory() as session:
        result = await session.exec(
            select(Conversation).where(Conversation.telegram_chat_id == int(chat_id)).where(Conversation.status == 'active')
        )
        conversation = result.first()

    if conversation is None:
        return None
    
    # check thread existence in langgraph storage
    if await get_thread(conversation.thread_id) is not None:


        # check if conversation hits messages limit
        if conversation.message_count >= MAX_MESSAGES:
            new_thread = await _rotate_thread(conversation)
            return new_thread, True

        return conversation, False
    
    new_thread = await _rotate_thread(conversation)
    return new_thread, True



async def _rotate_thread(previous: Conversation) -> Conversation:
    new_conversation = Conversation(
        business_id=previous.business_id,
        customer_id=previous.customer_id,
        telegram_chat_id=previous.telegram_chat_id,
        thread_id=uuid4(),
        status="active",
        message_count=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        parent_thread_id=previous.thread_id,  # ← store reference to old thread
    )
    async with _async_session_factory() as session:
        previous.status = "resolved"
        session.add(previous)
        session.add(new_conversation)
        await session.commit()
        await session.refresh(new_conversation)

    await create_langgraph_thread(new_conversation.thread_id)

    return new_conversation


async def increment_message_count(conversation_id: UUID) -> None:
    async with _async_session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.message_count += 1
            session.add(conversation)
            await session.commit()


async def create_langgraph_thread(thread_id):
    async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.AGENT_SERVICE_URL}/threads",
                json={
                    "thread_id": str(thread_id),
                },
            )
            response.raise_for_status()
    return response


async def get_context_from_langgraph(parent_thread_id: str, n: int = 10) -> list:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.AGENT_SERVICE_URL}/threads/{parent_thread_id}/history",
        )
        response.raise_for_status()
        history = response.json()

    # history is a list of states, most recent first
    # each state has a 'values' key with 'messages'
    all_messages = []
    for state in history:
        all_messages = state.get("values", {}).get("messages", [])
        if all_messages:
            break  # latest snapshot has all accumulated messages

    return all_messages[-n:]


async def get_thread(thread_id: UUID) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.AGENT_SERVICE_URL}/threads/{thread_id}"
            )
        response.raise_for_status()
        new_client = response.json()
        return new_client
    except httpx.HTTPStatusError as e:
        logger.error("Agent service error: %s", e.response.text)
        return None