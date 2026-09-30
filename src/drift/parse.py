"""Read Garmin .FIT activity files into tidy per-record DataFrames."""

from __future__ import annotations

from pathlib import Path

import fitdecode
import pandas as pd

# (preferred, fallback) — newer Garmin firmware writes only the "enhanced_"
# variants; older devices write the plain names. Confirmed against
# Forerunner exports; see README limitations.
_FIELDS: dict[str, tuple[str, str | None]] = {
    "timestamp": ("timestamp", None),
    "speed_mps": ("enhanced_speed", "speed"),
    "altitude_m": ("enhanced_altitude", "altitude"),
    "heart_rate": ("heart_rate", None),
    "distance_m": ("distance", None),
    "activity_type": ("activity_type", None),
}

REQUIRED = ("timestamp", "speed_mps", "heart_rate")
MIN_MOVING_SAMPLES = 60


class FitParseError(ValueError):
    """Raised when a file cannot be turned into a usable record stream."""


def _row(frame: fitdecode.FitDataMessage) -> dict:
    values = {f.name: f.value for f in frame.fields}
    row = {}
    for out_name, (primary, fallback) in _FIELDS.items():
        value = values.get(primary)
        if value is None and fallback is not None:
            value = values.get(fallback)
        row[out_name] = value
    return row


def load_fit(path: str | Path, min_speed_mps: float = 0.5) -> pd.DataFrame:
    """Return one row per moving record: timestamp, speed, HR, altitude, distance.

    Records slower than ``min_speed_mps`` are dropped, so row count is a
    proxy for moving time rather than elapsed time.
    """
    path = Path(path)
    rows = [
        _row(frame)
        for frame in fitdecode.FitReader(path)
        if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == "record"
    ]

    if not rows:
        raise FitParseError(f"{path.name}: no record messages")

    df = pd.DataFrame(rows)

    empty = [c for c in REQUIRED if df[c].isna().all()]
    if empty:
        raise FitParseError(f"{path.name}: no data for {', '.join(empty)}")

    df = (
        df.dropna(subset=list(REQUIRED))
        .sort_values("timestamp")
        .loc[lambda d: d["speed_mps"] >= min_speed_mps]
        .reset_index(drop=True)
    )

    if len(df) < MIN_MOVING_SAMPLES:
        raise FitParseError(f"{path.name}: only {len(df)} moving samples")

    return df