from datetime import date, datetime, time, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from src.api import appointments
from src.models.appointment import Appointment, AppointmentCreate
from src.models.business import Business
from src.models.business_hour import BusinessHour
from src.models.business_schedule_exception import BusinessScheduleException
from src.models.business_staff import BusinessStaff
from src.models.service import Service
from src.models.staff_block import StaffBlock
from src.models.staff_hour import StaffHour
from src.models.staff_service import StaffService


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2029, 1, 1, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(appointments, "datetime", FixedDatetime)


@pytest_asyncio.fixture
async def schedule(session):
    business = Business(name="Salon", slug="salon", timezone="America/Monterrey")
    staff = BusinessStaff(id=uuid4(), business_id=business.id)
    service = Service(id=uuid4(), business_id=business.id, name="Haircut", duration_minutes=60)
    hours = BusinessHour(id=uuid4(), business_id=business.id, day_of_week=0,
                         start_time=time(9), end_time=time(17))
    shift = StaffHour(id=uuid4(), business_staff_id=staff.id, day_of_week=0,
                      start_time=time(9), end_time=time(17))
    assignment = StaffService(business_staff_id=staff.id, service_id=service.id)
    session.add_all([business, staff, service, hours, shift, assignment])
    await session.commit()
    return business, staff, service, hours, shift, assignment


async def validate(client, business_id, service_name="Haircut", requested="2030-01-07T10:00:00-06:00"):
    return await client.get("/appointments/validate-date", params={
        "business_id": str(business_id), "service_name": service_name,
        "requested_start_date": requested,
    })


def is_available(response):
    payload = response.json()
    return payload["available"] if isinstance(payload, dict) else payload


@pytest.mark.parametrize("requested,expected", [
    ("2030-01-07T09:00:00-06:00", True),
    ("2030-01-07T16:00:00-06:00", True),
    ("2030-01-07T16:01:00-06:00", False),
    ("2030-01-07T17:00:00-06:00", False),
    ("2030-01-07T08:59:00-06:00", False),
    ("2030-01-08T10:00:00-06:00", False),
    ("2030-01-07T16:00:00Z", True),
    ("2030-01-08T01:00:00+09:00", True),
    ("2030-01-07T10:00:00", True),
    ("2020-01-06T10:00:00-06:00", False),
])
async def test_date_and_timezone_boundaries(client, schedule, requested, expected):
    response = await validate(client, schedule[0].id, schedule[2].name, requested)
    assert response.status_code == 200
    assert is_available(response) is expected


@pytest.mark.parametrize("index,field,value", [
    (0, "is_active", False), (1, "active", False), (1, "active", None),
    (5, "active", False), (3, "day_of_week", 1), (4, "day_of_week", 1),
    (4, "start_time", time(11)), (4, "end_time", time(10, 30)),
    (5, "custom_duration_minutes", 480), (5, "custom_duration_minutes", 0),
    (2, "buffer_before_minutes", 61), (2, "buffer_after_minutes", 361),
    (1, "business_id", uuid4()),
])
async def test_schedule_restrictions(client, session, schedule, index, field, value):
    setattr(schedule[index], field, value)
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is False


@pytest.mark.parametrize("index", [1, 3, 4, 5])
async def test_missing_schedule_is_unavailable(client, session, schedule, index):
    await session.delete(schedule[index])
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is False


async def test_inactive_staff_hours_are_unavailable(client, session, schedule):
    schedule[4].active = False
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is False


@pytest.mark.parametrize("closed,start,end,requested,expected", [
    (True, None, None, "2030-01-07T10:00:00-06:00", False),
    (False, time(12), time(14), "2030-01-07T10:00:00-06:00", False),
    (False, time(12), time(14), "2030-01-07T13:00:00-06:00", True),
    (False, time(12), time(14), "2030-01-07T13:01:00-06:00", False),
])
async def test_exceptions_override_weekly_hours(client, session, schedule, closed, start, end, requested, expected):
    session.add(BusinessScheduleException(id=uuid4(), business_id=schedule[0].id,
        exception_date=date(2030, 1, 7), is_closed=closed, start_time=start, end_time=end))
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name, requested)
    assert response.status_code == 200
    assert is_available(response) is expected


