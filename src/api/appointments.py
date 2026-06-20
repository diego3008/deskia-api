from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models.business import Business
from src.db import get_session
from src.models.appointment import Appointment, AppointmentBase, AppointmentUpdate

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/", response_model=Appointment)
async def create_appointment(
    appointment: AppointmentBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Appointment.model_validate(appointment)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Appointment])
async def list_appointments(
    business_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Appointment)
    if business_id is not None:
        query = query.where(Appointment.business_id == business_id)
    result = await session.exec(query)
    return result.all()


@router.get("/availability", response_model=bool)
async def check_availability(
    business_id: UUID,
    starts_at: date,
    session: AsyncSession = Depends(get_session),
):
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    tz = ZoneInfo(business.timezone)
    day_start = datetime(starts_at.year, starts_at.month, starts_at.day, tzinfo=tz)
    day_end = day_start + timedelta(days=1)

    query = (
        select(Appointment)
        .where(Appointment.business_id == business_id)
        .where(Appointment.starts_at >= day_start)
        .where(Appointment.starts_at < day_end)
    )
    result = await session.exec(query)
    return result.first() is None


@router.get("/{id}", response_model=Appointment)
async def get_appointment(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return obj


@router.patch("/{id}", response_model=Appointment)
async def update_appointment(
    id: UUID, data: AppointmentUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
