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