async def test_exception_can_open_day_without_weekly_hours(client, session, schedule):
    await session.delete(schedule[3])
    session.add(BusinessScheduleException(id=uuid4(), business_id=schedule[0].id,
        exception_date=date(2030, 1, 7), start_time=time(9), end_time=time(17)))
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is True


@pytest.mark.parametrize("start,end,expected", [
    (15, 16, True), (16, 17, False), (17, 18, True), (15, 18, False),
])
async def test_staff_block_overlap_boundaries(client, session, schedule, start, end, expected):
    session.add(StaffBlock(id=uuid4(), business_staff_id=schedule[1].id, block_type="break",
        start_at=datetime(2030, 1, 7, start, tzinfo=timezone.utc),
        end_at=datetime(2030, 1, 7, end, tzinfo=timezone.utc)))
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is expected


async def test_another_staff_member_can_be_available(client, session, schedule):
    business, staff, service, *_ = schedule
    staff.active = False
    other = BusinessStaff(id=uuid4(), business_id=business.id)
    session.add_all([other,
        StaffHour(id=uuid4(), business_staff_id=other.id, day_of_week=0,
                  start_time=time(9), end_time=time(17)),
        StaffService(business_staff_id=other.id, service_id=service.id)])
    await session.commit()
    response = await validate(client, business.id, service.name)
    assert response.status_code == 200
    assert is_available(response) is True


async def test_custom_duration_and_buffers(client, session, schedule):
    schedule[5].custom_duration_minutes = 30
    schedule[2].buffer_before_minutes = 10
    schedule[2].buffer_after_minutes = 10
    await session.commit()
    assert is_available(await validate(client, schedule[0].id, schedule[2].name, "2030-01-07T16:20:00-06:00")) is True
    assert is_available(await validate(client, schedule[0].id, schedule[2].name, "2030-01-07T16:21:00-06:00")) is False
    assert is_available(await validate(client, schedule[0].id, schedule[2].name, "2030-01-07T09:00:00-06:00")) is False


async def test_request_validation(client):
    assert (await validate(client, uuid4())).status_code == 404
    assert (await validate(client, "invalid")).status_code == 422
    assert (await validate(client, uuid4(), requested="invalid")).status_code == 422
    assert (await client.get("/appointments/validate-date")).status_code == 422


async def test_service_name_match_is_case_insensitive_and_partial(client, schedule):
    response = await validate(client, schedule[0].id, "hair")
    assert response.status_code == 200
    assert response.json()["available"] is True


async def test_available_response_returns_selected_staff_id(client, schedule):
    response = await validate(client, schedule[0].id)
    assert response.status_code == 200
    assert response.json()["business_staff_id"] == str(schedule[1].id)


async def test_booking_maps_selected_staff_and_service(schedule):
    business, staff, service, *_ = schedule
    session = AsyncMock()
    session.add = Mock()
    request = AppointmentCreate.model_validate({
        "business_id": str(business.id),
        "customer_id": str(uuid4()),
        "business_staff_id": str(staff.id),
        "service_id": str(service.id),
        "starts_at": "2030-01-07T10:00:00-06:00",
        "ends_at": "2030-01-07T11:00:00-06:00",
    })

    await appointments.book_appointment(request, session)

    stored = session.add.call_args.args[0]
    assert stored.business_staff_id == staff.id
    assert stored.service_id == service.id


async def test_unknown_service_name_returns_not_found(client, schedule):
    response = await validate(client, schedule[0].id, "Massage")
    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


@pytest.mark.parametrize("service_name", ["%", "_"])
async def test_service_name_wildcards_are_literal(client, schedule, service_name):
    response = await validate(client, schedule[0].id, service_name)
    assert response.status_code == 404


async def test_service_name_is_scoped_to_business(client, session, schedule):
    other_business = Business(name="Spa", slug="spa", timezone="America/Monterrey")
    session.add(other_business)
    await session.flush()
    session.add(Service(id=uuid4(), business_id=other_business.id,
                        name="Massage", duration_minutes=60))
    await session.commit()

    response = await validate(client, schedule[0].id, "massage")
    assert response.status_code == 404


async def test_blank_service_name_is_rejected(client, schedule):
    response = await validate(client, schedule[0].id, "   ")
    assert response.status_code == 422


