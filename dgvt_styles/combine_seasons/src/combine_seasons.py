"""
Combine every season's processed tables into one table each, and flag training rows.

Input:  input/<year>/{events,holes,rounds,hole_scores}.csv, one folder per season
        (linked from _import_, which points at data/<year>/processed)
Output: output/{events,holes,rounds,hole_scores}.csv, all seasons, with a `year` column.
        rounds and hole_scores also get `has_pdga_number` and `in_training`: players with
        no PDGA number or no event-time rating stay in the data (they count toward strokes
        gained) but are flagged out of training data.

Run from this task's src/ directory (pdpp does this).
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # repo root, for dgvt_styles
from dgvt_styles.features import add_training_flag

INPUT_DIR = Path("../input")
OUTPUT_DIR = Path("../output")
TABLES = ["events", "holes", "rounds", "hole_scores"]
# player_key is a PDGA number or 'name:<name>'; read it as str so the same player isn't split into int and str keys
DTYPES = {"player_key": str}

seasons = sorted(p for p in INPUT_DIR.iterdir() if p.is_dir() and p.name.isdigit())
assert seasons, f"No season folders found in {INPUT_DIR.resolve()}"

for table in TABLES:
    combined = pd.concat(
        [pd.read_csv(season / f"{table}.csv", dtype=DTYPES).assign(year=int(season.name)) for season in seasons],
        ignore_index=True)
    if table in ("rounds", "hole_scores"):
        combined = add_training_flag(combined)
    combined.to_csv(OUTPUT_DIR / f"{table}.csv", index=False)
    print(f"{table}: {len(combined):,} rows from {len(seasons)} seasons ({seasons[0].name}-{seasons[-1].name})")
