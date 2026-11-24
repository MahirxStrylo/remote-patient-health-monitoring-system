"""
generate_ecg.py
Synthetic ECG and vital signs generator for software testing.

DISCLAIMER:
All generated waveforms and metrics are synthetic approximations intended
strictly for testing ingestion, visualization, and data integrity.
NEVER use generated signals for clinical decisions.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass
class ECGParameters:
    """Configurable parameters for synthetic waveform synthesis."""
    heart_rate_bpm: float = 75.0
    sampling_rate_hz: int = 250
    duration_seconds: float = 10.0
    baseline_offset: int = 512       # 10-bit ADC midpoint baseline (~512)
    p_amplitude: float = 40.0
    q_amplitude: float = -30.0
    r_amplitude: float = 450.0      # Sharp positive R-peak
    s_amplitude: float = -70.0
    t_amplitude: float = 80.0
    noise_sigma: float = 6.0
    baseline_wander_amplitude: float = 15.0


def generate_pqrst_waveform(t: np.ndarray, params: ECGParameters) -> np.ndarray:
    """
    Synthesize an ECG trace by summing Gaussian wavelets modeling P, Q, R, S, and T waves.
    Operates on periodic time vector normalized by the RR interval.
    """
    rr_interval = 60.0 / params.heart_rate_bpm  # Duration in seconds of one cardiac cycle
    phase = (t % rr_interval) / rr_interval     # Phase from 0.0 to 1.0 within beat

    signal = np.zeros_like(t, dtype=float)

    # Wavelet parameters: (center_phase, width, amplitude)
    waves = [
        (0.18, 0.035, params.p_amplitude),      # P wave (atrial depolarization)
        (0.38, 0.012, params.q_amplitude),      # Q wave (septal depolarization)
        (0.42, 0.015, params.r_amplitude),      # R peak (ventricular depolarization)
        (0.46, 0.014, params.s_amplitude),      # S wave (late ventricular depolarization)
        (0.65, 0.055, params.t_amplitude),      # T wave (ventricular repolarization)
    ]

    for center, width, amp in waves:
        signal += amp * np.exp(-0.5 * ((phase - center) / width) ** 2)

    return signal


def generate_ecg_samples(
    params: Optional[ECGParameters] = None,
    heart_rate_bpm: Optional[float] = None,
    sampling_rate_hz: Optional[int] = None,
    duration_seconds: Optional[float] = None,
) -> List[int]:
    """
    Generate synthetic ECG numerical samples in ADC counts.
    
    Returns:
        List of integer ADC count values (e.g. 400 to 1050).
    """
    p = params or ECGParameters()
    if heart_rate_bpm is not None:
        p.heart_rate_bpm = heart_rate_bpm
    if sampling_rate_hz is not None:
        p.sampling_rate_hz = sampling_rate_hz
    if duration_seconds is not None:
        p.duration_seconds = duration_seconds

    total_samples = int(p.sampling_rate_hz * p.duration_seconds)
    t = np.linspace(0, p.duration_seconds, total_samples, endpoint=False)

    # 1. Base PQRST cardiac waveform
    cardiac = generate_pqrst_waveform(t, p)

    # 2. Respiration baseline wander (~0.25 Hz, simulating breathing)
    respiration = p.baseline_wander_amplitude * np.sin(2 * np.pi * 0.25 * t)

    # 3. High-frequency muscle artifact / electronic thermal noise
    rng = np.random.default_rng()
    noise = rng.normal(0, p.noise_sigma, total_samples)

    # 4. Sum with ADC baseline offset
    raw = p.baseline_offset + cardiac + respiration + noise

    # Clip to physical 12-bit ADC range [0, 4095]
    clipped = np.clip(raw, 0, 4095)
    return [int(round(x)) for x in clipped]


def add_lead_off_artifact(samples: List[int], start_fraction: float = 0.5) -> List[int]:
    """
    Simulate electrode detachment (lead-off condition).
    The AD8232 comparator trips and signal rails to max ADC count (4095).
    """
    res = list(samples)
    start_idx = int(len(res) * start_fraction)
    for i in range(start_idx, len(res)):
        res[i] = 4095  # Rail high
    return res


def generate_vital_signs(heart_rate_bpm: float = 75.0) -> Dict[str, float]:
    """
    Simulate pulse oximeter (MAX30102) and temperature (DS18B20) readings.
    """
    rng = random.Random()
    return {
        "heart_rate_bpm": round(heart_rate_bpm + rng.uniform(-1.5, 1.5), 1),
        "spo2_percent": round(min(100.0, max(94.0, 97.8 + rng.uniform(-0.8, 0.8))), 1),
        "temperature_c": round(36.6 + rng.uniform(-0.25, 0.25), 1),
    }


if __name__ == "__main__":
    p = ECGParameters(heart_rate_bpm=72.0, sampling_rate_hz=250, duration_seconds=10.0)
    samples = generate_ecg_samples(p)
    vitals = generate_vital_signs(72.0)
    print(f"Generated {len(samples)} samples at {p.sampling_rate_hz} Hz ({len(samples)/p.sampling_rate_hz:.1f}s)")
    print(f"Sample range: min={min(samples)}, max={max(samples)} ADC counts")
    print(f"Vitals: {vitals}")
    print(f"First 10 samples: {samples[:10]}")
