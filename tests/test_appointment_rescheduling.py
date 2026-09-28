from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.api import appointments
from src.models.appointment import Appointment
from src.models.business_staff import BusinessStaff
from src.models.service import Service


async def test_find_customer_appointment_returns_nearest_upcoming_with_names(
    client, session
):
    business_id = uuid4()
    customer_id = uuid4()
    staff = BusinessStaff(
        id=uuid4(),
        business_id=business_id,
        first_name="Ada",
        last_name="Lovelace",
    )
    service = Service(
        id=uuid4(),
        business_id=business_id,
        name="Haircut",
        duration_minutes=60,
    )
    now = datetime.now(timezone.utc)

    def appointment(
        starts_at,
        *,
        active=True,
        selected_business_id=business_id,
        selected_customer_id=customer_id,
    ):
        return Appointment(
            id=uuid4(),
            business_id=selected_business_id,
            customer_id=selected_customer_id,
            business_staff_id=staff.id,
            service_id=service.id,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            active=active,
        )

    expected = appointment(now + timedelta(days=2))
    session.add_all(
        [
            staff,
            service,
            appointment(now - timedelta(days=1)),
            appointment(now + timedelta(days=1), active=False),
            expected,
            appointment(now + timedelta(days=3)),
            appointment(
                now + timedelta(hours=1), selected_business_id=uuid4()
            ),
            appointment(
                now + timedelta(hours=1), selected_customer_id=uuid4()
            ),
        ]
    )
    await session.commit()

    response = await client.get(
        "/appointments/find_customer_appointment",
        params={"business_id": str(business_id), "customer_id": str(customer_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["starts_at"].startswith(expected.starts_at.isoformat()[:19])
    assert {key: value for key, value in body.items() if key != "starts_at"} == {
        "appointment_id": str(expected.id),
        "service_name": "Haircut",
        "staff_name": "Ada Lovelace",
    }


async def test_find_customer_appointment_returns_404_when_none_is_eligible(client):
    response = await client.get(
        "/appointments/find_customer_appointment",
        params={"business_id": str(uuid4()), "customer_id": str(uuid4())},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Upcoming active appointment not found"}


async def test_find_customer_appointment_validates_uuid_parameters(client):
    response = await client.get(
        "/appointments/find_customer_appointment",
        params={"business_id": "not-a-uuid", "customer_id": str(uuid4())},
    )

    assert response.status_code == 422


async def test_reschedule_appointment_updates_dates_and_returns_staff_name(
    client, session
):
    business_id = uuid4()
    appointment_id = uuid4()
    staff = BusinessStaff(
        id=uuid4(),
        business_id=business_id,
        first_name="Ada",
        last_name="Lovelace",
    )
    service = Service(
        id=uuid4(),
        business_id=business_id,
        name="Haircut",
        duration_minutes=60,
    )
    original_starts_at = datetime.now(timezone.utc) + timedelta(days=1)
    appointment = Appointment(
        id=appointment_id,
        business_id=business_id,
        customer_id=uuid4(),
        business_staff_id=staff.id,
        service_id=service.id,
        starts_at=original_starts_at,
        ends_at=original_starts_at + timedelta(hours=1),
        active=True,
    )
    session.add_all([staff, service, appointment])
    await session.commit()

    new_starts_at = original_starts_at + timedelta(days=2)
    new_ends_at = new_starts_at + timedelta(hours=1)
    response = await client.put(
        "/appointments/reschedule",
        params={
            "business_id": str(business_id),
            "appointment_id": str(appointment_id),
        },
        json={
            "starts_at": new_starts_at.isoformat(),
            "ends_at": new_ends_at.isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["starts_at"].startswith(new_starts_at.isoformat()[:19])
    assert body["ends_at"].startswith(new_ends_at.isoformat()[:19])
    assert body["staff_name"] == "Ada Lovelace"
    updated = await session.get(Appointment, appointment_id)
    assert updated.starts_at == new_starts_at
    assert updated.ends_at == new_ends_at


async def test_cancel_appointment_updates_cancellation_fields(
    client, session, monkeypatch
):
    business_id = uuid4()
    appointment_id = uuid4()
    cancelled_at = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cancelled_at.astimezone(tz)

    monkeypatch.setattr(appointments, "datetime", FixedDatetime)
    appointment = Appointment(
        id=appointment_id,
        business_id=business_id,
        customer_id=uuid4(),
        business_staff_id=uuid4(),
        service_id=uuid4(),
        starts_at=cancelled_at + timedelta(days=1),
        ends_at=cancelled_at + timedelta(days=1, hours=1),
        active=True,
        status=2,
    )
    session.add(appointment)
    await session.commit()

    response = await client.put(
        "/appointments/cancel",
        params={
            "appointment_id": str(appointment_id),
            "business_id": str(business_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(appointment_id)
    assert body["active"] is False
    assert body["status"] == 3
    assert datetime.fromisoformat(
        body["cancelled_at"].replace("Z", "+00:00")
    ).replace(tzinfo=timezone.utc) == cancelled_at

    updated = await session.get(Appointment, appointment_id)
    assert updated.active is False
    assert updated.status == 3
    assert updated.cancelled_at.replace(tzinfo=timezone.utc) == cancelled_at


async def test_cancel_appointment_returns_404_for_wrong_business(client, session):
    appointment = Appointment(
        id=uuid4(),
        business_id=uuid4(),
        customer_id=uuid4(),
        business_staff_id=uuid4(),
        service_id=uuid4(),
        starts_at=datetime(2030, 1, 3, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 3, 1, tzinfo=timezone.utc),
        active=True,
        status=2,
    )
    session.add(appointment)
    await session.commit()

    response = await client.put(
        "/appointments/cancel",
        params={
            "appointment_id": str(appointment.id),
            "business_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Appointment not found"}
    assert appointment.active is True
    assert appointment.status == 2
    assert appointment.cancelled_at is None


async def test_cancel_appointment_validates_uuid_parameters(client):
    response = await client.put(
        "/appointments/cancel",
        params={"appointment_id": "not-a-uuid", "business_id": str(uuid4())},
    )

    assert response.status_code == 422
