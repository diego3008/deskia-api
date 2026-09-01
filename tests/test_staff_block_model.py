from importlib import import_module, util

from sqlalchemy import CheckConstraint


def test_staff_block_model_matches_database_schema():
    spec = util.find_spec("src.models.staff_block")
    assert spec is not None

    StaffBlock = import_module("src.models.staff_block").StaffBlock
    table = StaffBlock.__table__

    assert table.name == "staff_blocks"
    assert set(table.c.keys()) == {
        "id",
        "business_staff_id",
        "start_at",
        "end_at",
        "block_type",
        "reason",
    }
    assert table.c.id.primary_key
    assert str(table.c.id.server_default.arg) == "gen_random_uuid()"
    assert table.c.start_at.type.timezone
    assert table.c.end_at.type.timezone
    assert table.c.block_type.type.length == 50
    assert table.c.reason.type.length == 255
    assert table.c.reason.nullable

    foreign_key = next(iter(table.c.business_staff_id.foreign_keys))
    assert foreign_key.target_fullname == "business_staff.id"
    assert foreign_key.ondelete == "CASCADE"
    assert {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"start_at < end_at"}
