# PA-HR

Calculates pace to heart rate efficiency (Pa:HR decoupling) from Garmin `.fit` running files.

Point `drift` at a folder of activities and it returns a CSV with one row per run and a chart of
decoupling over time. Runs that are too short, too variable or stop too often are flagged
instead of being scored, because decoupling is only meaningful on a steady effort.

## What is aerobic decoupling?

On a steady easy run, your heart rate usually creeps up over time while your pace stays the
same. Aerobic decoupling measures how much that happens.

For each half of a run, `drift` calculates an **efficiency factor**:

```
EF = mean speed (m/s) / mean heart rate (bpm)
```

Decoupling is the percentage drop in EF from the first half to the second:

```
decoupling % = (EF_first − EF_second) / EF_first × 100
```

- **Positive**: efficiency fell. The same heart rate bought less speed later in the run.
- **Around 0**: heart rate and pace stayed in step.
- **Negative**: the second half was more efficient than the first.

A common rule of thumb is that under about 5% on a long easy run indicates a solid aerobic
base. The chart draws a dashed line at 5% for reference. Treat it as a guide, not a hard limit.

## Installation

Requires Python 3.11 or newer.

```bash
git clone <repo-url> PA-HR
cd PA-HR
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `drift` command. Drop the `[dev]` if you don't need pytest and ruff.

## Usage

Export your runs from Garmin Connect as original `.fit` files and put them in a folder.
Subfolders are searched too.

```bash
drift data/ --out results/
```

| Argument      | Default    | Description                                      |
| ------------- | ---------- | ------------------------------------------------ |
| `data_dir`    | (required) | Folder to search recursively for `.fit` files    |
| `--out`       | `results/` | Output folder, created if it doesn't exist       |

Files that can't be read, or that have too little usable data, are skipped with a message:

```
skipped 12345_ACTIVITY.fit: no data for heart_rate
```

The terminal prints a summary of how many runs were analysed and why any were rejected.

### Output

`results/runs.csv` has one row per run, sorted by date:

| Column            | Meaning                                                              |
| ----------------- | -------------------------------------------------------------------- |
| `date`            | Start date of the run                                                |
| `moving_min`      | Moving time after the warm-up trim, in minutes                       |
| `distance_km`     | Total distance from the watch                                        |
| `avg_hr`          | Mean heart rate after the warm-up trim                               |
| `avg_pace_min_km` | Mean pace in decimal minutes per km (so `5.5` is 5:30/km)            |
| `coverage`        | Fraction of elapsed time spent moving (0 to 1)                       |
| `decoupling_pct`  | Aerobic decoupling, as defined above                                 |
| `rejected_for`    | Why the run isn't steady enough to trust. Empty means it passed      |
| `file`            | Path to the source file, relative to `data_dir`                      |

Rejected runs stay in the CSV so you can see them, but they're left off the chart.

`results/decoupling.png` plots decoupling against date for steady runs only.

## How it works

1. **Parse** (`parse.py`). Reads `record` messages from each file and keeps timestamp, speed,
   heart rate, altitude and distance. It prefers the `enhanced_speed` and `enhanced_altitude`
   fields newer Garmin firmware writes, and falls back to `speed` and `altitude` for older
   devices. Samples slower than 0.5 m/s are dropped, so the remaining rows are moving time only.
2. **Trim the warm-up** (`metrics.py`). Drops the first 900 samples (15 minutes at 1 Hz).
   Early in a run, heart rate lags behind pace, which makes the first half look artificially
   efficient and overstates decoupling.
3. **Filter** (`filters.py`). Checks whether the run is steady enough to score.
4. **Measure** (`metrics.py`). Splits the remaining samples in half by count and compares
   the efficiency factor of each half.

### Steadiness filters

A run is rejected, with the first reason that applies, if:

| Reason                  | Rule                                                           |
| ----------------------- | -------------------------------------------------------------- |
| `too short`             | Less than 15 minutes of moving time left after the warm-up     |
| `heart rate too variable` | Heart rate coefficient of variation above 0.08               |
| `pace too variable`     | Speed coefficient of variation above 0.15                      |
| `too much stopped time` | Coverage below 0.85, meaning more than 15% of the time stopped |

These thresholds were tuned by trial and error, not derived from research. Intervals,
fartleks, hilly trail runs and runs with lots of traffic-light stops will usually be rejected,
which is intended. If good runs are being rejected, or obviously unsteady ones are getting
through, adjust the constants at the top of `src/drift/filters.py`.

## Synthetic test data

`scripts/make_aerobic_fits.py` writes ten synthetic weekly long runs as valid `.fit` files.
They are flat, run at constant pace and have heart rate drift that shrinks each week, so
decoupling falls from about 7% to about 2% across the block. Use them to try the tool
without your own data, or to check that changes haven't shifted the results.

```bash
python scripts/make_aerobic_fits.py data/aerobic
drift data/aerobic --out results/aerobic
```

Expected output:

```
10 runs analysed, 10 steady
```

This data is generated, not recorded. It shows what the tool produces on an idealised
training block, not real-world results.

## Development

```bash
pytest          # run the tests
ruff check .    # lint
```

The tests in `tests/test_metrics.py` build synthetic record frames directly, so they don't need
any `.fit` files.

`data/`, `results/` and `scratch/` are in `.gitignore`, so your activity files and outputs
stay out of the repository.

## Limitations

- **Assumes 1-second recording.** Moving time, the warm-up trim and the minimum length are all
  calculated from sample counts. With Garmin's "Smart" recording, samples are irregular, so these
  are underestimated and coverage looks low. Runs are likely to be rejected as
  `too much stopped time`. Set your watch to 1-second recording for accurate results.
- **Field names have only been checked against Forerunner exports.** Other Garmin models and
  other brands' `.fit` files may use different fields and fail to parse.
- **Terrain is ignored.** Altitude is read but not used, so a run that's flat out and hilly back
  will show decoupling caused by the hills, not fitness.
- **Heat, hydration, fatigue and sensor errors aren't accounted for.** Wrist-based heart rate
  in particular can spike or drop out and skew a run's result.
- **Running only.** The tool doesn't check the activity type, so cycling or other files in
  the folder will be analysed as if they were runs.

