from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models.business import Business
from src.db import get_session
from src.models.appointment import Appointment, AppointmentBase, AppointmentCreate, AppointmentUpdate

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
    starts_at: datetime,
    session: AsyncSession = Depends(get_session),
):
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    ends_at = starts_at + timedelta(hours=1)

    query = (
        select(Appointment)
        .where(Appointment.business_id == business_id)
        .where(Appointment.starts_at < ends_at)
        .where(Appointment.ends_at > starts_at)
        .where(Appointment.active == True)
    )
    result = await session.exec(query)
    return result.first() is None


@router.get("/find_customer_appointment", response_model=dict)
async def find_customer_appointment(
    customer_id: UUID,
    business_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.exec(
            select(
                Appointment.id,
                Appointment.starts_at,
                Service.name,
                BusinessStaff.first_name,
                BusinessStaff.last_name,
            )
            .join(
                BusinessStaff,
                BusinessStaff.id == Appointment.business_staff_id,
            )
            .join(Service, Service.id == Appointment.service_id)
            .where(
                Appointment.business_id == business_id,
                Appointment.customer_id == customer_id,
                Appointment.active == True,
                Appointment.starts_at >= datetime.now(timezone.utc),
            )
            .order_by(Appointment.starts_at, Appointment.id)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Upcoming active appointment not found",
        )

    appointment_id, starts_at, service_name, first_name, last_name = row
    return {
        "appointment_id": appointment_id,
        "starts_at": starts_at,
        "service_name": service_name,
        "staff_name": " ".join(
            name for name in (first_name, last_name) if name
        ),
    }

    
    

@router.post("/book", status_code=201)
async def book_appointment(
    appointment: AppointmentCreate, session: AsyncSession = Depends(get_session)
):
    db_obj = Appointment.model_validate(appointment, update={"status": "pending"})
    print(appointment.customer_id)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return {"starts_at": db_obj.starts_at.astimezone(ZoneInfo("America/Monterrey")), "ends_at": db_obj.ends_at.astimezone(ZoneInfo("America/Monterrey"))}


@router.get("/{id}", response_model=Appointment)
async def get_appointment(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return obj


@router.patch("/{id}/reschedule", response_model=Appointment)
async def update_appointment(
    id: UUID, data: AppointmentUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")

    starts_at = data.starts_at if data.starts_at is not None else obj.starts_at
    ends_at = data.ends_at if data.ends_at is not None else obj.ends_at
    business_id = data.business_id if data.business_id is not None else obj.business_id

    conflict_query = (
        select(Appointment)
        .where(Appointment.business_id == business_id)
        .where(Appointment.id != id)
        .where(Appointment.starts_at < ends_at)
        .where(Appointment.ends_at > starts_at)
        .where(Appointment.active == True)
    )
    conflict = await session.exec(conflict_query)
    if conflict.first() is not None:
        raise HTTPException(
            status_code=409,
            detail="No availability for the requested time slot",
        )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj