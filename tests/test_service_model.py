from importlib import import_module, util

from sqlalchemy import CheckConstraint, Integer, String, create_engine


def test_service_model_matches_database_schema():
    spec = util.find_spec("src.models.service")
    assert spec is not None

    Service = import_module("src.models.service").Service
    table = Service.__table__

    assert table.name == "services"
    assert set(table.c.keys()) == {
        "id",
        "business_id",
        "name",
        "duration_minutes",
        "buffer_before_minutes",
        "buffer_after_minutes",
    }
    assert table.c.id.primary_key
    assert str(table.c.id.server_default.arg) == "gen_random_uuid()"

    business_id = table.c.business_id
    assert not business_id.nullable
    foreign_key = next(iter(business_id.foreign_keys))
    assert foreign_key.target_fullname == "businesses.id"

    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 150
    assert not table.c.name.nullable

    assert isinstance(table.c.duration_minutes.type, Integer)
    assert not table.c.duration_minutes.nullable
    assert isinstance(table.c.buffer_before_minutes.type, Integer)
    assert not table.c.buffer_before_minutes.nullable
    assert str(table.c.buffer_before_minutes.server_default.arg) == "0"
    assert isinstance(table.c.buffer_after_minutes.type, Integer)
    assert not table.c.buffer_after_minutes.nullable
    assert str(table.c.buffer_after_minutes.server_default.arg) == "0"

    assert {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"duration_minutes > 0"}


def test_service_model_can_create_in_sqlite_test_database():
    Business = import_module("src.models.business").Business
    Service = import_module("src.models.service").Service
    engine = create_engine("sqlite:///:memory:")

    Business.__table__.create(engine)
    Service.__table__.create(engine)
