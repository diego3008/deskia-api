from importlib import import_module, util

from sqlalchemy import SmallInteger, Time, create_engine


def test_business_hour_model_matches_database_schema():
    spec = util.find_spec("src.models.business_hour")
    assert spec is not None

    module = import_module("src.models.business_hour")
    BusinessHour = module.BusinessHour
    table = BusinessHour.__table__

    assert table.name == "business_hours"
    assert set(table.c.keys()) == {
        "id",
        "day_of_week",
        "start_time",
        "end_time",
        "business_id",
    }
    assert table.c.id.primary_key
    assert str(table.c.id.server_default.arg) == "gen_random_uuid()"
    assert isinstance(table.c.day_of_week.type, SmallInteger)
    assert not table.c.day_of_week.nullable
    assert isinstance(table.c.start_time.type, Time)
    assert table.c.start_time.type.timezone is False
    assert not table.c.start_time.nullable
    assert isinstance(table.c.end_time.type, Time)
    assert table.c.end_time.type.timezone is False
    assert not table.c.end_time.nullable

    business_id = table.c.business_id
    assert business_id.nullable
    assert str(business_id.server_default.arg) == "gen_random_uuid()"
    foreign_key = next(iter(business_id.foreign_keys))
    assert foreign_key.target_fullname == "businesses.id"
    assert {
        str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    } == {
        "start_time < end_time",
        "day_of_week >= 0 AND day_of_week <= 6",
    }


def test_business_hour_model_can_create_in_sqlite_test_database():
    Business = import_module("src.models.business").Business
    spec = util.find_spec("src.models.business_hour")
    assert spec is not None
    BusinessHour = import_module("src.models.business_hour").BusinessHour
    engine = create_engine("sqlite:///:memory:")

    Business.__table__.create(engine)
    BusinessHour.__table__.create(engine)
