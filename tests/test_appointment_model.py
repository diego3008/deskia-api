from importlib import import_module

from sqlalchemy import CheckConstraint


def test_appointment_model_matches_database_schema():
    Appointment = import_module("src.models.appointment").Appointment
    table = Appointment.__table__

    assert set(table.c.keys()) == {
        "id",
        "starts_at",
        "ends_at",
        "notes",
        "created_at",
        "updated_at",
        "business_id",
        "customer_id",
        "active",
        "status",
        "cancellation_reason",
        "cancelled_at",
        "business_staff_id",
        "service_id",
    }
    assert str(table.c.id.server_default.arg) == "extensions.uuid_generate_v4()"
    assert table.c.starts_at.type.timezone
    assert table.c.ends_at.type.timezone
    assert table.c.created_at.type.timezone
    assert table.c.updated_at.type.timezone
    assert table.c.cancelled_at.type.timezone
    assert table.c.status.type.python_type is int
    assert table.c.active.nullable
    assert table.c.business_id.server_default.arg.text == "gen_random_uuid()"
    assert table.c.customer_id.server_default.arg.text == "gen_random_uuid()"
    assert table.c.business_staff_id.nullable
    assert table.c.service_id.nullable
    assert {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"ends_at > starts_at"}
