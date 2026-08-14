from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models.business import Business
from src.db import get_session
from src.models.appointment import (
    Appointment,
    AppointmentBase,
    AppointmentCancellationRequest,
    AppointmentCancellationResponse,
    AppointmentCreate,
    AppointmentUpdate,
)
from src.models.appointment_status_codes import AppointmentStatusCode

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def cancellation_response(appointment: Appointment) -> AppointmentCancellationResponse:
    return AppointmentCancellationResponse(
        id=appointment.id,
        status="cancelled",
        cancelled_at=utc_datetime(appointment.cancelled_at),
        starts_at=utc_datetime(appointment.starts_at),
        ends_at=utc_datetime(appointment.ends_at),
    )


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


@router.get("/count", response_model=int)
async def count_appointments(
    business_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(ZoneInfo("America/Monterrey"))
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    query = select(func.count()).select_from(Appointment).where(Appointment.created_at >= month_start)
    if business_id is not None:
        query = query.where(Appointment.business_id == business_id)

    result = await session.exec(query)
    return result.one()


@router.get("/growth", response_model=Optional[float])
async def count_appointments_growth(
    business_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(ZoneInfo("America/Monterrey"))
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    async def count_between(start: datetime, end: datetime) -> int:
        query = (
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.created_at >= start)
            .where(Appointment.created_at < end)
        )
        if business_id is not None:
            query = query.where(Appointment.business_id == business_id)
        result = await session.exec(query)
        return result.one()

    this_month_count = await count_between(this_month_start, now)
    last_month_count = await count_between(last_month_start, this_month_start)

    if last_month_count == 0:
        return None

    return ((this_month_count - last_month_count) / last_month_count) * 100


@router.get('/find_customer_appointment', response_model=Appointment | None)
async def find_customer_appointment(
    customer_id: str,
    business_id: str,
    appointment_date: datetime | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = (
        select(Appointment)
        .where(Appointment.business_id == business_id)
        .where(Appointment.customer_id == customer_id)
        .where(Appointment.active)
    )
    if appointment_date is not None:
        query = query.where(func.date(Appointment.starts_at) == appointment_date)

    res = await session.exec(query)
    return res.first()

    
    

@router.post("/book", status_code=201)
async def book_appointment(
    appointment: AppointmentCreate, session: AsyncSession = Depends(get_session)
):
    pending_status_result = await session.exec(
        select(AppointmentStatusCode).where(AppointmentStatusCode.value == "pending")
    )
    pending_status = pending_status_result.first()
    if pending_status is None:
        raise HTTPException(status_code=500, detail="Pending status code is not configured")

    db_obj = Appointment.model_validate(appointment, update={"status": pending_status.id})
    print(appointment.customer_id)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return {"starts_at": db_obj.starts_at.astimezone(ZoneInfo("America/Monterrey")), "ends_at": db_obj.ends_at.astimezone(ZoneInfo("America/Monterrey"))}


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentCancellationResponse,
)
async def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancellationRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .where(Appointment.business_id == data.business_id)
        .where(Appointment.customer_id == data.customer_id)
    )
    appointment = result.first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current_status = await session.get(AppointmentStatusCode, appointment.status)
    if current_status is not None and current_status.value == "completed":
        raise HTTPException(
            status_code=409,
            detail="Completed appointments cannot be cancelled",
        )

    if current_status is not None and current_status.value == "cancelled":
        if appointment.cancelled_at is None:
            appointment.cancelled_at = datetime.now(UTC)
            appointment.active = False
            session.add(appointment)
            await session.commit()
            await session.refresh(appointment)
        return cancellation_response(appointment)

    cancelled_status_result = await session.exec(
        select(AppointmentStatusCode).where(AppointmentStatusCode.value == "cancelled")
    )
    cancelled_status = cancelled_status_result.first()
    if cancelled_status is None:
        raise HTTPException(status_code=500, detail="Cancelled status code is not configured")

    appointment.status = cancelled_status.id
    appointment.cancellation_reason = data.reason
    appointment.cancelled_at = datetime.now(UTC)
    appointment.active = False
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)

    return cancellation_response(appointment)


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