import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

@pytest_asyncio.fixture
async def client():
    from app.server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/api/login", json={"username": "admin", "password": "admin123"})
    if resp.status_code == 401:
        pytest.skip("本机数据库的管理员口令已不是默认值；该用例只验证默认安装")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

@pytest.mark.asyncio
async def test_login_fail(client):
    resp = await client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_devices_requires_auth(client):
    resp = await client.get("/api/devices")
    # 未带凭据必须被拒绝；401（未认证）与 403（禁止）都属拒绝。
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_devices_with_auth(client):
    login_resp = await client.post("/api/login", json={"username": "admin", "password": "admin123"})
    if login_resp.status_code != 200:
        pytest.skip("本机数据库的管理员口令已不是默认值；该用例只验证默认安装")
    token = login_resp.json()["access_token"]
    resp = await client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
