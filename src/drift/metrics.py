"""Run-level metrics computed from tidy record frames."""

from __future__ import annotations

import pandas as pd

MIN_HALF_SAMPLES = 30


class MetricError(ValueError):
    """Raised when a frame cannot support a metric."""


def _efficiency_factor(df: pd.DataFrame) -> float:
    """Mean speed per mean heartbeat. Higher is better."""
    mean_hr = df["heart_rate"].mean()
    if mean_hr <= 0:
        raise MetricError("mean heart rate is zero or negative")
    return df["speed_mps"].mean() / mean_hr


def decoupling(df: pd.DataFrame) -> float:
    """Percentage drop in efficiency factor from first to second half.

    Split is by row count. Rows are moving samples, so this is a moving-time
    split rather than a wall-clock one. Positive means efficiency fell:
    the same heart rate bought less speed later in the run.
    """
    if len(df) < 2 * MIN_HALF_SAMPLES:
        raise MetricError(f"need >= {2 * MIN_HALF_SAMPLES} samples, got {len(df)}")

    mid = len(df) // 2
    first = _efficiency_factor(df.iloc[:mid])
    second = _efficiency_factor(df.iloc[mid:])

    if first <= 0:
        raise MetricError("first-half efficiency factor is non-positive")

    return (first - second) / first * 100.0


def coverage(df: pd.DataFrame) -> float:
    """Fraction of elapsed time covered by moving samples (0-1).

    Garmin auto-pause omits records entirely while stopped, so a low value
    means a stop-heavy run, not a sensor dropout.
    """
    elapsed = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()
    if elapsed <= 0:
        raise MetricError("non-positive elapsed time")
    return min(len(df) / elapsed, 1.0)


def summarise(df: pd.DataFrame) -> dict:
    """One row's worth of run-level facts, for the output CSV."""
    return {
        "date": df["timestamp"].min().date(),
        "moving_min": round(len(df) / 60, 1),
        "distance_km": round(df["distance_m"].max() / 1000, 2),
        "avg_hr": round(df["heart_rate"].mean(), 1),
        "avg_pace_min_km": round(1000 / df["speed_mps"].mean() / 60, 2),
        "coverage": round(coverage(df), 3),
        "decoupling_pct": round(decoupling(df), 2),
    }

WARMUP_SAMPLES = 900  # 10 minutes at 1 Hz


def trim_warmup(df: pd.DataFrame, samples: int = WARMUP_SAMPLES) -> pd.DataFrame:
    """Drop the opening ramp, where HR lags pace and inflates efficiency.

    Decoupling is defined over the steady portion of a run. Including the
    warm-up puts an artificially efficient block in the first half and
    overstates the drop.
    """
    if len(df) <= samples + 2 * MIN_HALF_SAMPLES:
        raise MetricError("nothing left after trimming warm-up")
    return df.iloc[samples:].reset_index(drop=True)