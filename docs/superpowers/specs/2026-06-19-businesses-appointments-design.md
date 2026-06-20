# Businesses & Appointments — API Design

## Overview

Add a SQLModel-backed database layer and REST endpoints for the `businesses` and `appointments` tables that already exist in Supabase (PostgreSQL). No migrations required — tables are pre-existing.

## Libraries

- `sqlmodel` — ORM + Pydantic models in one class (SQLAlchemy under the hood)
- `asyncpg` — async Postgres driver

## Configuration

Add `DATABASE_URL` to `src/config.py` `Settings`, loaded from `.env`.

## Module Layout

**New files:**
- `src/db.py` — async engine, `AsyncSession` factory, `get_session` FastAPI dependency
- `src/models/business.py` — `Business` SQLModel table + `BusinessUpdate` Pydantic model
- `src/models/appointment.py` — `Appointment` SQLModel table + `AppointmentUpdate` Pydantic model
- `src/api/businesses.py` — APIRouter with create, get-one, list, update
- `src/api/appointments.py` — APIRouter with create, get-one, list, update

**Updated files:**
- `src/config.py` — add `DATABASE_URL: str`
- `src/api/__init__.py` — export `businesses_router` and `appointments_router`
- `main.py` — `app.include_router(businesses_router)` and `app.include_router(appointments_router)`

## Data Models

### Business

```python
class Business(SQLModel, table=True):
    __tablename__ = "businesses"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    slug: str
    telegram_bot_token: str | None = None
    timezone: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

### Appointment

```python
class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    business_id: UUID = Field(
        sa_column=Column("business", ForeignKey("businesses.id"), nullable=False)
    )
```

`business_id` in Python maps to the `business` column in Supabase — no DB changes needed.

### Update schemas

`BusinessUpdate` and `AppointmentUpdate` are plain Pydantic `BaseModel` subclasses with every field typed as `Optional` — callers send only what changed (PATCH semantics).

`created_at` and `updated_at` are never accepted on write; Supabase manages them via column defaults and triggers.

## Endpoints

### Businesses

| Method | Path | Description |
|--------|------|-------------|
| POST | `/businesses` | Create a business |
| GET | `/businesses` | List all businesses |
| GET | `/businesses/{id}` | Get one business |
| PATCH | `/businesses/{id}` | Update a business |

### Appointments

| Method | Path | Description |
|--------|------|-------------|
| POST | `/appointments` | Create an appointment |
| GET | `/appointments` | List appointments (optional `?business_id=` filter) |
| GET | `/appointments/{id}` | Get one appointment |
| PATCH | `/appointments/{id}` | Update an appointment |

No DELETE endpoints.

## Error Handling

- `GET`/`PATCH` on unknown ID → `404 Not Found`
- DB connection errors → propagate as `500` (FastAPI default)

## Session Management

`get_session` is an `async` generator dependency injected per-request via `Depends`. The engine is created once at startup (module level in `src/db.py`).
