from datetime import datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlmodel import Field, SQLModel


class StaffHourBase(SQLModel):
    business_staff_id: UUID = Field(
        sa_column=Column(
            "business_staff_id",
            Uuid(as_uuid=True),
            ForeignKey("business_staff.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    day_of_week: int = Field(sa_type=SmallInteger())
    start_time: time = Field(sa_type=Time(timezone=False))
    end_time: time = Field(sa_type=Time(timezone=False))
    active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )


class StaffHour(StaffHourBase, table=True):
    __tablename__ = "staff_hours"
    __table_args__ = (
        UniqueConstraint(
            "business_staff_id",
            "day_of_week",
            "start_time",
            "end_time",
            name="staff_hours_unique_period",
        ),
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="staff_hours_day_of_week_check",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="staff_hours_valid_time_range",
        ),
    )

    id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=text("gen_random_uuid()"),
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
