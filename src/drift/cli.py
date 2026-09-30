"""Command line entry point: a folder of .fit files in, a CSV and a chart out."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from drift.filters import rejection_reason
from drift.metrics import MetricError, summarise, trim_warmup
from drift.parse import FitParseError, load_fit


def analyse_folder(data_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(data_dir.glob("*.fit")):
        try:
            df = trim_warmup(load_fit(path))
            row = summarise(df)
            row["rejected_for"] = rejection_reason(df)
        except (FitParseError, MetricError) as exc:
            print(f"skipped {path.name}: {exc}")
            continue
        row["file"] = path.name
        rows.append(row)

    if not rows:
        raise SystemExit(f"no usable activities in {data_dir}")
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def plot(df: pd.DataFrame, out: Path) -> None:
    import matplotlib.pyplot as plt

    steady = df[df["rejected_for"].isna()]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhline(5, color="grey", ls="--", lw=1, label="5% reference")
    ax.axhline(0, color="black", lw=0.8)
    ax.scatter(steady["date"], steady["decoupling_pct"], s=60, label="steady runs")
    ax.set_ylabel("decoupling (%)")
    ax.set_title(f"Aerobic decoupling, {len(steady)} steady runs")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(prog="drift")
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    df = analyse_folder(args.data_dir)
    df.to_csv(args.out / "runs.csv", index=False)
    plot(df, args.out / "decoupling.png")

    steady = df["rejected_for"].isna().sum()
    print(f"{len(df)} runs analysed, {steady} steady")
    print(df["rejected_for"].value_counts(dropna=False).to_string())    