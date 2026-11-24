"""
tests/conftest.py
Pytest test fixtures and async SQLite database setup.
"""
import asyncio
import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set backend path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.core.security import hash_password, create_access_token
from app.models.doctor import DoctorUser
from app.models.patient import Patient
from app.models.device import Device
from app.security.device_auth import generate_device_api_key, hash_device_api_key
from app.api.v1.endpoints.auth import _login_attempts, _rate_limit_lock

# Test in-memory SQLite database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset the IP rate limiter before every test to avoid cross-test interference."""
    with _rate_limit_lock:
        _login_attempts.clear()
    yield
    with _rate_limit_lock:
        _login_attempts.clear()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Async test client with overridden database dependency."""
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_doctor(db_session: AsyncSession) -> DoctorUser:
    """Create a test doctor user."""
    doc = DoctorUser(
        username="testdoc",
        hashed_password=hash_password("docpassword123"),
        full_name="Dr. Test Physician",
        email="testdoc@example.com",
        is_active=True,
        is_admin=True,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest_asyncio.fixture
async def auth_headers(test_doctor: DoctorUser) -> dict:
    """Obtain Authorization Bearer header for test doctor."""
    token = create_access_token({"sub": test_doctor.username, "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_patient(db_session: AsyncSession) -> Patient:
    """Create a test patient."""
    p = Patient(
        patient_id="P001",
        full_name="Alice Smith",
        age=45,
        notes="Hypertension history",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def test_device(db_session: AsyncSession, test_patient: Patient) -> tuple[Device, str]:
    """Create a test device assigned to test_patient, returning (device, plain_key)."""
    full_api_key, key_id, prefix, secret = generate_device_api_key()
    dev = Device(
        device_id="ESP32-001",
        description="Rural Clinic Device 1",
        patient_id=test_patient.id,
        api_key_id=key_id,
        api_key_prefix=prefix,
        api_key_hash=hash_device_api_key(secret),
        is_active=True,
    )
    db_session.add(dev)
    await db_session.commit()
    await db_session.refresh(dev)
    return dev, full_api_key
