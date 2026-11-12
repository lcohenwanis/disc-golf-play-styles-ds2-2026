"""
Round 1 report: 2026 NADGC (PDGA 98248) MA3, round 1 on Williamson Wilco, and what to expect from round 2
on East Metro Shorts.

MA3 plays in two pools that swap courses. My pool (E) played Wilco in round 1 and plays East Metro in
round 2; the other pool did the reverse. Only MA3 plays these two layouts, so round 1 gives today's
conditions on both courses.

Input:  input/scouting/{rounds,hole_scores,holes}.csv      (linked from _import_; data/scouting/processed,
                                                            scraped after round 1)
        input/nadgc_hole_estimates.csv                     (report_nadgc_scouting: the pre-event per-hole
                                                            expectations at my rating, from 2025)
Output: output/nadgc_ma3_round1_report.md                  the report (links the figures below)
        output/nadgc_ma3_round1_strokes_gained.{png,pdf}   round 1, hole by hole, against expectations
        output/nadgc_ma3_round2_card.{png,pdf}             per-hole score chances on East Metro tomorrow
        output/nadgc_ma3_round2_score.{png,pdf}            simulated round 2 score
        output/nadgc_ma3_round1_holes.csv                  the per-hole round 1 numbers
        output/nadgc_ma3_round2_holes.csv                  the per-hole round 2 numbers

Round 1, per hole, compared three ways:
  pre-event   the 2025 model's expectation at my rating (report_nadgc_scouting)
  field today a linear model of round 1 score on rating, fit on the 2026 MA3 pool that played Wilco
              and evaluated at my rating. It answers "what would a 892 have shot today?"
  me          what I shot
Strokes gained vs pre-event = (pre-event - field today) + (field today - me), so conditions plus play.

Round 2: my round 1 updates my form for the week through the 2025 MA3 performance model (round rating =
rating + player-week effect + round noise), shrinking the round 1 surprise by the share of round-to-round
variance that's a lasting week effect. Per hole, the models are refit on 2025 MA3 East Metro scores plus
today's 2026 East Metro scores, with a day effect, and evaluated at today's conditions. Round 2's score
distribution uses today's East Metro rating-to-score line, shifted by a day-to-day change drawn from
2025's rounds.

Run from this task's src/ directory (pdpp does this).
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.miscmodels.ordinal_model import OrderedModel

INPUT_DIR = Path("../input")
OUTPUT_DIR = Path("../output")

PAST, EVENT, DIVISION = 87034, 98248, "MA3"
ME, ME_PDGA = "Luc Cohen-Wanis", 324228
PLAYED, NEXT_COURSE = "Williamson Wilco", "East Metro Shorts"
LAYOUTS_2026 = {"WilCo NADGC": "Williamson Wilco", "East Metro SHORTS NADGC": "East Metro Shorts"}
TODAY = "2026 R1"
N_SIMS = 20_000
RNG = np.random.default_rng(2026)

CATEGORIES = ["Birdie or better", "Par", "Bogey", "Double or worse"]
# Chart colors: same tokens as report_nadgc_scouting; diverging blue (good) <-> red (bad)
INK, INK_2, MUTED, GRID, SURFACE, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb", "#c3c2b7"
ACCENT = "#2a78d6"
GOOD, BAD = "#184f95", "#b93332"
CATEGORY_COLORS = ["#184f95", "#e4e3dd", "#f2a6a3", "#b93332"]
CATEGORY_TEXT = [SURFACE, INK, INK, SURFACE]

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


def fmt_to_par(x, digits=0):
    if round(x, digits) == 0:
        return "E"
    return f"{x:+.{digits}f}"


def fmt_sg(x, digits=1):
    """Strokes gained, with the sign spelled out (positive = better than expected)."""
    return f"{x:+.{digits}f}"


def article(n):
    """'a' or 'an' before a number, as it's said aloud (an 892, a 905)."""
    return "an" if str(int(n))[0] == "8" or str(int(n)).startswith(("11", "18")) else "a"


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def result_name(score_to_par):
    return {-3: "albatross", -2: "eagle", -1: "birdie", 0: "par", 1: "bogey", 2: "double"}.get(
        int(score_to_par), "triple+" if score_to_par > 2 else "ace")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
rounds = pd.read_csv(INPUT_DIR / "scouting" / "rounds.csv", dtype={"player_key": str})
hole_scores = pd.read_csv(INPUT_DIR / "scouting" / "hole_scores.csv", dtype={"player_key": str})
holes = pd.read_csv(INPUT_DIR / "scouting" / "holes.csv")
pre_event = pd.read_csv(INPUT_DIR / "nadgc_hole_estimates.csv")

# Round 1 layouts in 2025 are named "<layout> Rd1"; the 2026 layouts were renamed once the event started.
for df in (rounds, holes):
    df["course"] = df["layout_name"].str.removesuffix(" Rd1").replace(LAYOUTS_2026)
