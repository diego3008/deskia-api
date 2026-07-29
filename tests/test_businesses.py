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
