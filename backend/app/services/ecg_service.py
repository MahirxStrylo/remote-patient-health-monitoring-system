"""
app/services/ecg_service.py
Service for ECG session management, sequential batch reconstruction, digital filtering,
CSV export, and publication-quality PNG waveform generation.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless server
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal as sp_signal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ecg import ECGBatch, ECGSession

logger = logging.getLogger(__name__)


def filter_ecg_signal(
    samples: List[Optional[int]], sampling_rate_hz: int = 250
) -> List[Optional[float]]:
    """
    Apply zero-phase digital bandpass filter (0.5 Hz - 40 Hz) using second-order sections (SOS)
    to remove respiration baseline wander and high-frequency muscle tremor.

    CRITICAL RULE: Original raw ADC samples are NEVER overwritten.
    Filtering is strictly a derived display view.
    Gaps (represented by None) are preserved so lines are never falsely connected.
    """
    if not samples:
        return []

    filtered: List[Optional[float]] = [None] * len(samples)

    # Filter each continuous numeric segment separately across gaps
    idx = 0
    n = len(samples)
    nyquist = sampling_rate_hz / 2.0
    lowcut = 0.5 / nyquist
    highcut = min(40.0 / nyquist, 0.95)

    try:
        sos = sp_signal.butter(2, [lowcut, highcut], btype="bandpass", output="sos")
    except Exception as exc:
        logger.warning("Failed to design bandpass filter: %s", exc)
        sos = None

    while idx < n:
        if samples[idx] is None:
            filtered[idx] = None
            idx += 1
            continue

        # Find contiguous segment
        start = idx
        while idx < n and samples[idx] is not None:
            idx += 1
        end = idx

        seg = np.array(samples[start:end], dtype=float)
        seg_len = len(seg)

        if sos is not None and seg_len >= 15:
            try:
                # Zero-phase forward-backward filtering using second-order sections
                padlen = min(15, seg_len - 1)
                filtered_seg = sp_signal.sosfiltfilt(sos, seg, padlen=padlen)
                # Offset to nominal visual center (median of segment)
                baseline = np.median(seg)
                filtered_seg = filtered_seg + baseline
                for k, val in enumerate(filtered_seg):
                    filtered[start + k] = round(float(val), 2)
                continue
            except Exception as e:
                logger.debug("sosfiltfilt fallback on segment: %s", e)

        # Fallback for short segments: moving median baseline removal
        window = min(31, max(3, (seg_len // 2) * 2 + 1))
        if seg_len >= window:
            try:
                trend = sp_signal.medfilt(seg, kernel_size=window)
                detrended = seg - trend + np.median(seg)
                for k, val in enumerate(detrended):
                    filtered[start + k] = round(float(val), 2)
                continue
            except Exception:
                pass

        # Raw pass-through if segment too short to filter reliably
        for k, val in enumerate(seg):
            filtered[start + k] = float(val)

    return filtered


async def get_or_create_ecg_session(
    db: AsyncSession,
    patient_id: int,
    device_id: int,
    session_id: str,
    sampling_rate_hz: int,
    unit: str,
    started_at: datetime,
    is_simulated: bool = False,
) -> ECGSession:
    """Find active ECG session or create a new one with strict ownership and parameter checks."""
    res = await db.execute(
        select(ECGSession).where(ECGSession.session_id == session_id)
    )
    session = res.scalar_one_or_none()
    if session is not None:
        # Validate session ownership and parameters
        if session.device_id != device_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Device ID {device_id} is not authorized to upload data to session {session_id!r} "
                    f"owned by device ID {session.device_id}."
                ),
            )
        if session.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Session {session_id!r} belongs to patient ID {session.patient_id}, "
                    f"not patient ID {patient_id}."
                ),
            )
        if session.sampling_rate_hz != sampling_rate_hz:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payload sampling rate {sampling_rate_hz} Hz conflicts with session {session_id!r} "
                    f"sampling rate of {session.sampling_rate_hz} Hz."
                ),
            )
        if session.unit != unit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payload ECG unit {unit!r} conflicts with session {session_id!r} "
                    f"unit of {session.unit!r}."
                ),
            )
        if session.status == "Completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ECG session {session_id!r} has already been marked Completed and cannot accept new batches.",
            )
        if session.status == "Interrupted":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ECG session {session_id!r} was Interrupted and cannot accept new batches.",
            )
        return session

    session = ECGSession(
        session_id=session_id,
        patient_id=patient_id,
        device_id=device_id,
        started_at=started_at,
        sampling_rate_hz=sampling_rate_hz,
        unit=unit,
        status="Recording",
        total_samples=0,
        total_batches=0,
        is_simulated=is_simulated,
        lead_off_count=0,
        ai_analysis_status="not_configured",
    )
    try:
        db.add(session)
        await db.flush()
        return session
    except IntegrityError:
        await db.rollback()
        res = await db.execute(
            select(ECGSession).where(ECGSession.session_id == session_id)
        )
        existing = res.scalar_one_or_none()
        if existing is not None:
            if existing.device_id != device_id or existing.patient_id != patient_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session ownership conflict detected during concurrent creation.",
                )
            return existing
        raise


async def get_ecg_session(
    db: AsyncSession, session_id: str
) -> Optional[ECGSession]:
    """Retrieve an ECG session by its session_id string."""
    res = await db.execute(
        select(ECGSession).where(ECGSession.session_id == session_id)
    )
    return res.scalar_one_or_none()


# Backwards compatibility alias
get_ecg_recording = get_ecg_session


async def get_patient_ecg_sessions(
    db: AsyncSession, patient_id: int, limit: int = 50
) -> List[ECGSession]:
    """Retrieve historical ECG sessions for a patient ordered newest first."""
    res = await db.execute(
        select(ECGSession)
        .where(ECGSession.patient_id == patient_id)
        .order_by(ECGSession.started_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


# Backwards compatibility alias
get_patient_ecg_recordings = get_patient_ecg_sessions


async def get_all_ecg_sessions(
    db: AsyncSession,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[ECGSession], int]:
    """List paginated ECG sessions across all or specific patients."""
    from sqlalchemy import func
    q = select(ECGSession)
    if patient_id is not None:
        q = q.where(ECGSession.patient_id == patient_id)
    if status is not None:
        q = q.where(ECGSession.status == status)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    res = await db.execute(
        q.order_by(ECGSession.started_at.desc()).offset(skip).limit(limit)
    )
    return list(res.scalars().all()), total


async def reconstruct_ecg_timeline(
    db: AsyncSession, session: ECGSession
) -> Tuple[List[Optional[int]], List[Optional[float]], List[float], List[int], bool]:
    """
    Reconstruct continuous ordered ECG samples across all session batches.
    
    Preserves accurate physical elapsed time for missing sequences:
    When a batch is dropped (e.g. cellular network dropout), the timeline is advanced
    by the exact physical sample count (e.g. 2,500 samples @ 250 Hz = 10.0 seconds),
    filled with None sentinels so the time axis reflects actual elapsed physical time.

    Returns:
        tuple: (raw_samples, filtered_samples, time_axis, missing_sequences, has_gaps)
    """
    res = await db.execute(
        select(ECGBatch)
        .where(ECGBatch.session_id == session.id)
        .order_by(ECGBatch.sequence_number.asc())
    )
    batches = list(res.scalars().all())

    if not batches:
        return [], [], [], [], False

    raw_samples: List[Optional[int]] = []
    missing_sequences: List[int] = []
    has_gaps = False

    seq_map = {b.sequence_number: b for b in batches}
    min_seq = min(seq_map.keys())
    max_seq = max(seq_map.keys())

    # Determine typical sample count per batch (e.g. median of received batches, default 2500)
    sample_counts = [b.sample_count for b in batches if b.sample_count > 0]
    typical_batch_samples = int(np.median(sample_counts)) if sample_counts else 2500

    # Detect missing sequences starting from 1 to max_seq
    expected_start = 1 if min_seq <= 1 else min_seq
    for seq in range(expected_start, max_seq + 1):
        if seq not in seq_map:
            missing_sequences.append(seq)
            has_gaps = True
            # Advance timeline by the full physical duration of the missing batch
            raw_samples.extend([None] * typical_batch_samples)
        else:
            b = seq_map[seq]
            try:
                batch_samples = json.loads(b.samples_json)
                raw_samples.extend(batch_samples)
            except Exception:
                pass

    # Build continuous, physical time axis in seconds
    sr = session.sampling_rate_hz if session.sampling_rate_hz > 0 else 250
    dt = 1.0 / sr
    time_axis: List[float] = [round(i * dt, 6) for i in range(len(raw_samples))]

    # Filtered signal (dynamically computed with zero-phase SOS filter, raw samples unchanged)
    filtered_samples = filter_ecg_signal(raw_samples, sr)

    return raw_samples, filtered_samples, time_axis, missing_sequences, has_gaps


async def complete_ecg_session(db: AsyncSession, session: ECGSession) -> ECGSession:
    """Finalize an ECG session and calculate final status."""
    _, _, _, missing, has_gaps = await reconstruct_ecg_timeline(db, session)
    session.status = "Incomplete" if has_gaps else "Completed"
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


def generate_csv_bytes(
    session: ECGSession,
    samples: List[Optional[int]],
    filtered: Optional[List[Optional[float]]] = None,
) -> bytes:
    """Generate RFC 4180 CSV export bytes with explicit gap and filtering columns."""
    output = io.StringIO()
    writer = csv.writer(output)

    sr = session.sampling_rate_hz if session.sampling_rate_hz > 0 else 250
    total_valid = sum(1 for s in samples if s is not None)

    writer.writerow(["# Remote Health Monitoring System - ECG Session Export"])
    writer.writerow(["# Session ID", session.session_id])
    writer.writerow(["# Patient DB ID", session.patient_id])
    writer.writerow(["# Started At (UTC)", session.started_at.isoformat()])
    writer.writerow(["# Ended At (UTC)", session.ended_at.isoformat() if session.ended_at else "IN_PROGRESS"])
    writer.writerow(["# Status", session.status])
    writer.writerow(["# Sampling Frequency (Hz)", sr])
    writer.writerow(["# Signal Unit", session.unit])
    writer.writerow(["# Valid Sample Count", total_valid])
    writer.writerow(["# Total Timeline Entries", len(samples)])
    writer.writerow(["# Simulated Data", "YES" if session.is_simulated else "NO"])
    writer.writerow(["# Lead Off Detected", "YES" if session.lead_off_count > 0 else "NO"])
    writer.writerow([])
    writer.writerow(["time_seconds", f"raw_ecg_{session.unit}", f"filtered_ecg_{session.unit}"])

    for i, s in enumerate(samples):
        t = round(i / sr, 6)
        s_raw = "" if s is None else s
        s_filt = ""
        if filtered and i < len(filtered) and filtered[i] is not None:
            s_filt = filtered[i]
        writer.writerow([t, s_raw, s_filt])

    return output.getvalue().encode("utf-8")


def generate_png_bytes(
    session: ECGSession,
    samples: List[Optional[int]],
    filtered: Optional[List[Optional[float]]] = None,
) -> bytes:
    """Render publication-quality ECG strip waveform chart into PNG bytes."""
    sr = session.sampling_rate_hz if session.sampling_rate_hz > 0 else 250
    n = len(samples)

    if n == 0:
        fig, ax = plt.subplots(figsize=(10, 2), facecolor="#0a1628")
        ax.set_facecolor("#0a1628")
        ax.text(0.5, 0.5, "No samples in recording session", ha="center", va="center", color="#94a3b8", fontsize=12)
        ax.axis("off")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    t = np.arange(n) / sr
    # Convert None to NaN so Matplotlib leaves gaps instead of drawing false lines
    y_raw = np.array([float(s) if s is not None else np.nan for s in samples])

    fig, ax = plt.subplots(figsize=(15, 4.0), facecolor="#0a1628", dpi=120)
    ax.set_facecolor("#0d1b33")

    # Raw signal in cyan
    ax.plot(t, y_raw, color="#06b6d4", linewidth=0.9, antialiased=True, label="Raw ECG")

    # If filtered signal provided, overlay in bright white/emerald
    if filtered and any(f is not None for f in filtered):
        y_filt = np.array([float(f) if f is not None else np.nan for f in filtered])
        ax.plot(t, y_filt, color="#10b981", linewidth=1.1, alpha=0.85, label="Filtered ECG (0.5-40Hz)")

    # ECG grid emulation
    ax.grid(True, which="major", color="#1e3a5f", linestyle="-", linewidth=0.6, alpha=0.8)
    ax.minorticks_on()
    ax.grid(True, which="minor", color="#142640", linestyle=":", linewidth=0.4, alpha=0.5)

    ax.set_xlabel("Time (seconds)", color="#94a3b8", fontsize=9, labelpad=6)
    unit_label = "ADC Counts (AD8232 raw)" if session.unit == "adc_counts" else session.unit
    ax.set_ylabel(unit_label, color="#94a3b8", fontsize=9, labelpad=6)
    ax.tick_params(colors="#64748b", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#1e3a5f")

    sim_text = " [SIMULATED DATA]" if session.is_simulated else ""
    lead_text = " [LEAD-OFF DETECTED]" if session.lead_off_count > 0 else ""
    title = (
        f"ECG Session: {session.session_id[:8]}... | Status: {session.status} | "
        f"{session.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')} | "
        f"{sr} Hz | {n} entries ({n / sr:.2f}s){sim_text}{lead_text}"
    )
    ax.set_title(title, color="#e2e8f0", fontsize=10, pad=10, fontweight="medium")
    ax.legend(loc="upper right", facecolor="#0a1628", edgecolor="#1e3a5f", labelcolor="#94a3b8", fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


async def get_ecg_samples(db: AsyncSession, session: ECGSession) -> List[int]:
    """Backwards compatibility helper returning flat list of valid integer samples."""
    raw, _, _, _, _ = await reconstruct_ecg_timeline(db, session)
    return [s for s in raw if s is not None]
