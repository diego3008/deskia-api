from datetime import date, datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlmodel import Field, SQLModel


class BusinessStaffBase(SQLModel):

    is_active: bool
    name: str
    last_name: str
    business_id: UUID = Field(
            sa_column=Column(
                "business_id", ForeignKey("deskia.business.id"), nullable=False
            )
        )

class BusinessStaff(BusinessStaffBase):

    __tablename__ = "business_staff"
    __table_args__ = {"schema": "deskia"}
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

class BusinessStaffUpdate:
    id: int
    business_id: UUID
    name: str
    last_name: str
    is_active: bool


class BusinessStaffCreate:
    business_id: UUID
    name: str
    last_name: str
    created_at: datetime | None
    is_active: bool