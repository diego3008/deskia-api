from sqlalchemy import DateTime, Integer, String

from src.models.appointment import Appointment
from src.models.appointment_status_codes import AppointmentStatusCode


def test_appointment_status_code_maps_the_existing_database_table():
    table = AppointmentStatusCode.__table__

    assert table.fullname == "deskia.appointment_status_codes"
    assert isinstance(table.c.id.type, Integer)
    assert table.c.id.primary_key
    assert isinstance(table.c.value.type, String)
    assert not table.c.value.nullable


def test_appointment_maps_status_and_nullable_cancellation_fields():
    table = Appointment.__table__

    assert isinstance(table.c.status.type, Integer)
    assert not table.c.status.nullable
    assert {
        foreign_key.target_fullname for foreign_key in table.c.status.foreign_keys
    } == {"deskia.appointment_status_codes.id"}
    assert isinstance(table.c.cancellation_reason.type, String)
    assert table.c.cancellation_reason.nullable
    assert isinstance(table.c.cancelled_at.type, DateTime)
    assert table.c.cancelled_at.type.timezone
    assert table.c.cancelled_at.nullable
