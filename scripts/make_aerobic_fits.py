"""Write synthetic .fit files that pass every filter and show a decoupling trend.

Ten weekly easy runs matching RUNS below, flat, constant pace, 1 Hz. HR ramps over the
first 10 minutes, then drifts upward; the drift shrinks week by week, so
decoupling should fall from ~8% to ~2% across the block.

    python scripts/make_aerobic_fits.py data/aerobic
"""

from __future__ import annotations

import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)

# (field number, size, base type) for the record message, in write order
RECORD_FIELDS = [
    (253, 4, 0x86),  # timestamp, uint32
    (3, 1, 0x02),    # heart_rate, uint8
    (5, 4, 0x86),    # distance, uint32, scale 100
    (73, 4, 0x86),   # enhanced_speed, uint32, scale 1000
    (78, 4, 0x86),   # enhanced_altitude, uint32, scale 5, offset 500
]


def _crc(data: bytes, crc: int = 0) -> int:
    table = [0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
             0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400]
    for byte in data:
        for nibble in (byte & 0xF, byte >> 4):
            tmp = table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ table[nibble]
    return crc


def _definition(local: int, global_num: int, fields: list[tuple[int, int, int]]) -> bytes:
    out = struct.pack("<BBBHB", 0x40 | local, 0, 0, global_num, len(fields))
    return out + b"".join(struct.pack("<BBB", *f) for f in fields)


def write_fit(path: Path, start: datetime, hr, speed, altitude) -> None:
    ts0 = int((start - FIT_EPOCH).total_seconds())
    body = bytearray()

    # file_id: type=activity(4), manufacturer=development(255), time_created
    body += _definition(0, 0, [(0, 1, 0x00), (1, 2, 0x84), (4, 4, 0x86)])
    body += struct.pack("<BBHI", 0, 4, 255, ts0)

    body += _definition(1, 20, RECORD_FIELDS)
    distance = np.cumsum(speed)
    for i in range(len(hr)):
        body += struct.pack(
            "<BIBIII", 1, ts0 + i, int(round(hr[i])), int(round(distance[i] * 100)),
            int(round(speed[i] * 1000)), int(round((altitude[i] + 500) * 5)),
        )

    header = struct.pack("<BBHI4s", 14, 0x20, 2132, len(body), b".FIT")
    header += struct.pack("<H", _crc(header))
    data = header + bytes(body)
    path.write_bytes(data + struct.pack("<H", _crc(data)))


# date, moving minutes, distance km, target avg HR (after warm-up trim)
RUNS = [
    ("2025-03-02", 102.8, 16.3, 173),
    ("2025-03-09", 89.0, 14.1, 169),
    ("2025-03-16", 105.6, 17.5, 173),
    ("2025-03-23", 86.8, 15.2, 179),
    ("2025-03-30", 90.8, 15.4, 170),
    ("2025-04-06", 80.6, 14.2, 173),
    ("2025-04-13", 86.3, 15.6, 174),
    ("2025-04-20", 102.3, 16.9, 156),
    ("2025-04-27", 82.6, 14.0, 157),
    ("2025-05-04", 86.5, 15.23, 160),
]
WARMUP_S = 900  # matches drift.metrics.WARMUP_SAMPLES


def make_run(minutes: float, distance_km: float, avg_hr: float, drift: float, rng):
    """1 Hz run: 10 min HR ramp from rest, then linear drift of `drift` fraction.

    Speed is scaled so the run covers exactly `distance_km`; HR is scaled so
    its mean after the warm-up trim is `avg_hr`.
    """
    n = int(round(minutes * 60))
    t = np.arange(n)
    ramp = np.clip(t / 600, 0, 1)
    hr = 95 + (avg_hr - 95) * ramp
    after = np.clip(t - 600, 0, None) / (n - 600)
    hr = hr * (1 + drift * after) + rng.normal(0, 1.5, n)
    hr *= avg_hr / hr[WARMUP_S:].mean()
    speed = distance_km * 1000 / n + rng.normal(0, 0.05, n)
    speed *= distance_km * 1000 / speed.sum()
    altitude = 40 + rng.normal(0, 0.3, n)
    return hr, speed, altitude


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/aerobic")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    drifts = np.linspace(0.16, 0.04, len(RUNS))  # HR rise over the steady part
    for (date, minutes, distance_km, avg_hr), drift in zip(RUNS, drifts):
        when = datetime.fromisoformat(date).replace(hour=8, minute=30, tzinfo=timezone.utc)
        hr, speed, alt = make_run(minutes, distance_km, avg_hr, drift, rng)
        path = out / f"{when:%Y%m%d_%H%M%S}_long_easy_ACTIVITY.fit"
        write_fit(path, when, hr, speed, alt)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
