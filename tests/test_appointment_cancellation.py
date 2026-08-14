from datetime import UTC, datetime

from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.appointment import Appointment
from src.models.appointment_status_codes import AppointmentStatusCode
from src.models.business import Business
from src.models.customer import Customer


async def create_cancellable_appointment(session: AsyncSession):
    business = Business(name="Cancellation Test", slug="cancellation-test", timezone="UTC")
    session.add(business)
    await session.flush()

    customer = Customer(business_id=business.id, first_name="Ada")
    scheduled = AppointmentStatusCode(value="scheduled")
    cancelled = AppointmentStatusCode(value="cancelled")
    completed = AppointmentStatusCode(value="completed")
    session.add_all([customer, scheduled, cancelled, completed])
    await session.flush()

    appointment = Appointment(
        business_id=business.id,
        customer_id=customer.id,
        starts_at=datetime(2026, 8, 20, 16, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 20, 17, 0, tzinfo=UTC),
        status=scheduled.id,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)

    return appointment, business, customer, cancelled, completed


def cancellation_payload(business: Business, customer: Customer, reason: str):
    return {
        "business_id": str(business.id),
        "customer_id": str(customer.id),
        "reason": reason,
    }


async def test_cancel_appointment_marks_it_cancelled_and_releases_availability(
    client: AsyncClient, session: AsyncSession
):
    appointment, business, customer, cancelled, _ = await create_cancellable_appointment(session)

    response = await client.post(
        f"/appointments/{appointment.id}/cancel",
        json=cancellation_payload(business, customer, "Cancelled by customer"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(appointment.id)
    assert body["status"] == "cancelled"
    assert body["cancelled_at"].endswith("Z")
    assert body["starts_at"] == "2026-08-20T16:00:00Z"
    assert body["ends_at"] == "2026-08-20T17:00:00Z"

    await session.refresh(appointment)
    assert appointment.status == cancelled.id
    assert appointment.cancellation_reason == "Cancelled by customer"
    assert appointment.cancelled_at is not None
    assert not appointment.active


async def test_cancelling_an_already_cancelled_appointment_replays_its_response(
    client: AsyncClient, session: AsyncSession
):
    appointment, business, customer, _, _ = await create_cancellable_appointment(session)
    payload = cancellation_payload(business, customer, "Cancelled by customer")

    first_response = await client.post(f"/appointments/{appointment.id}/cancel", json=payload)
    second_response = await client.post(
        f"/appointments/{appointment.id}/cancel",
        json=cancellation_payload(business, customer, "A later reason must not overwrite it"),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()

    await session.refresh(appointment)
    assert appointment.cancellation_reason == "Cancelled by customer"


async def test_cancellation_returns_not_found_when_customer_does_not_own_appointment(
    client: AsyncClient, session: AsyncSession
):
    appointment, business, _, _, _ = await create_cancellable_appointment(session)
    other_business = Business(name="Other Business", slug="other-business", timezone="UTC")
    session.add(other_business)
    await session.flush()
    other_customer = Customer(business_id=other_business.id, first_name="Grace")
    session.add(other_customer)
    await session.commit()

    response = await client.post(
        f"/appointments/{appointment.id}/cancel",
        json=cancellation_payload(business, other_customer, "Cancelled by customer"),
    )

    assert response.status_code == 404


async def test_cancellation_rejects_completed_appointments(
    client: AsyncClient, session: AsyncSession
):
    appointment, business, customer, _, completed = await create_cancellable_appointment(session)
    appointment.status = completed.id
    session.add(appointment)
    await session.commit()

    response = await client.post(
        f"/appointments/{appointment.id}/cancel",
        json=cancellation_payload(business, customer, "Cancelled by customer"),
    )

    assert response.status_code == 409


async def test_cancelling_a_legacy_cancelled_appointment_backfills_its_timestamp(
    client: AsyncClient, session: AsyncSession
):
    appointment, business, customer, cancelled, _ = await create_cancellable_appointment(session)
    appointment.status = cancelled.id
    appointment.cancelled_at = None
    session.add(appointment)
    await session.commit()

    response = await client.post(
        f"/appointments/{appointment.id}/cancel",
        json=cancellation_payload(business, customer, "Cancelled by customer"),
    )

    assert response.status_code == 200
    assert response.json()["cancelled_at"].endswith("Z")

    await session.refresh(appointment)
    assert appointment.cancelled_at is not None


async def test_booking_stores_the_seeded_pending_status_id(
    client: AsyncClient, session: AsyncSession
):
    business = Business(name="Booking Test", slug="booking-test", timezone="UTC")
    session.add(business)
    await session.flush()

    customer = Customer(business_id=business.id, first_name="Lin")
    pending = AppointmentStatusCode(value="pending")
    session.add_all([customer, pending])
    await session.commit()

    response = await client.post(
        "/appointments/book",
        json={
            "business_id": str(business.id),
            "customer_id": str(customer.id),
            "starts_at": "2026-08-20T16:00:00Z",
            "ends_at": "2026-08-20T17:00:00Z",
        },
    )

    assert response.status_code == 201
    result = await session.exec(
        select(Appointment).where(Appointment.customer_id == customer.id)
    )
    assert result.one().status == pending.id
