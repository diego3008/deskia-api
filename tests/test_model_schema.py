from src.models.appointment import Appointment
from src.models.business import Business
from src.models.conversation import Conversation
from src.models.customer import Customer


def test_models_use_deskia_schema():
    models = (Business, Customer, Appointment, Conversation)

    assert all(model.__table__.schema == "deskia" for model in models)


def test_foreign_keys_reference_tables_in_deskia_schema():
    models = (Customer, Appointment, Conversation)
    targets = {
        foreign_key.target_fullname
        for model in models
        for foreign_key in model.__table__.foreign_keys
    }

    assert targets == {
        "deskia.appointment_status_codes.id",
        "deskia.business.id",
        "deskia.customers.id",
    }
