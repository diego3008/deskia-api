from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db import get_session
from src.models.conversation import Conversation, ConversationBase, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.post("/", response_model=Conversation)
async def create_conversation(
    conversation: ConversationBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Conversation.model_validate(conversation)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Conversation])
async def list_conversations(
    business_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Conversation)
    if business_id is not None:
        query = query.where(Conversation.business_id == business_id)
    if customer_id is not None:
        query = query.where(Conversation.customer_id == customer_id)
    result = await session.exec(query)
    return result.all()


@router.get("/by-chat/{telegram_chat_id}", response_model=Conversation)
async def get_conversation_by_chat_id(
    telegram_chat_id: int, session: AsyncSession = Depends(get_session)
):
    result = await session.exec(
        select(Conversation).where(Conversation.telegram_chat_id == telegram_chat_id)
    )
    obj = result.first()
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return obj


@router.get("/{id}", response_model=Conversation)
async def get_conversation(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Conversation, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return obj


@router.patch("/{id}", response_model=Conversation)
async def update_conversation(
    id: UUID, data: ConversationUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Conversation, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
