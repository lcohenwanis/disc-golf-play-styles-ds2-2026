"""
Build the hole x player x round features:
  1. field_avg_to_par: the field's average score-to-par on the hole, a measure of difficulty.
  2. strokes_gained: the field's average score on the hole minus the player's score. The field
     is everyone on the same layout, round and hole, rated or not.
  3. sg_style_adj: strokes gained minus the player's own average for that round, so it shows
     where they gained and lost strokes instead of how many.
  4. hole_type: short, medium or long within each par (terciles of length).

Input:  input/hole_scores.csv (from combine_seasons)
Output: output/hole_features.csv     one row per player x hole x round, usable 2020+ rounds only
        output/hole_type_cutoffs.csv length range of each par x hole type

The feature logic lives in dgvt_styles.features, shared with the notebooks.
Run from this task's src/ directory (pdpp does this).
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # repo root, for dgvt_styles
from dgvt_styles.features import ROUND_KEYS, add_hole_types, add_strokes_gained, add_style_adjusted

INPUT_DIR = Path("../input")
OUTPUT_DIR = Path("../output")

hole_scores = pd.read_csv(INPUT_DIR / "hole_scores.csv", dtype={"player_key": str})

# 1. Strokes gained; add_strokes_gained filters to usable 2020+ rounds so incomplete,
#    mismatched, and sparse-coverage 2019 rounds remain available only in audit tables.
features = add_strokes_gained(hole_scores)
print(f"{len(features):,} hole scores in usable rounds; "
      f"{(~features['in_training']).sum():,} are in the field but not in training data")

# 2. Style-adjusted strokes gained
features = add_style_adjusted(features)
assert features.groupby(ROUND_KEYS)["sg_style_adj"].sum().abs().max() < 1e-9, \
    "style-adjusted strokes gained should sum to 0 in every player-round"

# 3. Hole types
features = add_hole_types(features)
print(f"{features['hole_type'].isna().mean():.1%} of hole scores have no hole type (no length_ft)")

cutoffs = (features.drop_duplicates(["layout_id", "hole"])
           .groupby(["par", "hole_type"], observed=True)["length_ft"]
           .agg(n_holes="count", min_ft="min", max_ft="max"))
print(cutoffs.to_string())

features.to_csv(OUTPUT_DIR / "hole_features.csv", index=False)
cutoffs.to_csv(OUTPUT_DIR / "hole_type_cutoffs.csv")
