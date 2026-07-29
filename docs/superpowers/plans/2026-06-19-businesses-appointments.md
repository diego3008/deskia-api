# Businesses & Appointments API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLModel-backed CRUD endpoints for the pre-existing `businesses` and `appointments` Supabase tables.

**Architecture:** SQLModel (SQLAlchemy async + Pydantic in one class) connects to Supabase PostgreSQL via asyncpg. Each table gets a base model for create input, a table model for DB mapping + response, and an update model for PATCH. Sessions are injected per-request via a FastAPI `Depends` override, making tests simple: swap to an in-memory SQLite engine.

**Tech Stack:** `sqlmodel`, `asyncpg`, `aiosqlite` (tests only), `pytest`, `pytest-asyncio`, `httpx`

## Global Constraints

- Python ≥ 3.14
- Use `uv add` / `uv add --dev` for all dependency changes
- `DATABASE_URL` must use the `postgresql+asyncpg://` scheme (Supabase gives `postgresql://` — replace the scheme)
- The `appointments.business` DB column maps to `business_id` in Python via `sa_column`
- `created_at` / `updated_at` are never written from Python — Supabase manages them
- No DELETE endpoints

---

## File Map

| Path | Action | Responsibility |
|------|--------|----------------|
| `src/config.py` | Modify | Add `DATABASE_URL` setting |
| `src/db.py` | Create | Async engine + `get_session` dependency |
| `src/models/__init__.py` | Create | Empty package marker |
| `src/models/business.py` | Create | `BusinessBase`, `Business` table model, `BusinessUpdate` |
| `src/models/appointment.py` | Create | `AppointmentBase`, `Appointment` table model, `AppointmentUpdate` |
| `src/api/businesses.py` | Create | `/businesses` router (create, list, get, patch) |
| `src/api/appointments.py` | Create | `/appointments` router (create, list, get, patch) |
| `src/api/__init__.py` | Modify | Export two new routers |
| `main.py` | Modify | Include two new routers |
| `tests/__init__.py` | Create | Empty package marker |
| `tests/conftest.py` | Create | In-memory SQLite engine + session/client fixtures |
| `tests/test_businesses.py` | Create | CRUD tests for businesses |
| `tests/test_appointments.py` | Create | CRUD tests for appointments |
| `pyproject.toml` | Modify | Add pytest-asyncio config + dev deps |

---

## Task 1: Install dependencies + config + DB session layer

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config.py`
- Create: `src/db.py`

**Interfaces:**
- Produces: `get_session` async generator at `src.db.get_session` — yields `AsyncSession`
- Produces: `settings.DATABASE_URL: str` at `src.config.settings`

- [ ] **Step 1: Install runtime and dev dependencies**

```bash
uv add sqlmodel asyncpg
uv add --dev pytest pytest-asyncio httpx aiosqlite
```

- [ ] **Step 2: Add pytest-asyncio config to pyproject.toml**

Add this section at the bottom of `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Add DATABASE_URL to Settings**

In `src/config.py`, add `DATABASE_URL: str` to the `Settings` class:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str
    WEBHOOK_URL: str

    # Agent service
    AGENT_SERVICE_URL: str
    LANGGRAPH_ASSISTANT_ID: str
    LANGGRAPH_API_KEY: str

    # Database
    DATABASE_URL: str  # must use postgresql+asyncpg:// scheme

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 4: Add DATABASE_URL to .env**

In your `.env` file, add:

```
DATABASE_URL=postgresql+asyncpg://postgres:<password>@<host>:<port>/<dbname>
```

> Supabase gives a connection string starting with `postgresql://` — replace the scheme with `postgresql+asyncpg://`.

- [ ] **Step 5: Create src/db.py**

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

_async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session():
    async with _async_session_factory() as session:
        yield session
```

- [ ] **Step 6: Verify import works**

```bash
uv run python -c "from src.db import get_session; print('ok')"
```

Expected output: `ok`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/config.py src/db.py
git commit -m "feat: add sqlmodel/asyncpg deps and database session layer"
```

---

## Task 2: Business model + test infra + businesses router

**Files:**
- Create: `src/models/__init__.py`
- Create: `src/models/business.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_businesses.py`
- Create: `src/api/businesses.py`

**Interfaces:**
- Consumes: `get_session` from `src.db`
- Produces: `Business`, `BusinessBase`, `BusinessUpdate` from `src.models.business`
- Produces: `businesses_router` from `src.api.businesses`

- [ ] **Step 1: Create empty package markers**

Create `src/models/__init__.py` with empty content.
Create `tests/__init__.py` with empty content.

- [ ] **Step 2: Create src/models/business.py**

