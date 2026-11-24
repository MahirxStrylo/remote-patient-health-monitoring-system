"""
app/database/session.py
Async SQLAlchemy engine, session factory, and FastAPI dependency.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine (Dual SQLite & PostgreSQL support)
# ---------------------------------------------------------------------------
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict[str, object] = {
    "echo": False,
    "future": True,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Cloud PostgreSQL (Neon, Render, Supabase) connection pooling
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

async_engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an ``AsyncSession`` for the duration of a single request.

    Usage in a route::

        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """
    Create all tables that are registered on ``Base.metadata``.

    Call this once during application startup.  It is a no-op if the
    tables already exist (``checkfirst=True`` via ``create_all``).
    """
    # Import here to ensure all models are registered before we call
    # create_all.  The models __init__ does the heavy lifting.
    from app.database.base import Base  # noqa: F401
    import app.models  # noqa: F401 – registers every model on Base.metadata

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("Database tables created / verified.")


# ---------------------------------------------------------------------------
# Initial Admin Account Bootstrap
# ---------------------------------------------------------------------------
async def bootstrap_admin(db: AsyncSession | None = None) -> None:
    """
    Idempotently provision the initial administrator account on startup.
    Runs only if the administrator account does not already exist.
    Never overwrites an existing administrator's password automatically on restart.
    Safe against concurrent startup via try/except IntegrityError.
    """
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        log.info("ADMIN_USERNAME or ADMIN_PASSWORD not configured. Skipping admin bootstrap.")
        return

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.core.security import hash_password
    from app.models.doctor import DoctorUser

    async def _execute_bootstrap(session: AsyncSession) -> None:
        try:
            result = await session.execute(
                select(DoctorUser).where(DoctorUser.username == settings.ADMIN_USERNAME)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                log.info(
                    "Administrator account '%s' already exists. Skipping bootstrap.",
                    settings.ADMIN_USERNAME,
                )
                return

            admin = DoctorUser(
                username=settings.ADMIN_USERNAME,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                full_name="System Administrator",
                email=f"{settings.ADMIN_USERNAME}@health-monitor.local",
                is_active=True,
                is_admin=True,
            )
            session.add(admin)
            await session.commit()
            log.info(
                "Initial administrator account '%s' created successfully.",
                settings.ADMIN_USERNAME,
            )
        except IntegrityError:
            await session.rollback()
            log.info(
                "Administrator account '%s' was already created concurrently.",
                settings.ADMIN_USERNAME,
            )
        except Exception as exc:
            await session.rollback()
            log.error(
                "Failed to bootstrap administrator account: %s",
                type(exc).__name__,
            )

    if db is not None:
        await _execute_bootstrap(db)
    else:
        async with AsyncSessionLocal() as session:
            await _execute_bootstrap(session)

