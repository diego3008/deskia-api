# Appointment Cancellation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PUT endpoint that cancels one appointment scoped to its business.

**Architecture:** Add one route to the existing appointments router before the dynamic `/{id}` route. The handler uses a single SQLModel query to find the appointment by `appointment_id` and `business_id`, updates the existing cancellation columns, and returns the refreshed appointment.

**Tech Stack:** Python 3.14, FastAPI, SQLModel/SQLAlchemy async sessions, pytest, pytest-asyncio, HTTPX

**Spec:** Approved bounded design in conversation on 2026-09-10; no separate design document.

## Global Constraints

- Add `PUT /appointments/cancel`.
- Accept `appointment_id` and `business_id` as required `UUID` query parameters.
- Find the appointment using both `Appointment.id == appointment_id` and `Appointment.business_id == business_id`.
- Return HTTP 404 with detail `Appointment not found` when the scoped record does not exist.
- Set `cancelled_at` to the current UTC datetime, `active` to `False`, and the existing `status` foreign-key field to cancellation status ID `3`.
- Commit and refresh the appointment before returning it with `response_model=Appointment`.
- Keep the static `/cancel` route above `/{id}` so the dynamic UUID route cannot intercept it.
- Do not add a request schema, response schema, helper, repository layer, migration, or dependency.
- Preserve all unrelated uncommitted work already present in the worktree.

---

## File Map

- Modify `src/api/appointments.py:308`: add the cancellation route immediately before `get_appointment`.
- Modify `tests/test_appointment_rescheduling.py:152`: append focused API coverage for successful cancellation, business scoping/not-found behavior, and UUID validation.

### Task 1: Add and verify appointment cancellation

**Files:**
- Modify: `src/api/appointments.py:308`
- Test: `tests/test_appointment_rescheduling.py:152`

**Interfaces:**
- Consumes: `Appointment.id`, `Appointment.business_id`, `Appointment.cancelled_at`, `Appointment.active`, `Appointment.status`, and the existing `AsyncSession` dependency.
- Produces: `PUT /appointments/cancel?appointment_id=<UUID>&business_id=<UUID>` returning the updated `Appointment`, or HTTP 404 when no appointment matches both IDs.

- [ ] **Step 1: Write failing cancellation tests**

Add `from src.api import appointments` to the imports in `tests/test_appointment_rescheduling.py`, then append:

```python
async def test_cancel_appointment_updates_cancellation_fields(
    client, session, monkeypatch
):
    business_id = uuid4()
    appointment_id = uuid4()
    cancelled_at = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cancelled_at.astimezone(tz)

    monkeypatch.setattr(appointments, "datetime", FixedDatetime)
    appointment = Appointment(
        id=appointment_id,
        business_id=business_id,
        customer_id=uuid4(),
        starts_at=cancelled_at + timedelta(days=1),
        ends_at=cancelled_at + timedelta(days=1, hours=1),
        active=True,
        status=2,
    )
    session.add(appointment)
    await session.commit()

    response = await client.put(
        "/appointments/cancel",
        params={
            "appointment_id": str(appointment_id),
            "business_id": str(business_id),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(appointment_id)
    assert body["active"] is False
    assert body["status"] == 3
    assert datetime.fromisoformat(
        body["cancelled_at"].replace("Z", "+00:00")
    ).replace(tzinfo=timezone.utc) == cancelled_at

    updated = await session.get(Appointment, appointment_id)
    assert updated.active is False
    assert updated.status == 3
    assert updated.cancelled_at.replace(tzinfo=timezone.utc) == cancelled_at


async def test_cancel_appointment_returns_404_for_wrong_business(client, session):
    appointment = Appointment(
        id=uuid4(),
        business_id=uuid4(),
        customer_id=uuid4(),
        starts_at=datetime(2030, 1, 3, tzinfo=timezone.utc),
        ends_at=datetime(2030, 1, 3, 1, tzinfo=timezone.utc),
        active=True,
        status=2,
    )
    session.add(appointment)
    await session.commit()

    response = await client.put(
        "/appointments/cancel",
        params={
            "appointment_id": str(appointment.id),
            "business_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Appointment not found"}
    assert appointment.active is True
    assert appointment.status == 2
    assert appointment.cancelled_at is None


async def test_cancel_appointment_validates_uuid_parameters(client):
    response = await client.put(
        "/appointments/cancel",
        params={"appointment_id": "not-a-uuid", "business_id": str(uuid4())},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
uv run pytest tests/test_appointment_rescheduling.py -v
```

Expected: the three new cancellation tests fail because `PUT /appointments/cancel` does not exist. Existing tests in the file remain green.

- [ ] **Step 3: Add the minimal cancellation handler**

In `src/api/appointments.py`, insert this immediately before `@router.get("/{id}", response_model=Appointment)`:

```python
@router.put("/cancel", response_model=Appointment)
async def cancel_appointment(
    appointment_id: UUID,
    business_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    appointment = (
        await session.exec(
            select(Appointment).where(
                Appointment.id == appointment_id,
                Appointment.business_id == business_id,
            )
        )
    ).first()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.cancelled_at = datetime.now(timezone.utc)
    appointment.active = False
    appointment.status = 3
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
uv run pytest tests/test_appointment_rescheduling.py -v
```

Expected: all tests in `tests/test_appointment_rescheduling.py` pass, including the three cancellation cases.

- [ ] **Step 5: Run the complete test suite**

Run:

```bash
uv run pytest -v
```

Expected: the full suite passes with no regressions.

- [ ] **Step 6: Review the scoped diff**

Run:

```bash
git diff --check
git diff -- src/api/appointments.py tests/test_appointment_rescheduling.py
```

Expected: no whitespace errors; the diff contains only the cancellation handler, its import, and its tests, while preserving pre-existing work.

- [ ] **Step 7: Commit the endpoint and tests**

```bash
git add src/api/appointments.py tests/test_appointment_rescheduling.py
git commit -m "feat: add appointment cancellation endpoint"
```
