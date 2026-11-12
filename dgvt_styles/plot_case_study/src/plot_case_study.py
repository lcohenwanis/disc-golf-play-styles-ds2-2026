"""
Case study figures: DGVTour #11 Cold Hollow Classic (Sep 26-27, 2026), Cold Hollow Long Layout,
MA2 division. 114 players across 9 divisions played this layout; strokes gained is measured
against all of them, not just MA2.

Input:  input/hole_features.csv (from build_hole_features), input/rounds.csv (from combine_seasons,
        for player names)
Output: output/event_<id>_layout_<id>_<division>_strokes_gained.pdf  cumulative strokes gained over 36 holes
        output/event_<id>_layout_<id>_<division>_sg_style_adj.pdf    style-adjusted strokes gained heatmap
        output/event_<id>_layout_<id>_hole_types.pdf                 course card: length and hole type
        output/event_<id>_layout_<id>_<division>_tied_128.pdf        four players who shot 128, by hole type

Run from this task's src/ directory (pdpp does this).
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

INPUT_DIR = Path("../input")
OUTPUT_DIR = Path("../output")

EVENT_ID, LAYOUT_ID, DIVISION = 98254, 778928, "MA2"
STARS = {"Jacob Dell": "winner", "Luc Cohen-Wanis": "me", "Nolan Smith": "60 then 72"}
ME = "Luc Cohen-Wanis"
TIED_SCORE = 128
PREFIX = f"event_{EVENT_ID}_layout_{LAYOUT_ID}"

# Chart colors: ink and gridlines, 3 highlight colors, diverging blue (gained) <-> red (lost), ordinal blue for hole type
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
HIGHLIGHT = ["#2a78d6", "#eb6834", "#1baf7a"]
SG_CMAP = LinearSegmentedColormap.from_list("sg", ["#b93332", "#f2a6a3", "#f0efec", "#9ec5f4", "#184f95"])
HOLE_TYPE_COLORS = {"short": "#86b6ef", "medium": "#2a78d6", "long": "#104281"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def save(fig, name):
    fig.savefig(OUTPUT_DIR / f"{name}.pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}.pdf")


def plot_strokes_gained_race(div_df):
    """Cumulative strokes gained vs the whole field on this layout, hole by hole across both rounds."""
    worm = (div_df.sort_values("hole_seq")
            .assign(cum_sg=lambda d: d.groupby("player_name")["strokes_gained"].cumsum())
            .pivot(index="hole_seq", columns="player_name", values="cum_sg"))
    worm.loc[0] = 0  # everyone starts at 0
    worm = worm.sort_index()

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name in worm.columns.difference(list(STARS)):
        ax.plot(worm.index, worm[name], color="#c3c2b7", linewidth=1, alpha=0.8)
    for (name, note), color in zip(STARS.items(), HIGHLIGHT):
        ax.plot(worm.index, worm[name], color=color, linewidth=2.2)
        ax.plot(36, worm.loc[36, name], "o", color=color, markersize=7, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"{name} ({note})  {worm.loc[36, name]:+.1f}", (36, worm.loc[36, name]),
                    xytext=(10, 0), textcoords="offset points", va="center", color=INK, fontsize=9.5)

    ax.axhline(0, color=INK_2, linewidth=1)
    ax.axvline(18.5, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(18.8, ax.get_ylim()[0], "Round 2", color=MUTED, va="bottom", fontsize=9)
    ax.text(0.3, ax.get_ylim()[0], "Round 1", color=MUTED, va="bottom", fontsize=9)
    ax.set_xlim(0, 36)
    ax.set_xticks(range(0, 37, 3))
    ax.set_xlabel("Hole (both rounds)")
    ax.set_ylabel("Cumulative strokes gained vs field")
    ax.set_title(f"{DIVISION} at the Cold Hollow Classic: strokes gained vs the whole field, "
                 f"all {len(worm.columns)} players", pad=24)
    ax.text(0, 1.015, f"Above 0 = ahead of the average player on this layout (all divisions). "
            f"Gray lines are the rest of {DIVISION}.", transform=ax.transAxes, color=INK_2, fontsize=9)
    save(fig, f"{PREFIX}_{DIVISION}_strokes_gained")


def plot_style_adjusted_heatmap(div_df, standings):
    """Each cell is the hole's strokes gained minus the player's own average for that round."""
    heat = div_df.pivot(index="player_name", columns="hole_seq", values="sg_style_adj").loc[standings.index]

    fig, ax = plt.subplots(figsize=(13, 8))
    lim = 2
    mesh = ax.pcolormesh(heat.columns, range(len(heat)), heat.values, cmap=SG_CMAP, vmin=-lim, vmax=lim,
                         edgecolors=SURFACE, linewidth=1.5, shading="nearest")
    ax.grid(False)
    ax.invert_yaxis()
    ax.set_yticks(range(len(heat)))
    ax.set_yticklabels([f"{name}  ({standings[name]})" for name in heat.index], fontsize=9, color=INK_2)
    for label in ax.get_yticklabels():
        if label.get_text().startswith(ME):
            label.set_fontweight("bold")
            label.set_color(INK)
    ax.set_xticks(range(1, 37))
    ax.set_xticklabels([str((h - 1) % 18 + 1) for h in range(1, 37)], fontsize=8)
    ax.axvline(18.5, color=INK_2, linewidth=2)
    ax.set_xlabel("Hole (round 1 | round 2)")
    ax.tick_params(length=0)
    for side in ["left", "bottom"]:
        ax.spines[side].set_visible(False)

    cbar = fig.colorbar(mesh, ax=ax, shrink=0.5, pad=0.01, extend="both")
    cbar.set_label("Style-adjusted strokes gained", color=INK_2)
    cbar.outline.set_visible(False)
    ax.set_title(f"{DIVISION} at the Cold Hollow Classic: where each round was won and lost", pad=24)
    ax.text(0, 1.015, "Blue = better than the player's own average hole that round, red = worse. "
            "Sorted by final score (in parentheses).", transform=ax.transAxes, color=INK_2, fontsize=9)
    save(fig, f"{PREFIX}_{DIVISION}_sg_style_adj")


def plot_course_card(card):
    """Each bar is a hole's length, colored by its type within its par; the label above is how the field scored it."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(card.index, card["length_ft"], width=0.8, color=card["hole_type"].astype(str).map(HOLE_TYPE_COLORS),
           edgecolor=SURFACE, linewidth=2)
    for hole, row in card.iterrows():
        ax.text(hole, row["length_ft"] + 12, f"{row.field_to_par:+.2f}", ha="center", fontsize=8.5, color=INK_2)
        ax.text(hole, 18, f"P{row.par}", ha="center", fontsize=8.5, color=SURFACE, fontweight="bold")
    ax.set_xticks(card.index)
    ax.set_xlim(0.4, 18.6)
    ax.set_xlabel("Hole")
    ax.set_ylabel("Length (ft)")
    ax.grid(axis="x", visible=False)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in HOLE_TYPE_COLORS.values()]
    ax.legend(handles, [t.title() for t in HOLE_TYPE_COLORS], title="Hole type (within par)", frameon=False,
              loc="lower right", ncols=3, bbox_to_anchor=(1, 1.0))
    ax.set_title("Cold Hollow Long Layout: no short holes", pad=24)
    ax.text(0, 1.03, "Number above each bar = field average score to par on that hole (both rounds, all divisions).",
            transform=ax.transAxes, color=INK_2, fontsize=9)
    save(fig, f"{PREFIX}_hole_types")