course_of_layout = holes.drop_duplicates("layout_id").set_index("layout_id")["course"]
hole_scores["course"] = hole_scores["layout_id"].map(course_of_layout)
for df in (rounds, hole_scores):
    df["day"] = np.where(df["event_id"] == EVENT, "2026 R", "2025 R") + df["round"].astype(str)

ma3 = rounds[(rounds["division"] == DIVISION) & rounds["usable"] & rounds["event_rating"].notna()]
past = ma3[ma3["event_id"] == PAST]
r1 = ma3[(ma3["event_id"] == EVENT) & (ma3["round"] == 1)].copy()
h_ma3 = hole_scores[(hole_scores["division"] == DIVISION) & hole_scores["round_usable"]
                    & hole_scores["event_rating"].notna()]
h_r1 = h_ma3[(h_ma3["event_id"] == EVENT) & (h_ma3["round"] == 1)]

me_r1 = r1[r1["pdga_number"] == ME_PDGA].iloc[0]
MY_RATING = int(me_r1["event_rating"])
A, A_CAP = article(MY_RATING), article(MY_RATING).capitalize()
assert me_r1["course"] == PLAYED, me_r1["course"]
my_holes = h_r1[h_r1["pdga_number"] == ME_PDGA].set_index("hole")["score_to_par"]
cards = (holes[(holes["event_id"] == EVENT) & holes["course"].isin([PLAYED, NEXT_COURSE])]
         [["course", "hole", "par", "length_ft"]].reset_index(drop=True))
PAR = cards.groupby("course")["par"].sum().astype(int).to_dict()


# ---------------------------------------------------------------------------
# Per-hole models
# ---------------------------------------------------------------------------
def category(score_to_par):
    return np.select([score_to_par <= -1, score_to_par == 0, score_to_par == 1], [0, 1, 2], 3)


def fit_holes(data, rating, at_days):
    """
    Per hole: expected score to par and the chance of each result for a player of `rating`, averaged over
    `at_days`. Linear model and ordered logit, each on rating (per 10 points) plus a day effect.
    """
    data = data.copy()
    data["r"] = (data["event_rating"] - rating) / 10
    data["cat"] = category(data["score_to_par"])
    at = pd.DataFrame({"r": 0.0, "day": at_days})
    rows = []
    for hole, d in data.groupby("hole"):
        multi_day = d["day"].nunique() > 1
        strokes = smf.ols("score_to_par ~ r" + (" + C(day)" if multi_day else ""), d).fit()
        exog = pd.get_dummies(d["day"], prefix="day", drop_first=True, dtype=float).assign(r=d["r"])
        ordered = OrderedModel(pd.Categorical(d["cat"], categories=[0, 1, 2, 3], ordered=True),
                               exog, distr="logit").fit(method="bfgs", disp=False, maxiter=500)
        exog_at = (pd.get_dummies(at["day"], prefix="day", dtype=float)
                   .reindex(columns=exog.columns, fill_value=0.0).assign(r=0.0))
        probs = np.asarray(ordered.predict(exog_at[exog.columns])).mean(axis=0)
        rows.append({"hole": hole, "n_scores": len(d), "expected": strokes.predict(at).mean(),
                     "se": float(strokes.get_prediction(at).se_mean.mean()),
                     **{f"p_{c.split()[0].lower()}": p for c, p in zip(CATEGORIES, probs)}})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Round 1 on Wilco
# ---------------------------------------------------------------------------
def round1_holes():
    today = fit_holes(h_r1[h_r1["course"] == PLAYED], MY_RATING, [TODAY])
    field_avg = h_r1[h_r1["course"] == PLAYED].groupby("hole")["score_to_par"].mean().rename("field_avg")
    pre = pre_event[pre_event["course"] == PLAYED].set_index("hole")
    out = (cards[cards["course"] == PLAYED].set_index("hole")[["par", "length_ft"]]
           .join(pre[["hole_type", "my_expected_to_par", "p_birdie", "p_bogey", "p_double"]]
                 .rename(columns=lambda c: f"pre_{c}" if c.startswith("p_") else c))
           .rename(columns={"my_expected_to_par": "pre_expected"})
           .join(field_avg)
           .join(today.set_index("hole").rename(columns=lambda c: f"today_{c}"))
           .join(my_holes.rename("me")))
    out["sg_pre"] = out["pre_expected"] - out["me"]           # vs the pre-event expectation
    out["sg_today"] = out["today_expected"] - out["me"]       # vs a player of my rating today
    out["conditions"] = out["pre_expected"] - out["today_expected"]  # + = played easier than expected
    return out.reset_index()


def leaderboard():
    """Round 1 standings by score to par, and by round rating (which puts the two courses on one scale)."""
    board = r1.assign(place=r1["round_to_par"].rank(method="min"),
                      rating_place=r1["round_rating"].rank(method="min", ascending=False))
    return board, board[board["pdga_number"] == ME_PDGA].iloc[0]


