from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, ForeignKey
from sqlmodel import Field, SQLModel


class ConversationBase(SQLModel):
    business_id: UUID = Field(
        sa_column=Column("business_id", ForeignKey("businesses.id"), nullable=False)
    )
    customer_id: UUID = Field(
        sa_column=Column("customer_id", ForeignKey("customers.id"), nullable=False)
    )
    telegram_chat_id: int = Field(sa_type=BigInteger)
    thread_id: UUID | None = None
    status: str = Field(default="active")
    message_count: int = Field(default=1)
    parent_thread_id: UUID | None = None


class Conversation(ConversationBase, table=True):
    __tablename__ = "conversations"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class ConversationCreate(BaseModel):
    business_id: UUID
    customer_id: UUID
    telegram_chat_id: int
    thread_id: UUID | None = None
    status: str = "active"
    message_count: int = 1


class ConversationUpdate(BaseModel):
    thread_id: UUID | None = None
    status: str | None = None
    message_count: int | None = None
