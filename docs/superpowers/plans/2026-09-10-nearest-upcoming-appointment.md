# Nearest Upcoming Appointment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the rescheduling lookup endpoint so it returns a customer's nearest upcoming active appointment with its service and staff names.

**Architecture:** Replace the existing `find_customer_appointment` stub with one joined SQLModel query. FastAPI validates both query parameters as UUIDs; the database filters and orders eligible appointments, and the endpoint converts the single selected row into the requested dictionary or raises HTTP 404.

**Tech Stack:** Python 3.14, FastAPI, SQLModel/SQLAlchemy async sessions, pytest, pytest-asyncio, HTTPX

**Spec:** `docs/superpowers/specs/2026-06-19-businesses-appointments-design.md`, extended by the bounded design approved in conversation on 2026-09-10.

## Global Constraints

- Keep the existing route: `GET /appointments/find_customer_appointment`.
- Accept `business_id` and `customer_id` as required `UUID` query parameters; remove the unused `appointment_date` parameter.
- An eligible appointment must match both IDs, have `active == True`, and have `starts_at >= datetime.now(timezone.utc)`.
- Select the nearest eligible appointment with `ORDER BY starts_at ASC, id ASC` and `LIMIT 1`.
- Join `business_staff` and `services` through the appointment foreign keys.
- Return exactly `appointment_id`, `starts_at`, `service_name`, and `staff_name`; join non-empty first and last name values with one space.
- Raise HTTP 404 with detail `Upcoming active appointment not found` when no joined eligible row exists.
- Do not add a response schema, dependency, migration, repository layer, or helper abstraction.
- Preserve all unrelated uncommitted work already present in `src/api/appointments.py` and the rest of the worktree.

---

## File Map

- Modify `src/api/appointments.py:201-218`: replace only the existing lookup stub with the joined, ordered query and response mapping.
- Create `tests/test_appointment_rescheduling.py`: API-level coverage for lookup selection, response fields, missing results, and UUID validation.

### Task 1: Complete and verify the nearest-upcoming appointment lookup

**Files:**
- Modify: `src/api/appointments.py:201-218`
- Create: `tests/test_appointment_rescheduling.py`

**Interfaces:**
- Consumes: `Appointment.business_id`, `Appointment.customer_id`, `Appointment.active`, `Appointment.starts_at`, `Appointment.business_staff_id`, `Appointment.service_id`, `BusinessStaff.first_name`, `BusinessStaff.last_name`, `Service.name`, and the existing `AsyncSession` dependency.
- Produces: `GET /appointments/find_customer_appointment?business_id=<UUID>&customer_id=<UUID>` returning `{"appointment_id": UUID, "starts_at": datetime, "service_name": str, "staff_name": str}` or HTTP 404.

- [ ] **Step 1: Write failing endpoint tests**

Create `tests/test_appointment_rescheduling.py` with a successful lookup that includes nearer and farther valid appointments plus ineligible competitors, followed by 404 and UUID-validation checks:

```python
from datetime import datetime, timedelta, timezone
from uuid import uuid4

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
```

- [ ] **Step 2: Run the tests and confirm the current stub fails**

Run:

```bash
pytest tests/test_appointment_rescheduling.py -v
```

Expected: all three tests fail against the stub. The success case does not return joined response keys or deterministic nearest-upcoming selection, the empty case returns `200 null`, and invalid UUID text is accepted because the current parameters are typed as `str`.

- [ ] **Step 3: Replace only the existing endpoint stub with the minimal joined query**

In `src/api/appointments.py`, replace lines 201-218 with:

```python
@router.get("/find_customer_appointment", response_model=dict)
async def find_customer_appointment(
    customer_id: UUID,
    business_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.exec(
            select(
                Appointment.id,
                Appointment.starts_at,
                Service.name,
                BusinessStaff.first_name,
                BusinessStaff.last_name,
            )
            .join(
                BusinessStaff,
                BusinessStaff.id == Appointment.business_staff_id,
            )
            .join(Service, Service.id == Appointment.service_id)
            .where(
                Appointment.business_id == business_id,
                Appointment.customer_id == customer_id,
                Appointment.active == True,
                Appointment.starts_at >= datetime.now(timezone.utc),
            )
            .order_by(Appointment.starts_at, Appointment.id)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Upcoming active appointment not found",
        )

    appointment_id, starts_at, service_name, first_name, last_name = row
    return {
        "appointment_id": appointment_id,
        "starts_at": starts_at,
        "service_name": service_name,
        "staff_name": " ".join(
            name for name in (first_name, last_name) if name
        ),
    }
```

Do not alter the imports: `datetime`, `timezone`, `UUID`, `HTTPException`, `select`, `BusinessStaff`, and `Service` are already imported by the surrounding scheduling work.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run:

```bash
pytest tests/test_appointment_rescheduling.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Run the complete suite to catch route or model regressions**

Run:

```bash
pytest -v
```

Expected: all tests pass. Do not repair unrelated failures as part of this task; record any pre-existing failure separately.

- [ ] **Step 6: Review the scoped diff and commit only the endpoint and its test**

Run:

```bash
git diff -- src/api/appointments.py tests/test_appointment_rescheduling.py
git status --short
git add tests/test_appointment_rescheduling.py
git add -p src/api/appointments.py
git diff --cached -- src/api/appointments.py tests/test_appointment_rescheduling.py
git commit -m "feat: add nearest upcoming appointment lookup"
```

Expected: use patch staging to select only the endpoint hunk from `src/api/appointments.py`; the cached diff contains only the existing function body/decorator/signature plus the new test module. If the endpoint cannot be isolated from the user's surrounding changes, leave the implementation uncommitted rather than staging those changes accidentally.