# ---------------------------------------------------------------------------
# Form update and round 2 on East Metro
# ---------------------------------------------------------------------------
def performance_model():
    """2025 MA3, as in report_nadgc_scouting: round rating = a + b * (rating - mine) + week + noise."""
    d = past[past["event_rating"] >= r1["event_rating"].min()].dropna(subset=["round_rating"]).copy()
    d["r"] = d["event_rating"] - MY_RATING
    fit = smf.mixedlm("round_rating ~ r", d, groups="player_key").fit()
    return {"a": fit.params["Intercept"], "b": fit.params["r"],
            "sd_player": float(np.sqrt(fit.cov_re.iloc[0, 0])), "sd_round": float(np.sqrt(fit.scale))}


def week_effects(model, ratings, r1_ratings):
    """Posterior mean and SD of each player's week effect after one round."""
    v_p, v_r = model["sd_player"] ** 2, model["sd_round"] ** 2
    shrink = v_p / (v_p + v_r)
    surprise = r1_ratings - (model["a"] + model["b"] * (ratings - MY_RATING))
    return shrink * surprise, np.sqrt(v_p * v_r / (v_p + v_r)), shrink


def score_lines():
    """
    PDGA's rating-to-score line (score = c0 + c1 * rating) per course and day: 2025 (MA2 on Wilco, MA3 on
    East Metro, whichever played it) and 2026 round 1.
    """
    lines = {}
    played_2025 = rounds[(rounds["event_id"] == PAST) & rounds["usable"]]
    for (course, day), g in pd.concat([played_2025, r1]).dropna(subset=["round_rating"]).groupby(["course", "day"]):
        if course in (PLAYED, NEXT_COURSE):
            lines[(course, day)] = tuple(np.polyfit(g["round_rating"], g["round_score"], 1)[::-1])
    return lines


def at_rating(line, rating):
    c0, c1 = line
    return c0 + c1 * rating


def day_shifts(lines):
    """
    How much each 2025 day differed from the 2025 average on each course, at my rating. Tomorrow's conditions
    are today's plus one of these (the same 2025 day on both courses, since 2025's hard day was hard on both).
    """
    days = sorted({d for (_, d) in lines if d.startswith("2025")})
    shift = {}
    for course in (PLAYED, NEXT_COURSE):
        ssa = np.array([at_rating(lines[(course, d)], MY_RATING) for d in days])
        shift[course] = ssa - ssa.mean()
    return shift


def round2_holes(effective_rating):
    data = h_ma3[h_ma3["course"] == NEXT_COURSE]
    data = data[(data["event_id"] == PAST) | (data["day"] == TODAY)]
    tomorrow = fit_holes(data, effective_rating, [TODAY])
    baseline = fit_holes(data, MY_RATING, [TODAY])  # today's conditions at my registration rating
    pre = pre_event[pre_event["course"] == NEXT_COURSE].set_index("hole")
    today_avg = h_r1[h_r1["course"] == NEXT_COURSE].groupby("hole")["score_to_par"].mean().rename("today_field_avg")
    out = (cards[cards["course"] == NEXT_COURSE].set_index("hole")[["par", "length_ft"]]
           .join(pre[["hole_type", "field_avg_to_par", "my_expected_to_par"]]
                 .rename(columns={"field_avg_to_par": "field_2025", "my_expected_to_par": "pre_expected"}))
           .join(today_avg)
           .join(baseline.set_index("hole")["expected"].rename("today_at_rating"))
           .join(tomorrow.set_index("hole")))
    out["change_vs_pre"] = out["expected"] - out["pre_expected"]
    out["rank"] = out["expected"].rank(ascending=False, method="first").astype(int)
    return out.reset_index()


def simulate_round2(model, lines, shifts, week_sd, expected):
    """
    Round 2 to par, centered on the per-hole models' `expected` total. Spread: my form (posterior SD), round
    noise, both turned into strokes with today's East Metro line, and a 2025-sized day-to-day change.
    """
    off_form = RNG.normal(0, week_sd, N_SIMS) + RNG.normal(0, model["sd_round"], N_SIMS)
    shift = RNG.choice(shifts[NEXT_COURSE], N_SIMS)
    return np.rint(expected + lines[(NEXT_COURSE, TODAY)][1] * off_form + shift)


