from uuid import UUID

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Uuid, text
from sqlmodel import Field, SQLModel


class ServiceBase(SQLModel):
    business_id: UUID = Field(
        sa_column=Column("business_id", ForeignKey("businesses.id"), nullable=False)
    )
    name: str = Field(sa_type=String(150))
    duration_minutes: int = Field(
        sa_column=Column(Integer, nullable=False)
    )
    buffer_before_minutes: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    buffer_after_minutes: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )


class Service(ServiceBase, table=True):
    __tablename__ = "services"
    __table_args__ = (CheckConstraint("duration_minutes > 0"),)

    id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=text("gen_random_uuid()"),
        ),
    )
