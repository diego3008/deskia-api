from datetime import date, datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlmodel import Field, SQLModel

from src.models.appointment_status_codes import AppointmentStatusCode  # noqa: F401


class AppointmentBase(SQLModel):
    starts_at: datetime = Field(sa_type=DateTime(timezone=True))
    ends_at: datetime = Field(sa_type=DateTime(timezone=True))
    active: bool = Field(default=True)
    notes: str | None = None
    business_id: UUID = Field(
        sa_column=Column(
            "business_id", ForeignKey("deskia.business.id"), nullable=False
        )
    )
    customer_id: UUID = Field(
        sa_column=Column(
            "customer_id", ForeignKey("deskia.customers.id"), nullable=False
        )
    )
    status: int = Field(
        sa_column=Column(
            Integer, ForeignKey("deskia.appointment_status_codes.id"), nullable=False
        )
    )
    cancellation_reason: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    cancelled_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class Appointment(AppointmentBase, table=True):
    __tablename__ = "appointments"
    __table_args__ = {"schema": "deskia"}

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )



class AppointmentUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    business_id: UUID | None = None

class AppointmentSearch(BaseModel):
    starts_at: date | None = None
    business_id: UUID | None = None

class AppointmentCreate(BaseModel):
    business_id: UUID = Field(
        description="The UUID of the business that received the message."
    )
    starts_at: datetime = Field(
        description=(
            "The exact date and time requested by the user, including the hour "
            "(e.g. 2026-06-21T15:30:00). If the user only gave a date with no time, "
            "ask them to clarify the time before calling this tool."
        )
    )
    ends_at: datetime = Field(
        description=(
            "The approximate ending date and time of the appointment, including the hour. "
            "If the user didn't specify a duration, infer a reasonable default "
            "(e.g. 1 hour after starts_at) unless context suggests otherwise."
        )
    )
    customer_id: UUID = Field(
        description="The UUID of the customer who requested the appointment."
    )
class AppointmentCancellationRequest(BaseModel):
    business_id: UUID
    customer_id: UUID
    reason: str


class AppointmentCancellationResponse(BaseModel):
    id: UUID
    status: str
    cancelled_at: datetime
    starts_at: datetime
    ends_at: datetime
