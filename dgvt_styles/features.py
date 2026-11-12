"""
Stage 3 helpers shared by the notebooks, so every analysis builds strokes gained and
decides who goes into training data the same way.

Players with no event-time rating (no PDGA number, or unrated at the time of the event):
  - DO count toward the field average, so strokes gained compares every player against
    everyone who actually played the hole that round.
  - Are NOT used as training data (style profiles, clustering, models), since there is
    no rating to adjust for skill. Unrated rounds are always a player's first events or
    by players who never get a rating, so a player's later, rated rounds still count.
"""

import pandas as pd

# Everyone who played the same hole, on the same layout, in the same round of an event.
# Divisions on different tees have different layout_ids, so they aren't mixed.
FIELD_KEYS = ["event_id", "round", "layout_id", "hole"]
# One player's round.
ROUND_KEYS = ["event_id", "round", "layout_id", "player_key"]
HOLE_TYPES = ["short", "medium", "long"]
ANALYSIS_START_YEAR = 2020


def add_training_flag(df):
    """Add `has_pdga_number` and `in_training` to a rounds or hole-scores table.

    `in_training` is True when the row has a PDGA number and an event-time rating.
    Needs the `pdga_number` and `event_rating` columns.
    """
    df = df.copy()
    df["has_pdga_number"] = df["pdga_number"].notna()
    df["in_training"] = df["has_pdga_number"] & df["event_rating"].notna()
    return df


def add_strokes_gained(hole_scores):
    """Keep usable rounds from 2020 onward and add field difficulty and SG fields.

    Strokes gained is the field's average score on the hole minus the player's score
    (positive = beat the field). The field includes every player in a usable round,
    with or without a rating. The 2019 rows remain available in the combined audit
    tables but are excluded because only 2 of 8 events have hole-by-hole scores.
    `field_avg_to_par` is the field's average score-to-par on that same hole.
    """
    df = hole_scores[
        hole_scores["round_usable"] & (hole_scores["year"] >= ANALYSIS_START_YEAR)
    ].copy()
    field = df.groupby(FIELD_KEYS)
    df["field_avg"] = field["score"].transform("mean")
    df["field_avg_to_par"] = field["score_to_par"].transform("mean")
    df["field_n"] = field["score"].transform("size")   # small fields give noisy averages
    df["strokes_gained"] = df["field_avg"] - df["score"]
    return df


def add_style_adjusted(features):
    """Add `round_sg_avg` and `sg_style_adj` to a table from `add_strokes_gained`.

    Style-adjusted strokes gained subtracts the player's average strokes gained per hole
    in that round, which removes skill and the day's form and leaves only where in the
    round they gained or lost strokes. It sums to 0 within every player-round. Using the
    round (not a career average) keeps seasons separate.
    """
    df = features.copy()
    df["round_sg_avg"] = df.groupby(ROUND_KEYS)["strokes_gained"].transform("mean")
    df["sg_style_adj"] = df["strokes_gained"] - df["round_sg_avg"]
    return df


def add_hole_types(features):
    """Add `hole_type`: short, medium or long within each par.

    Cutoffs are terciles of length within each par, computed over distinct layout x hole
    combinations so courses that hosted many events don't pull the cutoffs toward their
    holes. Holes with no `length_ft` get no hole type.
    """
    unique_holes = features.drop_duplicates(["layout_id", "hole"])[["layout_id", "hole", "par", "length_ft"]].copy()
    unique_holes["hole_type"] = (
        unique_holes.groupby("par")["length_ft"]
        .transform(lambda lengths: pd.qcut(lengths, 3, labels=HOLE_TYPES))
    )
    df = features.drop(columns="hole_type", errors="ignore").merge(
        unique_holes[["layout_id", "hole", "hole_type"]], on=["layout_id", "hole"], how="left")
    df["hole_type"] = pd.Categorical(df["hole_type"], categories=HOLE_TYPES, ordered=True)
    return df