def simulate_finish(model, lines, shifts):
    """
    Rounds 2-4 for every MA3 player, starting from their round 1 score. Pools swap courses each round, as
    MA3 did in 2025 (round 3 = round 1's course, round 4 = round 2's). Each player's form carries over from
    round 1 through the week-effect posterior; each round's conditions are today's plus a 2025 day shift.
    """
    ratings = r1["event_rating"].to_numpy(float)
    mean, sd, _ = week_effects(model, ratings, r1["round_rating"].to_numpy(float))
    first = r1["course"].to_numpy()
    other = np.where(first == PLAYED, NEXT_COURSE, PLAYED)
    me = int(np.flatnonzero(r1["pdga_number"].to_numpy() == ME_PDGA)[0])
    n = len(ratings)
    totals = np.tile(r1["round_score"].to_numpy(float), (N_SIMS, 1))
    week = mean + RNG.normal(0, sd, (N_SIMS, n))
    for course_now in (other, first, other):
        perf = model["a"] + model["b"] * (ratings - MY_RATING) + week + RNG.normal(0, model["sd_round"], (N_SIMS, n))
        day = RNG.integers(len(shifts[PLAYED]), size=N_SIMS)
        for course in (PLAYED, NEXT_COURSE):
            who = course_now == course
            strokes = at_rating(lines[(course, TODAY)], perf[:, who]) + shifts[course][day][:, None]
            totals[:, who] += np.rint(strokes)
    places = (totals < totals[:, [me]]).sum(axis=1) + 1
    par_total = 2 * (PAR[PLAYED] + PAR[NEXT_COURSE])
    return totals - par_total, places, me


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def plot_round1(r1h):
    fig, ax = plt.subplots(figsize=(11, 5.4))
    x = r1h["hole"].to_numpy()
    sg = r1h["sg_today"].to_numpy()
    ax.bar(x, sg, width=0.72, color=np.where(sg >= 0, GOOD, BAD), edgecolor=SURFACE, linewidth=2)
    ax.scatter(x, r1h["sg_pre"], s=46, marker="D", color=SURFACE, edgecolor=INK, linewidth=1.3, zorder=3,
               label="vs pre-event expectation (from 2025)")
    ax.axhline(0, color=INK_2, linewidth=0.9)
    for xi, (_, h) in zip(x, r1h.iterrows()):
        top = max(h["sg_today"], h["sg_pre"], 0)
        ax.text(xi, top + 0.06, f"{int(h['par'] + h['me'])}", ha="center", va="bottom", fontsize=9,
                color=INK, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(h['hole'])}\npar {int(h['par'])}" for _, h in r1h.iterrows()], fontsize=8)
    ax.set_xlim(0.4, 18.6)
    ax.set_ylabel("Strokes gained (+ = better than expected)")
    ax.grid(axis="x", visible=False)
    handles = ax.get_legend_handles_labels()[0] + [
        matplotlib.patches.Patch(color=GOOD, label=f"vs {A} {MY_RATING} in today's field: gained"),
        matplotlib.patches.Patch(color=BAD, label=f"vs {A} {MY_RATING} in today's field: lost")]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8.5, ncol=3, bbox_to_anchor=(0, -0.27))
    total_today, total_pre = r1h["sg_today"].sum(), r1h["sg_pre"].sum()
    ax.set_title(f"Round 1 on Williamson Wilco: {fmt_to_par(r1h['me'].sum())}, strokes gained by hole", pad=22)
    ax.text(0, 1.015, f"{fmt_sg(total_today)} strokes against {A} {MY_RATING}-rated player in today's MA3 field, "
                      f"{fmt_sg(total_pre)} against the pre-event expectation. Numbers above the bars are your scores.",
            transform=ax.transAxes, fontsize=9, color=INK_2)
    return save(fig, "nadgc_ma3_round1_strokes_gained")


def plot_round2_card(r2h, effective_rating):
    fig, ax = plt.subplots(figsize=(8.2, 7.6))
    d = r2h.sort_values("hole")
    y = np.arange(len(d))
    left = np.zeros(len(d))
    probs = d[[f"p_{c.split()[0].lower()}" for c in CATEGORIES]].to_numpy()
    for j, (cat, color, text) in enumerate(zip(CATEGORIES, CATEGORY_COLORS, CATEGORY_TEXT)):
        ax.barh(y, probs[:, j], left=left, height=0.72, color=color, edgecolor=SURFACE, linewidth=2, label=cat)
        for yi, (l, p) in enumerate(zip(left, probs[:, j])):
            if p >= 0.09:
                ax.text(l + p / 2, yi, f"{p:.0%}", ha="center", va="center", fontsize=7.5, color=text)
        left += probs[:, j]
    for yi, (_, h) in enumerate(d.iterrows()):
        ax.text(1.02, yi, fmt_to_par(h["expected"], 2), va="center", fontsize=9, color=INK,
                transform=ax.get_yaxis_transform())
        ax.text(1.14, yi, fmt_sg(h["change_vs_pre"], 2), va="center", fontsize=8.5, color=MUTED,
                transform=ax.get_yaxis_transform())
    ax.text(1.02, -1.1, "Expected", fontsize=8, color=MUTED, transform=ax.get_yaxis_transform())
    ax.text(1.14, -1.1, "vs pre-event", fontsize=8, color=MUTED, transform=ax.get_yaxis_transform())
    ax.set_yticks(y)
    ax.set_yticklabels([f"{int(h['hole'])}   par {int(h['par'])}, {int(h['length_ft'])} ft" for _, h in d.iterrows()],
                       fontsize=8.5)
    ax.set_ylim(len(d) - 0.5, -1.4)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.05), frameon=False, fontsize=8.5)
    ax.set_title(f"Round 2 on East Metro Shorts (par {PAR[NEXT_COURSE]}): {fmt_to_par(d['expected'].sum(), 1)} expected",
                 pad=22)
    ax.text(0, 1.012, f"Playing like a {effective_rating:.0f} (your round 1 form), in today's East Metro conditions.",
            transform=ax.transAxes, fontsize=9, color=INK_2)
    return save(fig, "nadgc_ma3_round2_card")


