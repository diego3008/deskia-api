from importlib import import_module, util

from sqlalchemy import Text, create_engine


def test_business_staff_model_matches_database_schema():
    spec = util.find_spec("src.models.business_staff")
    assert spec is not None

    module = import_module("src.models.business_staff")
    BusinessStaff = module.BusinessStaff
    table = BusinessStaff.__table__

    assert table.name == "business_staff"
    assert set(table.c.keys()) == {
        "id",
        "created_at",
        "business_id",
        "first_name",
        "last_name",
        "active",
        "email",
        "phone",
    }
    assert table.c.id.primary_key
    assert str(table.c.id.server_default.arg) == "gen_random_uuid()"
    assert table.c.created_at.type.timezone
    assert not table.c.created_at.nullable
    assert str(table.c.created_at.server_default.arg) == "now()"

    business_id = table.c.business_id
    assert business_id.nullable
    assert str(business_id.server_default.arg) == "gen_random_uuid()"
    foreign_key = next(iter(business_id.foreign_keys))
    assert foreign_key.target_fullname == "businesses.id"
    assert foreign_key.onupdate == "RESTRICT"

    for name in ("first_name", "last_name", "email", "phone"):
        column = table.c[name]
        assert isinstance(column.type, Text)
        assert column.nullable
        assert str(column.server_default.arg) == "''"
    assert table.c.active.nullable
    assert str(table.c.active.server_default.arg) == "true"

    staff = BusinessStaff()
    assert staff.first_name == ""
    assert staff.last_name == ""
    assert staff.active is True
    assert staff.email == ""
    assert staff.phone == ""


def test_business_staff_model_can_create_in_sqlite_test_database():
    Business = import_module("src.models.business").Business
    BusinessStaff = import_module("src.models.business_staff").BusinessStaff
    engine = create_engine("sqlite:///:memory:")

    Business.__table__.create(engine)
    BusinessStaff.__table__.create(engine)
