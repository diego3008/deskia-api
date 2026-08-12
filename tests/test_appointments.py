import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def business_id(client: AsyncClient) -> str:
    resp = await client.post("/businesses/", json={
        "name": "Test Biz", "slug": "test-biz", "timezone": "UTC", "is_active": True
    })
    return resp.json()["id"]


@pytest_asyncio.fixture
async def customer_id(client: AsyncClient, business_id: str) -> str:
    resp = await client.post(
        "/customers/",
        json={"business_id": business_id, "first_name": "Test Customer"},
    )
    return resp.json()["id"]


async def test_create_appointment(
    client: AsyncClient, business_id: str, customer_id: str
):
    response = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "active": True,
        "business_id": business_id,
        "customer_id": customer_id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["business_id"] == business_id
    assert data["customer_id"] == customer_id
    assert "id" in data


async def test_list_appointments(
    client: AsyncClient, business_id: str, customer_id: str
):
    await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "business_id": business_id,
        "customer_id": customer_id,
    })
    response = await client.get("/appointments/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_list_appointments_filter_by_business(
    client: AsyncClient, business_id: str, customer_id: str
):
    await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "business_id": business_id,
        "customer_id": customer_id,
    })
    response = await client.get(f"/appointments/?business_id={business_id}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert all(a["business_id"] == business_id for a in results)


async def test_get_appointment(
    client: AsyncClient, business_id: str, customer_id: str
):
    create_resp = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "business_id": business_id,
        "customer_id": customer_id,
    })
    appt_id = create_resp.json()["id"]
    response = await client.get(f"/appointments/{appt_id}")
    assert response.status_code == 200
    assert response.json()["id"] == appt_id


async def test_get_appointment_not_found(client: AsyncClient):
    response = await client.get("/appointments/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_update_appointment(
    client: AsyncClient, business_id: str, customer_id: str
):
    create_resp = await client.post("/appointments/", json={
        "starts_at": "2026-06-19T10:00:00Z",
        "ends_at": "2026-06-19T11:00:00Z",
        "business_id": business_id,
        "customer_id": customer_id,
    })
    appt_id = create_resp.json()["id"]
    response = await client.patch(
        f"/appointments/{appt_id}/reschedule",
        json={
            "starts_at": "2026-06-19T12:00:00Z",
            "ends_at": "2026-06-19T13:00:00Z",
        },
    )
    assert response.status_code == 200
    assert response.json()["starts_at"] == "2026-06-19T12:00:00"
    assert response.json()["ends_at"] == "2026-06-19T13:00:00"


async def test_update_appointment_not_found(client: AsyncClient):
    response = await client.patch(
        "/appointments/00000000-0000-0000-0000-000000000000/reschedule",
        json={"starts_at": "2026-06-19T12:00:00Z"},
    )
    assert response.status_code == 404