```python
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class BusinessBase(SQLModel):
    name: str
    slug: str
    telegram_bot_token: str | None = None
    timezone: str
    is_active: bool = True


class Business(BusinessBase, table=True):
    __tablename__ = "businesses"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class BusinessUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    telegram_bot_token: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
```

- [ ] **Step 3: Create tests/conftest.py**

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from main import app
from src.db import get_session


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 4: Write failing tests for businesses**

Create `tests/test_businesses.py`:

```python
import pytest
from httpx import AsyncClient


async def test_create_business(client: AsyncClient):
    response = await client.post("/businesses/", json={
        "name": "Acme Corp",
        "slug": "acme-corp",
        "timezone": "America/Mexico_City",
        "is_active": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert "id" in data


async def test_list_businesses(client: AsyncClient):
    await client.post("/businesses/", json={
        "name": "Acme Corp", "slug": "acme", "timezone": "UTC", "is_active": True
    })
    response = await client.get("/businesses/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_business(client: AsyncClient):
    create_resp = await client.post("/businesses/", json={
        "name": "Beta Ltd", "slug": "beta", "timezone": "UTC", "is_active": True
    })
    biz_id = create_resp.json()["id"]
    response = await client.get(f"/businesses/{biz_id}")
    assert response.status_code == 200
    assert response.json()["id"] == biz_id


async def test_get_business_not_found(client: AsyncClient):
    response = await client.get("/businesses/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_update_business(client: AsyncClient):
    create_resp = await client.post("/businesses/", json={
        "name": "Old Name", "slug": "old", "timezone": "UTC", "is_active": True
    })
    biz_id = create_resp.json()["id"]
    response = await client.patch(f"/businesses/{biz_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["slug"] == "old"


async def test_update_business_not_found(client: AsyncClient):
    response = await client.patch(
        "/businesses/00000000-0000-0000-0000-000000000000", json={"name": "X"}
    )
    assert response.status_code == 404
```

- [ ] **Step 5: Run tests — expect import/route errors (no router yet)**

```bash
uv run pytest tests/test_businesses.py -v
```

Expected: errors about missing route or 404 from FastAPI (not yet registered).

- [ ] **Step 6: Create src/api/businesses.py**

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db import get_session
from src.models.business import Business, BusinessBase, BusinessUpdate

router = APIRouter(prefix="/businesses", tags=["Businesses"])


@router.post("/", response_model=Business)
async def create_business(
    business: BusinessBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Business.model_validate(business)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Business])
async def list_businesses(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Business))
    return result.all()