def plot_round2_score(scores, pre_expected):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    lo, hi = int(scores.min()), int(scores.max())
    values, counts = np.unique(scores, return_counts=True)
    ax.bar(values, counts / len(scores), width=0.8, color=ACCENT, edgecolor=SURFACE, linewidth=2)
    med = np.median(scores)
    top = (counts / len(scores)).max() * 1.22
    ax.set_ylim(0, top)
    ax.axvline(med, color=INK, linewidth=1.2)
    ax.text(med - 0.25, top * 0.95, f"median {fmt_to_par(med)}", ha="right", va="top", fontsize=9.5, color=INK)
    ax.axvline(pre_expected, color=MUTED, linewidth=1.0, linestyle=(0, (3, 3)))
    ax.text(pre_expected + 0.25, top * 0.95, f"pre-event {fmt_to_par(pre_expected, 1)}", ha="left", va="top",
            fontsize=9, color=INK_2)
    ax.set_xlim(max(lo, -10) - 1, min(hi, 16) + 1)
    ax.set_xticks(range(max(lo, -10), min(hi, 16) + 1, 2))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt_to_par(v)))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(f"Round 2 score to par on East Metro Shorts (par {PAR[NEXT_COURSE]})")
    ax.set_ylabel("Share of simulations")
    ax.grid(axis="x", visible=False)
    ax.set_title("Your round 2 score, simulated", pad=22)
    ax.text(0, 1.02, f"{N_SIMS:,} simulations: your form for the week, round-to-round noise, and a day-to-day "
                     f"change in conditions.", transform=ax.transAxes, fontsize=9, color=INK_2)
    return save(fig, "nadgc_ma3_round2_score")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def round1_table(r1h):
    lines = ["| Hole | Par | Feet | Type | You | Pre-event | Field today | SG vs pre-event | SG vs field today |",
             "|---|---|---|---|---|---|---|---|---|"]
    for _, h in r1h.iterrows():
        lines.append(f"| {int(h['hole'])} | {int(h['par'])} | {int(h['length_ft'])} | {h['hole_type']} | "
                     f"**{int(h['par'] + h['me'])}** ({result_name(h['me'])}) | {h['pre_expected']:+.2f} | "
                     f"{h['today_expected']:+.2f} | {h['sg_pre']:+.2f} | **{h['sg_today']:+.2f}** |")
    lines.append(f"| **Total** | {PAR[PLAYED]} | {int(r1h['length_ft'].sum()):,} | | **{int(PAR[PLAYED] + r1h['me'].sum())}** "
                 f"({fmt_to_par(r1h['me'].sum())}) | {r1h['pre_expected'].sum():+.1f} | {r1h['today_expected'].sum():+.1f} | "
                 f"{r1h['sg_pre'].sum():+.1f} | **{r1h['sg_today'].sum():+.1f}** |")
    return "\n".join(lines)


def breakdown_table(r1h):
    r1h = r1h.assign(group="par " + r1h["par"].astype(int).astype(str) + " " + r1h["hole_type"])
    rows = ["| Holes | Count | You | Field today | Strokes gained |", "|---|---|---|---|---|"]
    for g, d in r1h.groupby("group"):
        rows.append(f"| {g} ({', '.join(str(int(x)) for x in d['hole'])}) | {len(d)} | {d['me'].sum():+.0f} | "
                    f"{d['today_expected'].sum():+.1f} | **{d['sg_today'].sum():+.1f}** |")
    return "\n".join(rows)


def outcome_table(r1h):
    actual = {"Birdie or better": (r1h["me"] <= -1).sum(), "Par": (r1h["me"] == 0).sum(),
              "Bogey": (r1h["me"] == 1).sum(), "Double or worse": (r1h["me"] >= 2).sum()}
    keys = {"Birdie or better": "birdie", "Par": "par", "Bogey": "bogey", "Double or worse": "double"}
    rows = ["| Result | You | Expected today | Expected pre-event |", "|---|---|---|---|"]
    for cat, k in keys.items():
        today = r1h[f"today_p_{k}"].sum()
        pre = (1 - r1h[["pre_p_birdie", "pre_p_bogey", "pre_p_double"]].sum(axis=1)).sum() if k == "par" \
            else r1h[f"pre_p_{k}"].sum()
        rows.append(f"| {cat} | **{actual[cat]}** | {today:.1f} | {pre:.1f} |")
    return "\n".join(rows)


