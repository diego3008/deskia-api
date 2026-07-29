from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class BusinessBase(SQLModel):
    name: str
    slug: str
    telegram_bot_token: str | None = None
    timezone: str
    is_active: bool = True


class Business(BusinessBase, table=True):
    __tablename__ = "businesses"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class BusinessUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    telegram_bot_token: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