@router.get("/{id}", response_model=Business)
async def get_business(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Business, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Business not found")
    return obj


@router.patch("/{id}", response_model=Business)
async def update_business(
    id: UUID, data: BusinessUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Business, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Business not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
```

- [ ] **Step 7: Register router temporarily in main.py to unblock tests**

In `main.py`, add at the bottom (we'll clean this up in Task 4):

```python
from src.api.businesses import router as businesses_router
app.include_router(businesses_router)
```

- [ ] **Step 8: Run tests — expect all to pass**

```bash
uv run pytest tests/test_businesses.py -v
```

Expected: 6 tests PASSED.

- [ ] **Step 9: Commit**

```bash
git add src/models/__init__.py src/models/business.py src/api/businesses.py \
        tests/__init__.py tests/conftest.py tests/test_businesses.py main.py
git commit -m "feat: add Business model and /businesses CRUD endpoints"
```

---

## Task 3: Appointment model + appointments router

**Files:**
- Create: `src/models/appointment.py`
- Create: `tests/test_appointments.py`
- Create: `src/api/appointments.py`

**Interfaces:**
- Consumes: `Business` from `src.models.business` (for FK reference in tests)
- Consumes: `get_session` from `src.db`
- Produces: `Appointment`, `AppointmentBase`, `AppointmentUpdate` from `src.models.appointment`
- Produces: `appointments_router` from `src.api.appointments`

- [ ] **Step 1: Create src/models/appointment.py**

```python
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey
from sqlmodel import Field, SQLModel


class AppointmentBase(SQLModel):
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: str | None = None
    business_id: UUID = Field(
        sa_column=Column("business", ForeignKey("businesses.id"), nullable=False)
    )


class Appointment(AppointmentBase, table=True):
    __tablename__ = "appointments"

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)


class AppointmentUpdate(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None
    notes: str | None = None
```

- [ ] **Step 2: Write failing tests for appointments**

Create `tests/test_appointments.py`:

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def business_id(client: AsyncClient) -> str:
    resp = await client.post("/businesses/", json={
        "name": "Test Biz", "slug": "test-biz", "timezone": "UTC", "is_active": True
    })
    return resp.json()["id"]


async def test_create_appointment(client: AsyncClient, business_id: str):
    response = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "status": "scheduled",
        "business_id": business_id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "scheduled"
    assert data["business_id"] == business_id
    assert "id" in data


async def test_list_appointments(client: AsyncClient, business_id: str):
    await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "status": "scheduled",
        "business_id": business_id,
    })
    response = await client.get("/appointments/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_list_appointments_filter_by_business(client: AsyncClient, business_id: str):
    await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "status": "scheduled",
        "business_id": business_id,
    })
    response = await client.get(f"/appointments/?business_id={business_id}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert all(a["business_id"] == business_id for a in results)


async def test_get_appointment(client: AsyncClient, business_id: str):
    create_resp = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "status": "scheduled",
        "business_id": business_id,
    })
    appt_id = create_resp.json()["id"]
    response = await client.get(f"/appointments/{appt_id}")
    assert response.status_code == 200
    assert response.json()["id"] == appt_id


async def test_get_appointment_not_found(client: AsyncClient):
    response = await client.get("/appointments/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_update_appointment(client: AsyncClient, business_id: str):
    create_resp = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "status": "scheduled",
        "business_id": business_id,
    })
    appt_id = create_resp.json()["id"]
    response = await client.patch(f"/appointments/{appt_id}", json={"status": "confirmed"})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


async def test_update_appointment_not_found(client: AsyncClient):
    response = await client.patch(
        "/appointments/00000000-0000-0000-0000-000000000000", json={"status": "confirmed"}
    )
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests — expect import/route errors**

```bash
uv run pytest tests/test_appointments.py -v
```

Expected: errors about missing route (router not registered yet).

- [ ] **Step 4: Create src/api/appointments.py**

```python
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db import get_session
from src.models.appointment import Appointment, AppointmentBase, AppointmentUpdate

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("/", response_model=Appointment)
async def create_appointment(
    appointment: AppointmentBase, session: AsyncSession = Depends(get_session)
):
    db_obj = Appointment.model_validate(appointment)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[Appointment])
async def list_appointments(
    business_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Appointment)
    if business_id is not None:
        query = query.where(Appointment.business_id == business_id)
    result = await session.exec(query)
    return result.all()


@router.get("/{id}", response_model=Appointment)
async def get_appointment(id: UUID, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return obj


@router.patch("/{id}", response_model=Appointment)
async def update_appointment(
    id: UUID, data: AppointmentUpdate, session: AsyncSession = Depends(get_session)
):
    obj = await session.get(Appointment, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj
```

- [ ] **Step 5: Register router temporarily in main.py**

Add to `main.py`:

```python
from src.api.appointments import router as appointments_router
app.include_router(appointments_router)
```

- [ ] **Step 6: Run tests — expect all to pass**

```bash
uv run pytest tests/test_appointments.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest -v
```

Expected: 14 tests PASSED (6 businesses + 8 appointments).

- [ ] **Step 8: Commit**

```bash
git add src/models/appointment.py src/api/appointments.py \
        tests/test_appointments.py main.py
git commit -m "feat: add Appointment model and /appointments CRUD endpoints"
```

---

## Task 4: Clean up — wire routers via __init__.py

**Files:**
- Modify: `src/api/__init__.py`
- Modify: `main.py`

**Interfaces:**
- Consumes: `router` from `src.api.businesses` and `src.api.appointments`
- Produces: `businesses_router`, `appointments_router` exported from `src.api`

- [ ] **Step 1: Update src/api/__init__.py**

Replace the full file content:

```python
from .telegram import telegram_router
from .businesses import router as businesses_router
from .appointments import router as appointments_router
```

- [ ] **Step 2: Update main.py to import from src.api**

Replace the full file content:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application
from src.api import telegram_router, businesses_router, appointments_router
from src.config import settings

logging.basicConfig(
    level="INFO",
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def build_ptb() -> Application:
    return (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .updater(None)
        .build()
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    ptb = build_ptb()
    app.state.ptb = ptb

    webhook_url = f"{settings.WEBHOOK_URL}/webhook/telegram"
    await ptb.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    logger.info("Webhook registered: %s", webhook_url)

    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()


app = FastAPI(
    title="Telegram Gateway",
    description="Receives Telegram updates and forwards them to the agent service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(telegram_router)
app.include_router(businesses_router)
app.include_router(appointments_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```bash
uv run pytest -v
```

Expected: 14 tests PASSED.

- [ ] **Step 4: Commit**

```bash
git add src/api/__init__.py main.py
git commit -m "chore: wire businesses and appointments routers via src/api/__init__.py"
```
