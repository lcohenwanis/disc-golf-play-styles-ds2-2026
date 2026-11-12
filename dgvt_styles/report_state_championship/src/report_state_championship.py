"""
Case study and short report: DGVTour Finals - Vermont State Championship (PDGA 98262), October 10-11, 2026.
A look at every division, then a focus on MA2.

Input:  input/hole_features.csv (from build_hole_features), input/rounds.csv and input/events.csv
        (from combine_seasons)
Output: output/report.md                                           the summary report (links the figures below)
        output/event_98262_all_divisions_vs_rating.{png,pdf}       round ratings vs event-time rating, every division
        output/event_98262_MA2_strokes_gained.{png,pdf}            cumulative strokes gained over 36 holes
        output/event_98262_MA2_sg_style_adj.{png,pdf}              style-adjusted strokes gained heatmap
        output/event_98262_MA2_course_cards.{png,pdf}              MA2's two layouts: length, hole type, scoring

Every number in the report is computed here, so rerunning after a re-scrape updates it.
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

EVENT_ID, DIVISION = 98262, "MA2"
ME = "Luc Cohen-Wanis"
PREFIX = f"event_{EVENT_ID}"

# Chart colors: ink and gridlines, 3 highlight colors, diverging blue (gained) <-> red (lost), ordinal blue for hole type
INK, INK_2, MUTED, GRID, SURFACE, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb", "#c3c2b7"
HIGHLIGHT = ["#2a78d6", "#eb6834", "#1baf7a"]
SG_CMAP = LinearSegmentedColormap.from_list("sg", ["#b93332", "#f2a6a3", "#f0efec", "#9ec5f4", "#184f95"])
HOLE_TYPE_COLORS = {"short": "#86b6ef", "medium": "#2a78d6", "long": "#104281"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def save(fig, name):
    for ext, dpi in (("png", 200), ("pdf", 300)):
        fig.savefig(OUTPUT_DIR / f"{name}.{ext}", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}.png/.pdf")
    return f"{name}.png"


def subtitle(ax, text, y=1.015):
    ax.text(0, y, text, transform=ax.transAxes, color=INK_2, fontsize=9)


def fmt_to_par(x):
    return "E" if x == 0 else f"{int(x):+d}"


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
features = pd.read_csv(INPUT_DIR / "hole_features.csv", dtype={"player_key": str})
rounds = pd.read_csv(INPUT_DIR / "rounds.csv", dtype={"player_key": str})
events = pd.read_csv(INPUT_DIR / "events.csv")

event = events.set_index("event_id").loc[EVENT_ID]
ev_rounds = rounds[rounds["event_id"] == EVENT_ID].copy()
ev_holes = features[features["event_id"] == EVENT_ID].copy()
ev_holes["hole_seq"] = (ev_holes["round"] - 1) * 18 + ev_holes["hole"]  # 1-36 across both rounds
names = ev_rounds.drop_duplicates("player_key").set_index("player_key")["player_name"]
ev_holes["player_name"] = ev_holes["player_key"].map(names)
n_rounds = int(event["n_rounds"])

# One row per player: completed both rounds with a real score, total to par, average round rating
scored = ev_rounds[ev_rounds["round_score"].notna() & ~ev_rounds["unfinished_999"] & (ev_rounds["round_score"] > 0)]
players = (ev_rounds.groupby(["division", "player_key"])
           .agg(name=("player_name", "first"), rating=("event_rating", "first"))
           .join(scored.groupby(["division", "player_key"])
                 .agg(rounds_scored=("round", "nunique"), total=("round_score", "sum"),
                      to_par=("round_to_par", "sum"), avg_round_rating=("round_rating", "mean")))
           .reset_index())
players["finished"] = players["rounds_scored"] == n_rounds
players["vs_rating"] = players["avg_round_rating"] - players["rating"]

finishers = players[players["finished"]].sort_values(["division", "to_par"])
divisions = players.groupby("division").agg(players=("player_key", "size"), median_rating=("rating", "median"))
best = finishers.groupby("division").head(1).set_index("division")
runner_up = finishers.groupby("division").nth(1).set_index("division")["to_par"]
n_tied = finishers.merge(best[["to_par"]].rename(columns={"to_par": "best"}), left_on="division", right_index=True) \
    .query("to_par == best").groupby("division").size()
divisions = divisions.join(best[["name", "to_par", "avg_round_rating"]]).join(runner_up.rename("second"))
divisions["margin"] = divisions["second"] - divisions["to_par"]
divisions["n_tied"] = n_tied
divisions = divisions.sort_values("median_rating", ascending=False, na_position="last")

layouts = (ev_rounds.groupby(["round", "layout_id"])
           .agg(layout=("layout_name", lambda s: " ".join(s.iloc[0].split()).removeprefix(f"{event['year']} ")), course=("course_name", "first"),
                par=("layout_par", "first"), field=("player_key", "size"),
                divisions=("division", lambda s: ", ".join(sorted(s.unique()))))
           .reset_index())
courses = sorted(ev_rounds["course_name"].unique())

# MA2
div_holes = ev_holes[ev_holes["division"] == DIVISION].copy()
div_players = finishers[finishers["division"] == DIVISION].copy()
by_round = scored[scored["division"] == DIVISION].pivot_table(index="player_name", columns="round", values="round_score")
standings = div_players.set_index("name")["total"].sort_values()
div_players["place"] = div_players["total"].rank(method="min").astype(int)
place = div_players.set_index("name")["place"]
div_layouts = layouts[layouts["divisions"].str.split(", ").apply(lambda d: DIVISION in d)].sort_values("round")
round_avg_to_par = scored[scored["division"] == DIVISION].groupby("round")["round_to_par"].mean()

winner = standings.index[0]
turnaround = (by_round[1] - by_round[2]).sort_values(ascending=False)
comeback = turnaround.index[0]
STARS = {winner: "winner", ME: "me", comeback: f"{int(by_round.loc[comeback, 1])} then {int(by_round.loc[comeback, 2])}"}
if len(STARS) < 3:   # if the winner or I also had the biggest turnaround, highlight the runner-up instead
    STARS[standings.index[1]] = "2nd"


# ---------------------------------------------------------------------------
# Figure 1: every division, round ratings vs event-time rating
# ---------------------------------------------------------------------------
def plot_all_divisions():
    data = players.dropna(subset=["vs_rating"])
    order = [d for d in divisions.index if d in data["division"].unique()]
    rng = np.random.default_rng(0)

    fig, ax = plt.subplots(figsize=(10, 0.42 * len(order) + 1.6))
    for y, division in enumerate(order):
        pts = data[data["division"] == division]
        color = HIGHLIGHT[0] if division == DIVISION else "#a3a29d"
        jitter = y + rng.uniform(-0.18, 0.18, len(pts))
        ax.scatter(pts["vs_rating"], jitter, s=26, color=color, alpha=0.8, linewidth=0, zorder=3)
        win = pts[pts["name"] == divisions.loc[division, "name"]]
        ax.scatter(win["vs_rating"], [y] * len(win), s=70, marker="D", facecolor="none", edgecolor=INK,
                   linewidth=1.2, zorder=4)
        ax.text(1.01, y, f"{len(pts)}", transform=ax.get_yaxis_transform(), va="center", fontsize=8, color=MUTED)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{d}  ({divisions.loc[d, 'median_rating']:.0f})" for d in order], fontsize=9)
    for label in ax.get_yticklabels():
        if label.get_text().startswith(DIVISION + " "):
            label.set_color(HIGHLIGHT[0])
            label.set_fontweight("bold")
    ax.set_ylim(len(order) - 0.5, -0.6)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Average round rating minus event-time rating (points)")
    ax.set_title(f"Who played above their rating? {event['name'].split(' - ')[-1]}, all divisions", pad=36)
    subtitle(ax, "Each dot is a player with an event-time rating and round ratings; diamonds mark division winners.\n"
                 "Divisions sorted by median rating (in parentheses); number at right = players.")
    return save(fig, f"{PREFIX}_all_divisions_vs_rating")


# ---------------------------------------------------------------------------
# Figure 2: MA2 strokes gained race
# ---------------------------------------------------------------------------
def plot_strokes_gained_race():
    worm = (div_holes.sort_values("hole_seq")
            .assign(cum_sg=lambda d: d.groupby("player_name")["strokes_gained"].cumsum())
            .pivot(index="hole_seq", columns="player_name", values="cum_sg"))
    worm.loc[0] = 0
    worm = worm.sort_index()
    last = worm.index.max()

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for name in worm.columns.difference(list(STARS)):
        ax.plot(worm.index, worm[name], color=AXIS, linewidth=1, alpha=0.8)
    for (name, note), color in zip(STARS.items(), HIGHLIGHT):
        end = worm[name].dropna()
        ax.plot(end.index, end, color=color, linewidth=2.2)
        ax.plot(end.index[-1], end.iloc[-1], "o", color=color, markersize=7, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"{name} ({note})  {end.iloc[-1]:+.1f}", (end.index[-1], end.iloc[-1]),
                    xytext=(10, 0), textcoords="offset points", va="center", color=INK, fontsize=9.5)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.axvline(18.5, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    r1, r2 = div_layouts.iloc[0], div_layouts.iloc[1]
    ax.text(0.3, ax.get_ylim()[0], f"Round 1: {r1['layout']}", color=MUTED, va="bottom", fontsize=9)
    ax.text(18.8, ax.get_ylim()[0], f"Round 2: {r2['layout']}", color=MUTED, va="bottom", fontsize=9)
    ax.set_xlim(0, last)
    ax.set_xticks(range(0, last + 1, 3))
    ax.set_xlabel("Hole (both rounds)")
    ax.set_ylabel("Cumulative strokes gained vs field")
    ax.set_title(f"{DIVISION} at the State Championship: strokes gained, all {len(worm.columns)} players", pad=24)
    subtitle(ax, f"Field = everyone on the same layout that round ({r1['field']} players in round 1, {r2['field']} in "
                 f"round 2). Gray lines are the rest of {DIVISION}.")
    return save(fig, f"{PREFIX}_{DIVISION}_strokes_gained")


# ---------------------------------------------------------------------------
# Figure 3: MA2 style-adjusted heatmap
# ---------------------------------------------------------------------------
def plot_style_adjusted_heatmap():
    heat = div_holes.pivot(index="player_name", columns="hole_seq", values="sg_style_adj")
    heat = heat.loc[[n for n in standings.index if n in heat.index]]

    fig, ax = plt.subplots(figsize=(13, 0.3 * len(heat) + 1.8))
    mesh = ax.pcolormesh(heat.columns, range(len(heat)), heat.values, cmap=SG_CMAP, vmin=-2, vmax=2,
                         edgecolors=SURFACE, linewidth=1.2, shading="nearest")
    ax.grid(False)
    ax.invert_yaxis()
    ax.set_yticks(range(len(heat)))
    ax.set_yticklabels([f"{name}  ({int(standings[name])})" for name in heat.index], fontsize=8.5, color=INK_2)
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
    cbar = fig.colorbar(mesh, ax=ax, shrink=0.4, pad=0.01, extend="both")
    cbar.set_label("Style-adjusted strokes gained", color=INK_2)
    cbar.outline.set_visible(False)
    ax.set_title(f"{DIVISION} at the State Championship: where each round was won and lost", pad=24)
    subtitle(ax, "Blue = better than the player's own average hole that round, red = worse. Sorted by final score "
                 "(in parentheses).", y=1.005)
    return save(fig, f"{PREFIX}_{DIVISION}_sg_style_adj")


# ---------------------------------------------------------------------------
# Figure 4: MA2's two layouts
# ---------------------------------------------------------------------------
def course_card_data():
    return (div_holes.groupby(["round", "hole"])
            .agg(par=("par", "first"), length_ft=("length_ft", "first"), hole_type=("hole_type", "first"),
                 div_to_par=("score_to_par", "mean"))
            .reset_index())


def plot_course_cards(cards):
    fig, axes = plt.subplots(len(div_layouts), 1, figsize=(12, 4.2 * len(div_layouts)), sharey=True)
    for ax, (_, lay) in zip(np.atleast_1d(axes), div_layouts.iterrows()):
        card = cards[cards["round"] == lay["round"]].set_index("hole")
        ax.bar(card.index, card["length_ft"], width=0.8, color=card["hole_type"].astype(str).map(HOLE_TYPE_COLORS),
               edgecolor=SURFACE, linewidth=2)
        for hole, row in card.iterrows():
            ax.text(hole, row["length_ft"] + 15, f"{row.div_to_par:+.2f}", ha="center", fontsize=8.5, color=INK_2)
            ax.text(hole, 25, f"P{row.par}", ha="center", fontsize=8.5, color=SURFACE, fontweight="bold")
        ax.set_xticks(card.index)
        ax.set_xlim(0.4, 18.6)
        ax.set_ylabel("Length (ft)")
        ax.grid(axis="x", visible=False)
        ax.set_title(f"Round {lay['round']}: {lay['layout']} (par {lay['par']}), {DIVISION} averaged "
                     f"{fmt_to_par(round(round_avg_to_par[lay['round']]))}", fontsize=11, pad=10)
    np.atleast_1d(axes)[-1].set_xlabel("Hole")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in HOLE_TYPE_COLORS.values()]
    fig.legend(handles, [t.title() for t in HOLE_TYPE_COLORS], title="Hole type (within par, all DGVT holes)",
               frameon=False, loc="upper right", ncols=3, bbox_to_anchor=(0.98, 1.0))
    fig.suptitle(f"{DIVISION}'s two courses", x=0.06, ha="left", fontweight="bold", fontsize=13, y=1.0)
    fig.text(0.06, 0.965, f"Number above each bar = {DIVISION} average score to par on that hole.",
             color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return save(fig, f"{PREFIX}_{DIVISION}_course_cards")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def division_row(division, row):
    if pd.isna(row["name"]):
        return f"| {division} | {row['players']} | {row['median_rating']:.0f} | no finisher | | |"
    rating = "" if pd.isna(row["median_rating"]) else f"{row['median_rating']:.0f}"
    if row["n_tied"] > 1:
        result = f"tied for 1st ({int(row['n_tied'])} players)"
    elif pd.isna(row["margin"]):
        result = "only finisher"
    else:
        result = f"by {int(row['margin'])}"
    return (f"| {division} | {row['players']} | {rating} | {row['name']} | {fmt_to_par(row['to_par'])} | {result} |")


def write_report(figures, cards):
    mpo = divisions.loc["MPO"] if "MPO" in divisions.index else None
    top_round = scored.loc[scored["round_rating"].idxmax()]
    big_fields = divisions[divisions["players"] >= 10].index.tolist()
    above = players.dropna(subset=["vs_rating"])
    share_above = (above["vs_rating"] > 0).mean()

    me = div_players[div_players["name"] == ME]
    me_line = ""
    if len(me):
        me_row = me.iloc[0]
        def round_place(rnd):
            scores = by_round[rnd]
            rank = int(scores.rank(method="min")[ME])
            tied = int((scores == scores[ME]).sum()) > 1
            return f"{'tied for ' if tied else ''}{ordinal(rank)}-best"
        harder = 1 if round_avg_to_par[1] > round_avg_to_par[2] else 2
        me_line = (f"- **{ME}** finished {'tied for ' if (place == place[ME]).sum() > 1 else ''}"
                   f"{ordinal(place[ME])} at {fmt_to_par(me_row['to_par'])} ({int(by_round.loc[ME, 1])}, "
                   f"{int(by_round.loc[ME, 2])}). Round 1 was {round_place(1)} in {DIVISION} and round 2 "
                   f"{round_place(2)}, of {len(by_round)}; round {harder} was on the harder course.")

    hardest = cards.sort_values("div_to_par", ascending=False).iloc[0]
    hardest_layout = div_layouts.set_index("round").loc[hardest["round"], "layout"]
    types = (div_holes.dropna(subset=["hole_type"]).drop_duplicates(["round", "hole"])["hole_type"]
             .value_counts().reindex(["short", "medium", "long"], fill_value=0))
    r1, r2 = div_layouts.iloc[0], div_layouts.iloc[1]

    lines = [
        f"# {event['name']}: event summary",
        "",
        f"PDGA event {EVENT_ID} · {event['start_date']} to {event['end_date']} · {event['location']} · "
        f"{event['tier']}-tier · {n_rounds} rounds",
        "",
        "## The event",
        "",
        f"- **{int(event['n_players'])} players in {int(event['n_divisions'])} divisions** played {n_rounds} rounds "
        f"across {len(courses)} courses ({', '.join(courses)}), on {int(event['n_layouts'])} layouts. "
        f"Divisions switched courses between rounds.",
        f"- **{int(event['n_rounds_usable'])} of {int(event['n_player_rounds'])} player-rounds** have complete hole "
        f"scores ({event['share_usable']:.0%}). The other {int(event['n_player_rounds'] - event['n_rounds_usable'])} "
        f"have no hole scores ({int(event['n_unfinished_999'])} were unfinished).",
    ]
    if mpo is not None:
        lines.append(f"- **MPO** ({int(mpo['players'])} players) was won by {mpo['name']} at "
                     f"{fmt_to_par(mpo['to_par'])}, by {int(mpo['margin'])} strokes, averaging a "
                     f"{mpo['avg_round_rating']:.0f} round rating.")
    lines += [
        f"- **Highest-rated round:** {top_round['player_name']} ({top_round['division']}), "
        f"{int(top_round['round_score'])} in round {int(top_round['round'])}, rated {top_round['round_rating']:.0f}.",
        f"- **{share_above:.0%} of players beat their rating** on average across their rounds (figure 1). "
        f"The {len(big_fields)} divisions with 10+ players were {', '.join(big_fields)}.",
        "",
        "### Every division",
        "",
        "| Division | Players | Median rating | Winner | Score | Won |",
        "|---|---|---|---|---|---|",
        *[division_row(d, row) for d, row in divisions.iterrows()],
        "",
        "Divisions are sorted by median event-time rating. Ties for first may have been settled by a playoff, "
        "which isn't in the data.",
        "",
        f"![Every division]({figures['all']})",
        "",
        f"## Focus: {DIVISION}",
        "",
        f"- **{len(div_players)} players** finished both rounds. {DIVISION} played {r1['layout']} "
        f"(par {r1['par']}) in round 1 with {r1['divisions'].replace(DIVISION + ', ', '').replace(', ' + DIVISION, '')}, "
        f"and {r2['layout']} (par {r2['par']}) in round 2 with "
        f"{r2['divisions'].replace(DIVISION + ', ', '').replace(', ' + DIVISION, '')}.",
        f"- **{winner} won by {int(standings.iloc[1] - standings.iloc[0])}** at "
        f"{fmt_to_par(div_players.iloc[0]['to_par'])} ({int(by_round.loc[winner, 1])}, "
        f"{int(by_round.loc[winner, 2])}). {standings.index[1]} was 2nd at "
        f"{fmt_to_par(div_players.iloc[1]['to_par'])} and {standings.index[2]} 3rd at "
        f"{fmt_to_par(div_players.iloc[2]['to_par'])}. Best single round: "
        f"{int(by_round.min().min())}, by {by_round.stack().idxmin()[0]} in round {by_round.stack().idxmin()[1]}.",
        f"- **Round 1 was much harder.** {DIVISION} averaged {fmt_to_par(round(round_avg_to_par[1]))} on "
        f"{r1['layout']} and {fmt_to_par(round(round_avg_to_par[2]))} on {r2['layout']}. The hardest hole was "
        f"{r1['layout'] if hardest['round'] == 1 else hardest_layout} hole {int(hardest['hole'])}, a "
        f"{hardest['length_ft']:.0f} ft par {int(hardest['par'])} that {DIVISION} played at "
        f"{hardest['div_to_par']:+.2f} on average.",
        f"- **Biggest turnaround:** {comeback} shot {int(by_round.loc[comeback, 1])} then "
        f"{int(by_round.loc[comeback, 2])}, {int(turnaround.iloc[0])} strokes better.",
    ]
    if me_line:
        lines.append(me_line)
    lines += [
        f"- **Hole types:** {DIVISION}'s 36 holes were {types['long']} long and {types['medium']} medium for their "
        f"par, and {'no' if types['short'] == 0 else types['short']} short.",
        "",
        f"![{DIVISION} strokes gained]({figures['race']})",
        "",
        f"![{DIVISION} style-adjusted strokes gained]({figures['heat']})",
        "",
        f"![{DIVISION} course cards]({figures['cards']})",
        "",
        "## Notes on the data",
        "",
        "- Strokes gained compares each score with everyone on the same layout in the same round, so "
        f"{DIVISION}'s round 1 and round 2 numbers are against different fields.",
        "- Round ratings and event-time ratings come from PDGA. Players without either are left out of figure 1.",
        "- The scraper marks an event final the day after it ends. " + ("This event was final when scraped."
            if event["is_final"] else "This event wasn't final yet when scraped, so re-scrape it to pick up any "
            "score corrections, then rerun `pdpp run`."),
    ]
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines) + "\n")
    print("saved report.md")


if __name__ == "__main__":
    cards = course_card_data()
    figures = {
        "all": plot_all_divisions(),
        "race": plot_strokes_gained_race(),
        "heat": plot_style_adjusted_heatmap(),
        "cards": plot_course_cards(cards),
    }
    write_report(figures, cards)
