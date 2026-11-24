"""
app/database/base.py
SQLAlchemy 2.x declarative base and shared mixins.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base.  All ORM models inherit from this."""
    pass


class TimestampMixin:
    """
    Adds ``created_at`` and ``updated_at`` columns to any model that
    inherits from it.

    * ``created_at`` is set once by the DB when the row is first inserted.
    * ``updated_at`` is refreshed by the DB on every UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
