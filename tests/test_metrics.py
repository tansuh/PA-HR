import numpy as np
import pandas as pd
import pytest

from drift.filters import rejection_reason
from drift.metrics import MetricError, coverage, decoupling, trim_warmup


def make_run(speed, heart_rate, n=1800, start="2025-01-01 09:00:00", freq_s=1):
    """Build a synthetic record frame. Scalars are broadcast to length n."""
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=n, freq=f"{freq_s}s", tz="UTC"),
        "speed_mps": np.broadcast_to(speed, n).astype(float),
        "heart_rate": np.broadcast_to(heart_rate, n).astype(float),
    })


def test_perfectly_steady_run_has_no_decoupling():
    assert decoupling(make_run(3.0, 150)) == pytest.approx(0.0)


def test_heart_rate_drift_produces_positive_decoupling():
    # Same pace, HR 10% higher in the second half: 1 - 1/1.1 = 9.09%
    hr = np.concatenate([np.full(900, 150.0), np.full(900, 165.0)])
    assert decoupling(make_run(3.0, hr)) == pytest.approx(9.0909, abs=0.01)


def test_too_few_samples_raises():
    with pytest.raises(MetricError):
        decoupling(make_run(3.0, 150, n=50))


def test_coverage_detects_auto_pause_gaps():
    # 1800 samples spread over 3600s of elapsed time = half the run stopped
    df = make_run(3.0, 150, n=1800, freq_s=2)
    assert coverage(df) == pytest.approx(0.5, abs=0.01)


def test_interval_session_is_rejected_for_pace():
    speed = np.tile(np.concatenate([np.full(60, 5.0), np.full(60, 2.0)]), 15)
    assert rejection_reason(make_run(speed, 150)) == "pace too variable"


def test_warmup_trim_removes_the_opening_ramp():
    hr = np.concatenate([np.linspace(110, 175, 900), np.full(900, 175.0)])
    df = make_run(3.0, hr)
    trimmed = trim_warmup(df, samples=900)
    assert len(trimmed) == 900
    assert trimmed["heart_rate"].std() == pytest.approx(0.0, abs=0.01)