async def test_shortest_matching_service_name_is_selected(client, session, schedule):
    business, staff, service, *_ = schedule
    service.duration_minutes = 480
    shorter = Service(id=uuid4(), business_id=business.id, name="Cut", duration_minutes=30)
    session.add_all([shorter, StaffService(business_staff_id=staff.id, service_id=shorter.id)])
    await session.commit()

    response = await validate(client, business.id, "cut")
    assert response.status_code == 200
    assert is_available(response) is True


async def test_existing_active_appointment_makes_time_unavailable(client, session, schedule):
    business, staff, service, *_ = schedule
    session.add(Appointment(
        id=uuid4(),
        business_id=business.id,
        customer_id=uuid4(),
        business_staff_id=staff.id,
        service_id=service.id,
        starts_at=datetime(2030, 1, 7, 16, 30, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 7, 17, 30, tzinfo=timezone.utc),
    ))
    await session.commit()

    response = await validate(client, business.id, service.name)
    assert response.status_code == 200
    assert is_available(response) is False


@pytest.mark.parametrize("start,end,active", [
    (15, 16, True),
    (17, 18, True),
    (16, 17, False),
])
async def test_nonconflicting_appointments_do_not_block(
    client, session, schedule, start, end, active
):
    business, staff, service, *_ = schedule
    session.add(Appointment(
        id=uuid4(),
        business_id=business.id,
        customer_id=uuid4(),
        business_staff_id=staff.id,
        service_id=service.id,
        starts_at=datetime(2030, 1, 7, start, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 7, end, tzinfo=timezone.utc),
        active=active,
    ))
    await session.commit()

    response = await validate(client, business.id, service.name)
    assert response.status_code == 200
    assert is_available(response) is True


@pytest.mark.parametrize("requested", ["2030-03-10T02:30:00", "2030-11-03T01:30:00"])
async def test_dst_local_time_requires_offset(client, session, schedule, requested):
    schedule[0].timezone = "America/New_York"
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name, requested)
    assert response.status_code == 422


async def test_invalid_business_timezone(client, session, schedule):
    schedule[0].timezone = "Not/A_Zone"
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 500
    assert response.json()["detail"] == "Invalid business timezone"


@pytest.mark.parametrize("start,end", [(15, 16), (17, 18)])
async def test_buffers_cannot_overlap_blocks(client, session, schedule, start, end):
    schedule[2].buffer_before_minutes = 10
    schedule[2].buffer_after_minutes = 10
    session.add(StaffBlock(id=uuid4(), business_staff_id=schedule[1].id, block_type="break",
        start_at=datetime(2030, 1, 7, start, tzinfo=timezone.utc),
        end_at=datetime(2030, 1, 7, end, tzinfo=timezone.utc)))
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is False


async def test_only_requested_service_can_qualify(client, session, schedule):
    business, staff, service, *_ = schedule
    service.duration_minutes = 480
    shorter = Service(id=uuid4(), business_id=business.id, name="Trim", duration_minutes=30)
    session.add_all([shorter, StaffService(business_staff_id=staff.id, service_id=shorter.id)])
    await session.commit()
    response = await validate(client, business.id, service.name)
    assert response.status_code == 200
    assert is_available(response) is False
    assert is_available(await validate(client, business.id, shorter.name)) is True


async def test_split_hours_do_not_allow_crossing_a_gap(client, session, schedule):
    schedule[3].end_time = time(10, 30)
    session.add(BusinessHour(id=uuid4(), business_id=schedule[0].id, day_of_week=0,
                            start_time=time(10, 45), end_time=time(17)))
    await session.commit()
    response = await validate(client, schedule[0].id, schedule[2].name)
    assert response.status_code == 200
    assert is_available(response) is False
    assert is_available(await validate(client, schedule[0].id, schedule[2].name, "2030-01-07T11:00:00-06:00")) is True


@pytest.mark.parametrize("requested", [
    "9999-12-31T23:59:59", "9999-12-31T23:59:59-12:00", "0001-01-01T00:00:00Z",
])
async def test_unrepresentable_timezone_conversion(client, schedule, requested):
    response = await validate(client, schedule[0].id, schedule[2].name, requested)
    assert response.status_code == 422
