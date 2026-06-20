from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlmodel import Field, SQLModel


class CustomerBase(SQLModel):
    business_id: UUID = Field(
        sa_column=Column("business_id", ForeignKey("businesses.id"), nullable=False)
    )
    telegram_user_id: int
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    phone: str | None = None


class Customer(CustomerBase, table=True):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("business_id", "telegram_user_id"),)

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class CustomerUpdate(BaseModel):
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    phone: str | None = None