def plot_tied_players(div_df, standings, card):
    """Average style-adjusted strokes gained on each par x hole type, for the players tied at TIED_SCORE."""
    def hole_kind(d):
        return "Par " + d["par"].astype(str) + "\n" + d["hole_type"].astype(str)

    tied = standings[standings == TIED_SCORE].index
    profile = (div_df[div_df["player_name"].isin(tied)]
               .assign(hole_kind=hole_kind)
               .groupby(["hole_kind", "player_name"])["sg_style_adj"].mean()
               .unstack())
    holes_per_kind = card.assign(hole_kind=hole_kind)["hole_kind"].value_counts()
    order = [f"Par {par}\n{t}" for par in (3, 4, 5) for t in ("short", "medium", "long")]
    profile = profile.loc[[k for k in order if k in profile.index]]
    players = [ME] + [p for p in profile.columns if p != ME]
    colors = HIGHLIGHT + ["#eda100"]

    fig, ax = plt.subplots(figsize=(11, 5))
    width = 0.2
    x = np.arange(len(profile))
    for i, (player, color) in enumerate(zip(players, colors)):
        ax.bar(x + (i - 1.5) * width, profile[player], width=width - 0.03, color=color, label=player)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}\n({holes_per_kind[k]} hole{'s' if holes_per_kind[k] > 1 else ''} x 2 rounds)"
                        for k in profile.index])
    ax.set_ylabel("Avg style-adjusted strokes gained")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, ncols=4, loc="upper left", bbox_to_anchor=(0, 1.1))
    ax.set_title(f"Four {DIVISION} players, one score ({TIED_SCORE}): where each gained and lost", pad=30)
    ax.text(0, -0.2, "Par 4 long and par 5 are one hole each, so those bars are only 2 scores per player.",
            transform=ax.transAxes, color=INK_2, fontsize=9)
    save(fig, f"{PREFIX}_{DIVISION}_tied_{TIED_SCORE}")


if __name__ == "__main__":
    features = pd.read_csv(INPUT_DIR / "hole_features.csv", dtype={"player_key": str})
    rounds = pd.read_csv(INPUT_DIR / "rounds.csv", dtype={"player_key": str})

    event_df = features[(features["event_id"] == EVENT_ID) & (features["layout_id"] == LAYOUT_ID)].copy()
    event_df["hole_seq"] = (event_df["round"] - 1) * 18 + event_df["hole"]  # 1-36 across both rounds

    names = rounds.drop_duplicates("player_key").set_index("player_key")["player_name"]
    div_df = event_df[event_df["division"] == DIVISION].copy()
    div_df["player_name"] = div_df["player_key"].map(names)

    # Final standings in the division (lowest total first)
    standings = div_df.groupby("player_name")["score"].sum().sort_values()
    print(f"{event_df['player_key'].nunique()} players on this layout, {len(standings)} in {DIVISION}")

    card = (event_df.groupby("hole")
            .agg(par=("par", "first"), length_ft=("length_ft", "first"), hole_type=("hole_type", "first"),
                 field_to_par=("score_to_par", "mean")))

    plot_strokes_gained_race(div_df)
    plot_style_adjusted_heatmap(div_df, standings)
    plot_course_card(card)
    plot_tied_players(div_df, standings, card)
