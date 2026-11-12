"""
Data quality checks on the combined tables: what's missing, and who has no event-time rating.

Input:  input/hole_scores.csv, input/rounds.csv (from combine_seasons)
Output: output/null_percentages.csv     % of hole-score rows missing each column
        output/null_heatmap.png         where the missing values are, rows sorted by season
        output/rating_status_counts.csv rounds by rating status (rated / unrated at the time /
                                        no PDGA number), all rounds and usable rounds

Also checks that unrated rounds by players with a PDGA number come before the player's first
rated round (or the player is never rated), i.e. they're first events, not missing data.

Run from this task's src/ directory (pdpp does this).
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

INPUT_DIR = Path("../input")
OUTPUT_DIR = Path("../output")

hole_scores = pd.read_csv(INPUT_DIR / "hole_scores.csv", dtype={"player_key": str})
rounds = pd.read_csv(INPUT_DIR / "rounds.csv", dtype={"player_key": str})

# What's missing: event_rating and pdga_number (players without a rating), length_ft (a few courses)
source_columns = hole_scores.columns.drop(["has_pdga_number", "in_training"])
null_percentage = (hole_scores[source_columns].isnull().mean() * 100).round(2).sort_values(ascending=False)
null_percentage.rename("pct_missing").to_csv(OUTPUT_DIR / "null_percentages.csv", index_label="column")
print(null_percentage[null_percentage > 0].to_string())

plt.figure(figsize=(12, 6))
sns.heatmap(hole_scores[source_columns].sort_values("year").T.isnull(), cbar=False)
plt.title("Heatmap of Null Values in Hole Scores DataFrame")
plt.savefig(OUTPUT_DIR / "null_heatmap.png", dpi=150, bbox_inches="tight")
plt.close()


def rating_status(df):
    status = pd.Series("PDGA number, unrated at the time", index=df.index)
    status[df["in_training"]] = "rated"
    status[~df["has_pdga_number"]] = "no PDGA number"
    return status


status_counts = pd.DataFrame({
    "all rounds": rating_status(rounds).value_counts(),
    "usable rounds": rating_status(rounds[rounds["usable"]]).value_counts(),
})
status_counts.to_csv(OUTPUT_DIR / "rating_status_counts.csv", index_label="rating_status")
print(status_counts.to_string())

# Unrated rounds by players with a PDGA number come before their first rated round (or they're never rated)
first_rated = rounds[rounds["in_training"]].groupby("player_key")["round_date"].min()
unrated = rounds[rounds["has_pdga_number"] & ~rounds["in_training"]]
later_rated = unrated["round_date"] < unrated["player_key"].map(first_rated)
never_rated = unrated["player_key"].map(first_rated).isna()
assert (later_rated | never_rated).all(), "Some unrated rounds come after the player was already rated"
print(f"Unrated rounds with a PDGA number: {later_rated.sum()} before the player's first rated round, "
      f"{never_rated.sum()} by players never rated in this data")
