"""Decide whether a run is steady enough for decoupling to mean anything."""

from __future__ import annotations

import pandas as pd

from drift.metrics import coverage

MIN_MOVING_MIN = 30
MAX_HR_CV = 0.08
MAX_SPEED_CV = 0.15
MIN_COVERAGE = 0.85
MIN_STEADY_MIN = 15   


def _cv(series: pd.Series) -> float:
    mean = series.mean()
    return float("inf") if mean == 0 else series.std() / mean


def rejection_reason(df: pd.DataFrame) -> str | None:
    """Return why this run is unsuitable, or None if it is steady.

    Thresholds are tuned empirically, not derived. See README.
    """
    if len(df) / 60 < MIN_STEADY_MIN:
        return "too short"
    if _cv(df["heart_rate"]) > MAX_HR_CV:
        return "heart rate too variable"
    if _cv(df["speed_mps"]) > MAX_SPEED_CV:
        return "pace too variable"
    if coverage(df) < MIN_COVERAGE:
        return "too much stopped time"
    return None


def is_steady(df: pd.DataFrame) -> bool:
    return rejection_reason(df) is None