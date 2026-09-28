from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Identity, Text, func
from sqlmodel import Field, SQLModel


class AppointmentStatusCodeBase(SQLModel):
    value: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class AppointmentStatusCode(AppointmentStatusCodeBase, table=True):
    __tablename__ = "appointment_status_codes"

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            Identity(always=False),
            primary_key=True,
            nullable=False,
        ),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
