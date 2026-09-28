from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.models.business import Business
from src.models.business_hour import BusinessHour
from src.models.business_schedule_exception import BusinessScheduleException
from src.models.business_staff import BusinessStaff
from src.models.service import Service
from src.models.staff_block import StaffBlock
from src.models.staff_hour import StaffHour
from src.models.staff_service import StaffService
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


@router.get("/validate-date", response_model=Union[bool, dict])
async def validate_appointment_date(
    business_id: UUID,
    requested_start_date: datetime,
    service_name: str,
    session: AsyncSession = Depends(get_session),
):
    """Check if assigned staff can perform the service at the requested date.

    Service names use a case-insensitive substring match within the business.
    Naive datetimes use the business timezone; ambiguous/nonexistent local
    times require an explicit UTC offset. Weekdays use Monday=0, Sunday=6.
    Active appointments must not overlap the requested service window.
    """
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    service_name = service_name.strip()
    if not service_name:
        raise HTTPException(status_code=422, detail="service_name must not be blank")
    requested_service = (await session.exec(
        select(Service)
        .where(
            Service.business_id == business_id,
            Service.name.icontains(service_name, autoescape=True),
        )
        .order_by(func.length(Service.name), Service.name, Service.id)
        .limit(1)
    )).first()
    if requested_service is None:
        raise HTTPException(status_code=404, detail="Service not found")

    if not business.is_active:
        return False

    try:
        tz = ZoneInfo(business.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=500, detail="Invalid business timezone")

    try:
        if requested_start_date.tzinfo is None:
            local = requested_start_date.replace(tzinfo=tz)
            if (
                local.utcoffset() != local.replace(fold=1).utcoffset()
                or local.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
                != requested_start_date
            ):
                raise HTTPException(status_code=422, detail="Provide an explicit UTC offset for this local time")
        else:
            local = requested_start_date.astimezone(tz)
        starts_at = local.astimezone(timezone.utc)
    except OverflowError:
        raise HTTPException(status_code=422, detail="Requested date is outside the supported timezone range")
    if starts_at <= datetime.now(timezone.utc):
        return False

    day = local.date()
    exception = (await session.exec(select(BusinessScheduleException).where(
        BusinessScheduleException.business_id == business_id,
        BusinessScheduleException.exception_date == day,
    ))).first()
    if exception is not None:
        if exception.is_closed:
            return False
        windows = [(exception.start_time, exception.end_time)]
    else:
        windows = (await session.exec(select(BusinessHour.start_time, BusinessHour.end_time).where(
            BusinessHour.business_id == business_id,
            BusinessHour.day_of_week == day.weekday(),
        ))).all()
    business_windows = [
        (datetime.combine(day, start, tz).astimezone(timezone.utc),
         datetime.combine(day, end, tz).astimezone(timezone.utc))
        for start, end in windows if start is not None and end is not None
    ]
    if not business_windows:
        return False

    candidates = (await session.exec(
        select(StaffService, Service, StaffHour)
        .join(Service, Service.id == StaffService.service_id)
        .join(BusinessStaff, BusinessStaff.id == StaffService.business_staff_id)
        .join(StaffHour, StaffHour.business_staff_id == BusinessStaff.id)
        .where(
            BusinessStaff.business_id == business_id,
            BusinessStaff.active == True,
            Service.business_id == business_id,
            StaffService.service_id == requested_service.id,
            StaffService.active == True,
            StaffHour.active == True,
            StaffHour.day_of_week == day.weekday(),
        )
    )).all()
    for assignment, service, shift in candidates:
        duration = assignment.custom_duration_minutes
        if duration is None:
            duration = service.duration_minutes
        before, after = service.buffer_before_minutes, service.buffer_after_minutes
        if duration <= 0 or before < 0 or after < 0:
            continue
        try:
            occupied_start = starts_at - timedelta(minutes=before)
            end_date = starts_at + timedelta(minutes=duration)
            occupied_end = starts_at + timedelta(minutes=duration + after)
        except OverflowError:
            continue
        if not any(start <= occupied_start and occupied_end <= end for start, end in business_windows):
            continue
        shift_start = datetime.combine(day, shift.start_time, tz).astimezone(timezone.utc)
        shift_end = datetime.combine(day, shift.end_time, tz).astimezone(timezone.utc)
        if not shift_start <= occupied_start < occupied_end <= shift_end:
            continue
        conflict = (await session.exec(select(Appointment.id).where(
            Appointment.business_id == business_id,
            Appointment.starts_at < occupied_end,
            Appointment.ends_at > occupied_start,
            Appointment.active == True,
        ).limit(1))).first()
        if conflict is not None:
            continue
        block = (await session.exec(select(StaffBlock.id).where(
            StaffBlock.business_staff_id == assignment.business_staff_id,
            StaffBlock.start_at < occupied_end,
            StaffBlock.end_at > occupied_start,
        ).limit(1))).first()
        if block is None:
            return {"available": True, "service_id": requested_service.id, "ends_at": end_date, "starts_at": requested_start_date, "business_staff_id": assignment.business_staff_id}
    return False


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


@router.put("/cancel", response_model=Appointment)
async def cancel_appointment(
    appointment_id: UUID,
    business_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    appointment = (
        await session.exec(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.business_id == business_id,
            )
        )
    ).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.cancelled_at = datetime.now(timezone.utc)
    appointment.active = False
    appointment.status = 3
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@router.post("/book", status_code=201)
async def book_appointment(
    appointment: AppointmentCreate, session: AsyncSession = Depends(get_session)
):
    db_obj = Appointment.model_validate(appointment, update={"status": 2})
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return {"starts_at": db_obj.starts_at.astimezone(ZoneInfo("America/Monterrey")), "ends_at": db_obj.ends_at.astimezone(ZoneInfo("America/Monterrey"))}


@router.put("/reschedule", response_model=dict)
async def reschedule_appointment(
    business_id: UUID,
    appointment_id: UUID,
    starts_at: datetime = Body(...),
    ends_at: datetime = Body(...),
    session: AsyncSession = Depends(get_session),
):
    row = (await session.exec(
        select(Appointment, BusinessStaff.first_name, BusinessStaff.last_name)
        .join(BusinessStaff, BusinessStaff.id == Appointment.business_staff_id)
        .where(
            Appointment.id == appointment_id,
            Appointment.business_id == business_id,
        )
    )).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if starts_at >= ends_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")

    appointment, first_name, last_name = row
    conflict = (await session.exec(
        select(Appointment.id)
        .where(
            Appointment.business_id == business_id,
            Appointment.id != appointment_id,
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
            Appointment.active == True,
        )
        .limit(1)
    )).first()
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail="No availability for the requested time slot",
        )

    appointment.starts_at = starts_at
    appointment.ends_at = ends_at
    session.add(appointment)
    await session.commit()
    return {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "staff_name": " ".join(name for name in (first_name, last_name) if name),
    }


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
