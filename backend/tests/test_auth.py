"""
tests/test_auth.py
Tests for doctor authentication, password hashing, and token verification.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_doctor):
    """Test successful doctor login returns valid JWT token."""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testdoc", "password": "docpassword123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_doctor):
    """Test login with wrong password returns 401."""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "testdoc", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient, db_session):
    """Test login with non-existent username returns 401."""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent", "password": "anypassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, auth_headers):
    """Test accessing /auth/me with valid Bearer token."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testdoc"
    assert data["full_name"] == "Dr. Test Physician"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """Test accessing protected route without token returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, auth_headers):
    """Test logout audit endpoint."""
    resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert "Successfully logged out" in resp.json()["message"]
