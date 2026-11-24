"""
app/schemas/dashboard.py
Pydantic v2 schemas for the dashboard statistics endpoint.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class RecentEvent(BaseModel):
    """A single entry in the recent activity feed."""

    event_type: str
    actor_type: str
    actor_id: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class DashboardStats(BaseModel):
    """Aggregate statistics and recent activity shown on the dashboard."""

    total_patients: int
    total_devices: int
    active_devices: int
    latest_uploads_count: int
    recent_ecg_count: int
    recent_events: List[RecentEvent] = []
    ingestion_errors: int = 0
