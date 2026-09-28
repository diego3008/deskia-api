from importlib import import_module

from sqlalchemy import CheckConstraint, UniqueConstraint


def test_staff_hour_model_matches_database_schema():
    StaffHour = import_module("src.models.staff_hour").StaffHour
    table = StaffHour.__table__

    assert set(table.c.keys()) == {
        "id",
        "business_staff_id",
        "day_of_week",
        "start_time",
        "end_time",
        "active",
        "created_at",
    }
    foreign_key = next(iter(table.c.business_staff_id.foreign_keys))
    assert foreign_key.target_fullname == "business_staff.id"
    assert foreign_key.ondelete == "CASCADE"
    assert not table.c.active.nullable
    assert str(table.c.active.server_default.arg) == "true"
    assert table.c.created_at.type.timezone
    assert str(table.c.created_at.server_default.arg) == "now()"
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, (CheckConstraint, UniqueConstraint))
    } == {
        "staff_hours_unique_period",
        "staff_hours_day_of_week_check",
        "staff_hours_valid_time_range",
    }
