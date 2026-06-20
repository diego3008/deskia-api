from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey
from sqlmodel import Field, SQLModel


class AppointmentBase(SQLModel):
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: str | None = None
    business_id: UUID = Field(
        sa_column=Column("business", ForeignKey("businesses.id"), nullable=False)
    )


class Appointment(AppointmentBase, table=True):
    __tablename__ = "appointments"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class AppointmentUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None
    notes: str | None = None
