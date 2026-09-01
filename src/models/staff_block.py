from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, text
from sqlmodel import Field, SQLModel


class StaffBlockBase(SQLModel):
    business_staff_id: UUID = Field(
        sa_column=Column(
            "business_staff_id",
            ForeignKey("business_staff.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    start_at: datetime = Field(sa_type=DateTime(timezone=True))
    end_at: datetime = Field(sa_type=DateTime(timezone=True))
    block_type: str = Field(max_length=50)
    reason: str | None = Field(default=None, max_length=255)


class StaffBlock(StaffBlockBase, table=True):
    __tablename__ = "staff_blocks"
    __table_args__ = (
        CheckConstraint("start_at < end_at", name="staff_blocks_check"),
    )

    id: UUID | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
