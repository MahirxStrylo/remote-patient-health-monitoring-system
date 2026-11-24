"""
app/services/ai_stub.py
Future AI ECG classification service interface.

DISCLAIMER:
Educational research prototype only. The system does not provide medical diagnoses.
AD8232 provides a single-lead ECG. Models trained on standard 12-lead ECGs cannot
be used directly without formal domain validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class ECGAnalysisResult:
    """Structured result returned by an ECG analysis model."""

    status: str = "not_configured"  # "not_configured" | "completed" | "inconclusive" | "unsupported_signal"
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    classification: Optional[str] = None
    confidence: Optional[float] = None
    signal_quality: Optional[str] = None
    analysis_timestamp: Optional[datetime] = None
    disclaimer: str = (
        "This AI analysis is experimental and uncertified. "
        "It must not be used for medical diagnosis, treatment planning, or clinical triage."
    )
    message: str = (
        "AI analysis: Not configured. "
        "Connect an authorized single-lead ECG classification model to enable automated evaluation."
    )


class ECGAnalysisService:
    """
    Interface contract for pluggable ECG classification models.
    Default implementation safely returns 'not_configured'.
    """

    async def analyze(
        self, samples: List[int], sampling_rate_hz: int, ecg_unit: str
    ) -> ECGAnalysisResult:
        """
        Analyze an ECG waveform. Currently returns the non-configured stub.
        
        Future integration requirements:
        1. Model must explicitly be calibrated for single-lead AD8232 input.
        2. Must evaluate signal quality before attempting classification.
        3. Outcomes must include 'inconclusive' and 'unsupported_signal'.
        4. Confidence must be calibrated, not raw softmax.
        """
        return ECGAnalysisResult()

    def is_configured(self) -> bool:
        """Indicate whether a live inference model is registered."""
        return False


# Singleton service instance
ai_service = ECGAnalysisService()