def round2_table(r2h):
    lines = ["| Hole | Par | Feet | Type | 2025 MA3 | Today's pool | You tomorrow | vs pre-event | Birdie+ | Bogey | Double+ | Rank |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, h in r2h.iterrows():
        lines.append(f"| {int(h['hole'])} | {int(h['par'])} | {int(h['length_ft'])} | {h['hole_type']} | "
                     f"{h['field_2025']:+.2f} | {h['today_field_avg']:+.2f} | **{h['expected']:+.2f}** | "
                     f"{h['change_vs_pre']:+.2f} | {h['p_birdie']:.0%} | {h['p_bogey']:.0%} | {h['p_double']:.0%} | "
                     f"{int(h['rank'])} |")
    lines.append(f"| **Total** | {PAR[NEXT_COURSE]} | {int(r2h['length_ft'].sum()):,} | | {r2h['field_2025'].sum():+.1f} | "
                 f"{r2h['today_field_avg'].sum():+.1f} | **{r2h['expected'].sum():+.1f}** | {r2h['change_vs_pre'].sum():+.1f} | "
                 f"{r2h['p_birdie'].sum():.1f} | {r2h['p_bogey'].sum():.1f} | {r2h['p_double'].sum():.1f} | |")
    return "\n".join(lines)


def list_holes(d, col, fmt):
    return ", ".join(f"{int(h['hole'])} ({fmt(h[col])})" for _, h in d.iterrows())


def write_report(r1h, board, me_row, model, lines, shifts, r2h, scores, finish):
    week_mean, week_sd, shrink = week_effects(model, np.array([MY_RATING]), np.array([me_row["round_rating"]]))
    week_mean = float(week_mean[0])
    effective = MY_RATING + week_mean
    expected_r1_rating = model["a"]
    per_stroke = -1 / lines[(PLAYED, TODAY)][1]

    figs = {"r1": plot_round1(r1h), "card": plot_round2_card(r2h, effective)}
    pre_r2 = pre_event.loc[pre_event["course"] == NEXT_COURSE, "my_expected_to_par"].sum()
    figs["score"] = plot_round2_score(scores, pre_r2)

    sg_today, sg_pre = r1h["sg_today"].sum(), r1h["sg_pre"].sum()
    conditions = r1h["conditions"].sum()
    gained = r1h.sort_values("sg_today", ascending=False).head(4)
    lost = r1h.sort_values("sg_today").head(4)
    lost = lost[lost["sg_today"] < 0]
    birdies = r1h[r1h["me"] <= -1]
    rare = birdies.sort_values("today_p_birdie").head(3)
    long4 = r1h[(r1h["par"] == 4) & (r1h["hole_type"] == "long")]

    pool = board[board["course"] == PLAYED]
    pool_place = int((pool["round_to_par"] < me_row["round_to_par"]).sum()) + 1
    pool_ties = int((pool["round_to_par"] == me_row["round_to_par"]).sum())
    leader = board.sort_values("round_to_par").iloc[0]
    top_ratings = int((board["round_rating"] > me_row["round_rating"]).sum())

    ssa_today = {c: at_rating(lines[(c, TODAY)], MY_RATING) - PAR[c] for c in (PLAYED, NEXT_COURSE)}
    em_line_effective = at_rating(lines[(NEXT_COURSE, TODAY)], model["a"] + week_mean) - PAR[NEXT_COURSE]
    em_line_baseline = at_rating(lines[(NEXT_COURSE, TODAY)], model["a"]) - PAR[NEXT_COURSE]
    em_2025 = [at_rating(lines[(NEXT_COURSE, d)], model["a"]) - PAR[NEXT_COURSE] for d in sorted(
        d for (c, d) in lines if c == NEXT_COURSE and d.startswith("2025"))]
    hole_total = r2h["expected"].sum()
    hole_baseline = r2h["today_at_rating"].sum()

    totals, places, me = finish
    my_total = totals[:, me]
    pct = lambda a, q: np.percentile(a, q)
    p = lambda k: (places <= k).mean()

    best = r2h.sort_values("p_birdie", ascending=False).head(3)
    danger = r2h.sort_values("p_double", ascending=False).head(3)
    hardest = r2h.sort_values("expected", ascending=False).head(3)
    moved = r2h.reindex(r2h["change_vs_pre"].abs().sort_values(ascending=False).index).head(4)

    report = f"""# NADGC 2026 MA3: round 1 review and round 2 preview

2026 NADGT North American Disc Golf Championships (PDGA {EVENT}) · Austin, Texas · for {ME} (MA3, rated {MY_RATING}, pool E)

Your pool played **Williamson Wilco** in round 1 and plays **East Metro Shorts** in round 2; the other pool did
the reverse. Only MA3 plays these two layouts, so today's MA3 scores show how both courses are playing.

## Bottom line

- **Round 1: {int(PAR[PLAYED] + r1h['me'].sum())} ({fmt_to_par(r1h['me'].sum())}) on Wilco, rated {int(me_row['round_rating'])}.** {A_CAP} {MY_RATING} was expected to shoot about {fmt_to_par(r1h['pre_expected'].sum(), 1)} before the event, and {A} {MY_RATING} in today's field projects to {fmt_to_par(r1h['today_expected'].sum(), 1)}. So you gained **{fmt_sg(sg_today)} strokes on today's field** and {fmt_sg(sg_pre)} on the pre-event expectation. Wilco played {abs(conditions):.1f} strokes {'easier' if conditions > 0 else 'harder'} than the 2025 model expected, so that difference comes down to conditions.
- **Standings:** tied {ordinal(me_row['place'])} of {len(board)} in MA3 and tied {ordinal(pool_place)} in your pool ({pool_ties} players at {fmt_to_par(me_row['round_to_par'])}), {int(me_row['round_to_par'] - leader['round_to_par'])} back of {leader['player_name']} ({fmt_to_par(leader['round_to_par'])} on East Metro). By round rating, which puts both courses on one scale, your {int(me_row['round_rating'])} is tied for the {ordinal(top_ratings + 1)}-best round in the division. Pre-event, your median finish was 55th.
- **Where you gained:** birdies. You made {len(birdies)} (holes {', '.join(str(int(h)) for h in birdies['hole'])}), where {A} {MY_RATING} averages {r1h['today_p_birdie'].sum():.1f}, and you made no doubles, where they average {r1h['today_p_double'].sum():.1f}. The biggest gains came on {list_holes(gained, 'sg_today', lambda v: f'{v:+.2f}')}.
- **Where you lost:** {list_holes(lost, 'sg_today', lambda v: f'{v:+.2f}')}.
- **Round 2 on East Metro:** expect about **{fmt_to_par(hole_total, 1)}** (80% of simulated rounds between {fmt_to_par(pct(scores, 10))} and {fmt_to_par(pct(scores, 90))}). That's {abs(hole_total - pre_r2):.1f} strokes {'better' if hole_total < pre_r2 else 'worse'} than the pre-event {fmt_to_par(pre_r2, 1)}, because East Metro played easier today and your round 1 nudges your form up. PDGA's ratings for today's East Metro scores point to {fmt_to_par(em_line_effective, 1)}, so the per-hole estimate is the more cautious one. Chance of breaking par: {(scores < 0).mean():.0%}; even or better: {(scores <= 0).mean():.0%}.
- **Updated finish:** median **{ordinal(np.median(places))}**, with 80% between {ordinal(pct(places, 10))} and {ordinal(pct(places, 90))}. Top 10: {p(10):.0%}; top 3: {p(3):.0%}; win: {p(1):.1%}. Projected 4-round total: {fmt_to_par(np.median(my_total))}.

## Round 1 on Williamson Wilco, hole by hole

![Round 1 strokes gained]({figs['r1']})

{round1_table(r1h)}

Three expectations, all for a player rated {MY_RATING}:

- **Pre-event** is the scouting report's per-hole model, fit on 2025 MA2 on Wilco.
- **Field today** is a per-hole model of today's scores on rating, fit on the {len(pool)} MA3 players who played Wilco today (median rating {pool['event_rating'].median():.0f}). It shows what {A} {MY_RATING} shot today on average.
- **Strokes gained (SG)** is expected minus your score, so a positive number is good. SG vs pre-event = conditions ({fmt_sg(conditions)}) + SG vs field today ({fmt_sg(sg_today)}).

### By hole type

{breakdown_table(r1h)}

### By result

{outcome_table(r1h)}

The round came from birdies, not from avoiding bogeys. You had {(r1h['me'] == 1).sum()} bogeys, about what {A} {MY_RATING} makes, but {len(birdies)} birdies, which is {len(birdies) - r1h['today_p_birdie'].sum():.1f} more than expected, and no doubles. The least likely were on {', '.join(str(int(h)) for h in rare['hole'])}, where {A} {MY_RATING} birdies {', '.join(f'{v:.0%}' for v in rare['today_p_birdie'])} of the time today. The par 3 bogeys on {' and '.join(str(int(h)) for h in r1h.loc[(r1h['me'] == 1) & (r1h['par'] == 3), 'hole'])} were the costliest holes. The long par 4s still came out ahead ({fmt_sg(long4['sg_today'].sum())}), but only because of the birdie on 5: you went {'-'.join(str(int(h['par'] + h['me'])) for _, h in long4.iterrows())} on holes {', '.join(str(int(h)) for h in long4['hole'])}.

**How much of this is form?** A {int(me_row['round_rating'])} round is {me_row['round_rating'] - expected_r1_rating:.0f} points above what the 2025 MA3 model expects from {A} {MY_RATING} ({expected_r1_rating:.0f}), about {(me_row['round_rating'] - expected_r1_rating) / per_stroke:.1f} strokes. In 2025, round-to-round noise (SD {model['sd_round']:.0f} points) was much bigger than week-long form (SD {model['sd_player']:.0f} points). So only {shrink:.0%} of a one-round surprise carries over: your expected form for the rest of the week rises by **{week_mean:+.0f} points**, to playing like a {effective:.0f}.

## Round 2 on East Metro Shorts

![Round 2 course card]({figs['card']})

{round2_table(r2h)}

- **Best birdie chances:** holes {list_holes(best, 'p_birdie', lambda v: f'{v:.0%}')}.
- **Blow-up risk (double or worse):** holes {list_holes(danger, 'p_double', lambda v: f'{v:.0%}')}.
- **Hardest for you:** holes {list_holes(hardest, 'expected', lambda v: f'{v:+.2f}')}.
- **Biggest changes from the pre-event report:** holes {list_holes(moved, 'change_vs_pre', lambda v: f'{v:+.2f}')}. Of the {fmt_sg(hole_total - pre_r2)} total change, {fmt_sg(hole_baseline - pre_r2)} is today's conditions at your registration rating, and {fmt_sg(hole_total - hole_baseline)} is your round 1 form, spread across every hole.

How the numbers are built:

- **Per hole:** each hole's models are refit on the 2025 MA3 East Metro scores ({int(r2h['n_scores'].iloc[0]) - len(board[board['course'] == NEXT_COURSE])} per hole) plus today's ({len(board[board['course'] == NEXT_COURSE])} per hole), with a separate effect for each day, and evaluated at today's conditions. At your registration rating that gives {fmt_to_par(hole_baseline, 1)}; at your updated form ({effective:.0f}) it gives {fmt_to_par(hole_total, 1)}.
- **From PDGA ratings:** today's East Metro rating-to-score line puts {A} {MY_RATING} at {fmt_to_par(ssa_today[NEXT_COURSE], 1)}. At the round rating the model now expects from you ({model['a'] + week_mean:.0f}), it gives {fmt_to_par(em_line_effective, 1)}, against {fmt_to_par(em_line_baseline, 1)} without the round 1 update. That's {hole_total - em_line_effective:.1f} strokes better than the per-hole models. Part of the gap is how each method handles today's lower-rated pool. The rating lines also give more for each rating point, so they make more of the form update. The simulation is centered on the per-hole estimate, which is the more cautious of the two.
- **Conditions:** today's pool on East Metro was the lower-rated half of MA3 (median {board.loc[board['course'] == NEXT_COURSE, 'event_rating'].median():.0f}). Through the rating lines, East Metro played about {abs(ssa_today[NEXT_COURSE] - np.mean(em_2025)):.1f} strokes {'easier' if ssa_today[NEXT_COURSE] < np.mean(em_2025) else 'harder'} than the 2025 average. 2025's four rounds put {article(model['a'])} {model['a']:.0f}-rated round between {fmt_to_par(min(em_2025), 1)} and {fmt_to_par(max(em_2025), 1)}, so tomorrow's weather can move this by a couple of strokes either way.

![Round 2 score]({figs['score']})

| Round 2 score | Chance |
|---|---|
| Under par | {(scores < 0).mean():.0%} |
| E or better | {(scores <= 0).mean():.0%} |
| +3 or better | {(scores <= 3).mean():.0%} |
| +6 or worse | {(scores >= 6).mean():.0%} |

## Updated finish

Each of {N_SIMS:,} simulations plays rounds 2-4 for all {len(board)} MA3 players, starting from their round 1 scores. Pools swap courses each round, as they did in 2025, so round 3 repeats round 1's course. Every player's form gets the same round 1 update as yours. Each round's conditions are today's, shifted by one of 2025's day-to-day changes.

| | Pre-event | After round 1 |
|---|---|---|
| Median finish | 55th | **{ordinal(np.median(places))}** |
| 80% range | 9th to 134th | {ordinal(pct(places, 10))} to {ordinal(pct(places, 90))} |
| Top 10 | 12% | {p(10):.0%} |
| Top 3 | 3% | {p(3):.0%} |
| Win | 1.2% | {p(1):.1%} |

## Caveats

- **Round ratings are unofficial.** PDGA Live ratings during an event are preliminary and can shift by a few points when they're finalized.
- **One round.** The field-today model uses {len(pool)} players on one day. A per-hole expectation is uncertain by about ±{r1h['today_se'].mean():.2f} strokes, or ±{np.sqrt((r1h['today_se'] ** 2).sum()):.1f} for the round if the errors were independent.
- **Form.** The {week_mean:+.0f}-point update assumes 2025's split between lasting form and round noise. A hot round is mostly noise.
- **Schedule.** Rounds 3 and 4 are assumed to repeat rounds 1 and 2's courses. If MA3 plays a different rotation, the finish numbers don't apply.
- **Weather.** Conditions tomorrow are today's plus a 2025-sized day-to-day change, nothing worse.
- Rerun after round 2 with `python -m dgvt_styles.scrape --events {EVENT} --data-dir data/scouting`, then `pdpp run`.
"""
    (OUTPUT_DIR / "nadgc_ma3_round1_report.md").write_text(report)
    print("saved nadgc_ma3_round1_report.md")


def main():
    r1h = round1_holes()
    r1h.to_csv(OUTPUT_DIR / "nadgc_ma3_round1_holes.csv", index=False, float_format="%.4f")
    board, me_row = leaderboard()
    model, lines = performance_model(), score_lines()
    shifts = day_shifts(lines)
    week_mean, week_sd, _ = week_effects(model, np.array([MY_RATING]), np.array([me_row["round_rating"]]))
    r2h = round2_holes(MY_RATING + float(week_mean[0]))
    r2h.to_csv(OUTPUT_DIR / "nadgc_ma3_round2_holes.csv", index=False, float_format="%.4f")
    scores = simulate_round2(model, lines, shifts, week_sd, r2h["expected"].sum())
    finish = simulate_finish(model, lines, shifts)
    write_report(r1h, board, me_row, model, lines, shifts, r2h, scores, finish)


if __name__ == "__main__":
    main()
