from datetime import datetime

from sqlalchemy import Column, DateTime, String, func
from sqlmodel import Field, SQLModel


class AppointmentStatusCodesBase(SQLModel):
    value: str = Field(sa_column=Column(String, nullable=False))


class AppointmentStatusCode(AppointmentStatusCodesBase, table=True):
    __tablename__ = "appointment_status_codes"
    __table_args__ = {"schema": "deskia"}

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
