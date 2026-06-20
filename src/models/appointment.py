from datetime import date, datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey
from sqlmodel import Field, SQLModel


class AppointmentBase(SQLModel):
    starts_at: datetime = Field(sa_type=DateTime(timezone=True))
    ends_at: datetime = Field(sa_type=DateTime(timezone=True))
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


class AppointmentSearch(BaseModel):
    starts_at: date | None = None
    business_id: UUID | None = None
