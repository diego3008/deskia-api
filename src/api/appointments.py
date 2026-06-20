from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
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
