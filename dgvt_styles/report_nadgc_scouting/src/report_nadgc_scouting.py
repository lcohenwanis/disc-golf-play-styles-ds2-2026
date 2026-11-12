"""
Scouting report: 2026 NADGT North American Disc Golf Championships (PDGA 98248), October 28-31, 2026,
MA3 on Williamson Wilco and East Metro Shorts, built from the 2025 edition (PDGA 87034).

In 2025, MA2 played Williamson Wilco and MA3 played East Metro Shorts, on the same par and length
on every hole as the 2026 layouts. So Wilco is scouted from 2025 MA2 and East Metro from 2025 MA3.

Input:  input/scouting/{rounds,hole_scores,holes,registrations}.csv   (linked from _import_, which
        points at data/scouting/processed; registrations are the 2026 sign-ups)
        input/hole_features.csv                                       (DGVT, from build_hole_features)
Output: output/nadgc_report.md                     the scouting report (links the figures below)
        output/nadgc_course_cards.{png,pdf}        per-hole score chances for a player of my rating
        output/nadgc_MA3_finish.{png,pdf}          simulated finishing place in 2026 MA3
        output/nadgc_hole_estimates.csv            the per-hole numbers behind the course cards

Per hole: an ordered logit (birdie or better / par / bogey / double or worse) and a linear model for
strokes, each on event-time rating plus round, fit on the 2025 division that played the course and
evaluated at my rating, averaged over the four 2025 rounds (so over 2025's conditions).

Overall: each 2026 MA3 player's round rating is drawn from a model fit on 2025 MA3 (rating + a
player effect for the week + round noise), then turned into strokes with one of the four 2025 PDGA
rating-to-score lines for that course, drawn once per course and round so everyone on a course
shares the conditions. Each simulated round uses one 2025 round's lines for both courses, since a
hard day in 2025 (round 1) was hard on both. Every MA3 player is assumed to play each course twice, in two pools that swap
courses, as MA3 did in 2025.

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

PAST, NEXT, DIVISION = 87034, 98248, "MA3"
ME, ME_PDGA = "Luc Cohen-Wanis", 324228
COURSES = {"Williamson Wilco": "MA2", "East Metro Shorts": "MA3"}  # course -> 2025 division that played it
ROUNDS_PER_COURSE = 2
N_SIMS = 10_000
RNG = np.random.default_rng(2026)

CATEGORIES = ["Birdie or better", "Par", "Bogey", "Double or worse"]
# Chart colors: same tokens as report_state_championship; diverging blue (good) <-> red (bad)
INK, INK_2, MUTED, GRID, SURFACE, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb", "#c3c2b7"
ACCENT = "#2a78d6"
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


def ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
rounds = pd.read_csv(INPUT_DIR / "scouting" / "rounds.csv", dtype={"player_key": str})
hole_scores = pd.read_csv(INPUT_DIR / "scouting" / "hole_scores.csv", dtype={"player_key": str})
holes = pd.read_csv(INPUT_DIR / "scouting" / "holes.csv")
registrations = pd.read_csv(INPUT_DIR / "scouting" / "registrations.csv")
features = pd.read_csv(INPUT_DIR / "hole_features.csv", dtype={"player_key": str},
                       usecols=["player_key", "par", "hole_type", "sg_style_adj", "round_usable"])

# Round 1 layouts are named "<layout> Rd1"; they're the same holes. PDGA renamed the 2026 layouts once
# the event started.
LAYOUTS_2026 = {"WilCo NADGC": "Williamson Wilco", "East Metro SHORTS NADGC": "East Metro Shorts"}
for df in (rounds, holes):
    df["course"] = df["layout_name"].str.removesuffix(" Rd1").replace(LAYOUTS_2026)
course_of_layout = holes.drop_duplicates("layout_id").set_index("layout_id")["course"]
hole_scores["course"] = hole_scores["layout_id"].map(course_of_layout)

past = rounds[(rounds["event_id"] == PAST) & rounds["usable"] & rounds["event_rating"].notna()].copy()
past_holes = hole_scores[(hole_scores["event_id"] == PAST) & hole_scores["round_usable"]
                         & hole_scores["event_rating"].notna()].copy()
cards = (holes[(holes["event_id"] == NEXT) & holes["course"].isin(COURSES)]
         [["course", "hole", "hole_label", "par", "length_ft"]].reset_index(drop=True))

field = registrations[(registrations["event_id"] == NEXT) & (registrations["division"] == DIVISION)].copy()
MY_RATING = int(field.loc[field["pdga_number"] == ME_PDGA, "rating"].iloc[0])
N_FIELD = len(field)
PAR_TOTAL = int(sum(cards.groupby("course")["par"].sum() * ROUNDS_PER_COURSE))


# ---------------------------------------------------------------------------
# Per-hole estimates at my rating
# ---------------------------------------------------------------------------
def category(score_to_par):
    return np.select([score_to_par <= -1, score_to_par == 0, score_to_par == 1], [0, 1, 2], 3)


def hole_estimates():
    rows = []
    for course, division in COURSES.items():
        data = past_holes[(past_holes["course"] == course) & (past_holes["division"] == division)].copy()
        data["r"] = (data["event_rating"] - MY_RATING) / 10  # per 10 rating points
        data["cat"] = category(data["score_to_par"])
        n_rounds = sorted(data["round"].unique())
        at_me = pd.DataFrame({"r": 0.0, "round": n_rounds})
        for hole, d in data.groupby("hole"):
            strokes = smf.ols("score_to_par ~ r + C(round)", d).fit()
            exog = pd.get_dummies(d["round"], prefix="rd", drop_first=True, dtype=float).assign(r=d["r"])
            ordered = OrderedModel(pd.Categorical(d["cat"], categories=[0, 1, 2, 3], ordered=True),
                                   exog, distr="logit").fit(method="bfgs", disp=False, maxiter=500)
            exog_me = pd.get_dummies(at_me["round"], prefix="rd", dtype=float).reindex(columns=exog.columns,
                                                                                         fill_value=0.0)
            exog_me["r"] = 0.0
            probs = np.asarray(ordered.predict(exog_me[exog.columns])).mean(axis=0)
            rows.append({
                "course": course, "hole": hole, "scouted_from": f"2025 {division}",
                "n_scores": len(d), "field_rating": d["event_rating"].median(),
                "field_avg_to_par": d["score_to_par"].mean(),
                "my_expected_to_par": strokes.predict(at_me).mean(),
                "strokes_per_10_points": -strokes.params["r"],
                **{f"p_{c.split()[0].lower()}": p for c, p in zip(CATEGORIES, probs)},
                "field_sd": d["score"].std(),
            })
    est = cards.merge(pd.DataFrame(rows), on=["course", "hole"])
    est["difficulty_rank"] = est.groupby("course")["my_expected_to_par"].rank(ascending=False, method="first").astype(int)
    est["hole_type"] = hole_type(est)
    return est


def hole_type(df):
    """DGVT hole type (short / medium / long for its par), from build_hole_features' cutoffs."""
    cutoffs = pd.read_csv(INPUT_DIR / "hole_type_cutoffs.csv")
    out = pd.Series(index=df.index, dtype=object)
    for _, c in cutoffs.iterrows():
        mask = (df["par"] == c["par"]) & (df["length_ft"] >= c["min_ft"] - 0.5) & (df["length_ft"] <= c["max_ft"] + 0.5)
        out[mask] = c["hole_type"]
    return out


# ---------------------------------------------------------------------------
# My play style on DGVT holes (style-adjusted strokes gained by hole type), shrunk toward 0
# ---------------------------------------------------------------------------
def style_profile():
    f = features[features["round_usable"] & features["hole_type"].notna() & features["sg_style_adj"].notna()].copy()
    f["type"] = "par " + f["par"].astype(int).clip(upper=5).astype(str) + " " + f["hole_type"]
    per_player = f.groupby(["player_key", "type"])["sg_style_adj"].agg(["mean", "var", "size"])
    per_player = per_player[per_player["size"] >= 30]
    mine = f[f["player_key"] == str(ME_PDGA)].groupby("type")["sg_style_adj"].agg(["mean", "var", "size"])
    rows = []
    for t, m in mine.iterrows():
        others = per_player.xs(t, level="type") if t in per_player.index.get_level_values("type") else None
        if others is None or len(others) < 20 or m["size"] < 2:
            rows.append({"type": t, "holes": int(m["size"]), "raw": m["mean"], "between_sd": np.nan, "shrunk": np.nan})
            continue
        tau2 = max(others["mean"].var() - (others["var"] / others["size"]).mean(), 0.0)
        k = tau2 / (tau2 + m["var"] / m["size"])
        rows.append({"type": t, "holes": int(m["size"]), "raw": m["mean"], "between_sd": np.sqrt(tau2),
                     "shrunk": k * m["mean"]})
    return pd.DataFrame(rows), f.loc[f["player_key"] == str(ME_PDGA)].shape[0]


# ---------------------------------------------------------------------------
# Simulate 2026 MA3
# ---------------------------------------------------------------------------
def performance_model():
    """
    2025 MA3: round rating = a + b * (event rating - mine) + player-week effect + round noise, fit on
    players inside the 2026 field's rating range (a few much lower-rated 2025 players far outplayed
    their ratings and flatten the slope).
    """
    d = past[(past["division"] == DIVISION) & (past["event_rating"] >= field["rating"].min())]
    d = d.dropna(subset=["round_rating"]).copy()
    d["r"] = d["event_rating"] - MY_RATING
    fit = smf.mixedlm("round_rating ~ r", d, groups="player_key").fit()
    return {"a": fit.params["Intercept"], "b": fit.params["r"],
            "sd_player": float(np.sqrt(fit.cov_re.iloc[0, 0])), "sd_round": float(np.sqrt(fit.scale)),
            "mean_vs_rating": (d["round_rating"] - d["event_rating"]).mean()}


def score_lines():
    """PDGA's rating-to-score line for each 2025 round on each course: score = c0 + c1 * rating."""
    lines = {}
    for course in COURSES:
        d = past[past["course"] == course].dropna(subset=["round_rating"])
        lines[course] = [tuple(np.polyfit(g["round_rating"], g["round_score"], 1)[::-1])
                         for _, g in d.groupby("round")]
    return lines


def simulate(model, lines):
    ratings = field["rating"].to_numpy(float)
    me = int(np.flatnonzero(field["pdga_number"].to_numpy() == ME_PDGA)[0])
    n, courses = len(ratings), list(COURSES)
    schedule = [courses[i % 2] for i in range(2 * ROUNDS_PER_COURSE)]  # pool A; pool B plays the other course
    totals = np.zeros((N_SIMS, n))
    my_by_course = {c: np.zeros(N_SIMS) for c in courses}
    for s in range(N_SIMS):
        pool_b = RNG.permutation(n) < n // 2
        week = RNG.normal(0, model["sd_player"], n)
        for rnd, course_a in enumerate(schedule):
            course_b = courses[1 - courses.index(course_a)]
            perf = model["a"] + model["b"] * (ratings - MY_RATING) + week + RNG.normal(0, model["sd_round"], n)
            day = RNG.integers(len(lines[course_a]))  # one 2025 day's conditions for both courses
            for course, who in ((course_a, ~pool_b), (course_b, pool_b)):
                c0, c1 = lines[course][day]
                strokes = np.rint(c0 + c1 * perf[who])
                totals[s, who] += strokes
                if who[me]:
                    my_by_course[course][s] += strokes[np.flatnonzero(who) == me][0]
    places = (totals < totals[:, [me]]).sum(axis=1) + 1
    return totals, places, me, my_by_course


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def plot_course_cards(est):
    fig, axes = plt.subplots(1, 2, figsize=(13, 7.6))
    for ax, (course, division) in zip(axes, COURSES.items()):
        d = est[est["course"] == course].sort_values("hole")
        y = np.arange(len(d))
        left = np.zeros(len(d))
        probs = d[[f"p_{c.split()[0].lower()}" for c in CATEGORIES]].to_numpy()
        for j, (cat, color, text) in enumerate(zip(CATEGORIES, CATEGORY_COLORS, CATEGORY_TEXT)):
            ax.barh(y, probs[:, j], left=left, height=0.72, color=color, edgecolor=SURFACE, linewidth=2,
                    label=cat)
            for yi, (l, p) in enumerate(zip(left, probs[:, j])):
                if p >= 0.09:
                    ax.text(l + p / 2, yi, f"{p:.0%}", ha="center", va="center", fontsize=7.5, color=text)
            left += probs[:, j]
        for yi, (_, h) in enumerate(d.iterrows()):
            ax.text(1.02, yi, fmt_to_par(h["my_expected_to_par"], 2), va="center", fontsize=9, color=INK,
                    transform=ax.get_yaxis_transform())
        ax.text(1.02, -1.1, "Expected", fontsize=8, color=MUTED, transform=ax.get_yaxis_transform())
        ax.set_yticks(y)
        ax.set_yticklabels([f"{int(h['hole'])}   par {int(h['par'])}, {int(h['length_ft'])} ft"
                            for _, h in d.iterrows()], fontsize=8.5)
        ax.set_ylim(len(d) - 0.5, -1.4)
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
        total = d["my_expected_to_par"].sum()
        ax.set_title(f"{course}  (par {int(d['par'].sum())}, {int(d['length_ft'].sum()):,} ft)", pad=22)
        ax.text(0, 1.012, f"Expected round: {fmt_to_par(total, 1)}. Scouted from 2025 {division} "
                          f"({d['n_scores'].iloc[0] // 1} scores per hole).",
                transform=ax.transAxes, fontsize=9, color=INK_2)
    axes[0].legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.06), frameon=False, fontsize=9)
    fig.suptitle(f"How a {MY_RATING}-rated player scores on each hole, NADGC 2026 MA3 courses",
                 x=0.06, ha="left", fontsize=13, fontweight="bold", y=1.0)
    fig.tight_layout(w_pad=6)
    return save(fig, "nadgc_course_cards")


def plot_finish(places, summary):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    bins = np.arange(0.5, places.max() + 1.5, 1)
    counts, _ = np.histogram(places, bins)
    ax.bar(bins[:-1] + 0.5, counts / len(places), width=1.0, color=ACCENT, edgecolor=SURFACE, linewidth=0.6)
    lo, med, hi = summary["p10"], summary["median"], summary["p90"]
    ax.axvspan(lo - 0.5, hi + 0.5, color=ACCENT, alpha=0.08, linewidth=0)
    ax.axvline(med, color=INK, linewidth=1.2)
    ax.annotate(f"median {ordinal(med)}", (med, ax.get_ylim()[1] * 0.93), xytext=(6, 0), textcoords="offset points",
                fontsize=9.5, color=INK)
    ax.text(hi + 1.5, ax.get_ylim()[1] * 0.78, f"80% of simulations:\n{ordinal(lo)} to {ordinal(hi)}",
            fontsize=9, color=INK_2)
    ax.set_xlim(0, min(places.max() + 2, N_FIELD))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    ax.set_xlabel(f"Finishing place of {N_FIELD} (ties share the better place)")
    ax.set_ylabel("Share of simulations")
    ax.set_title(f"Where a {MY_RATING}-rated player finishes in 2026 MA3", pad=22)
    ax.text(0, 1.015, f"{N_SIMS:,} simulated events against the {N_FIELD} registered MA3 players, "
                      f"2 rounds each on {' and '.join(COURSES)}.", transform=ax.transAxes, fontsize=9, color=INK_2)
    return save(fig, "nadgc_MA3_finish")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def hole_table(est, course):
    d = est[est["course"] == course].sort_values("hole")
    lines = ["| Hole | Par | Feet | Type | 2025 field | You (expected) | Birdie+ | Bogey | Double+ | Rank |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for _, h in d.iterrows():
        lines.append(f"| {int(h['hole'])} | {int(h['par'])} | {int(h['length_ft'])} | {h['hole_type'] or ''} | "
                     f"{h['field_avg_to_par']:+.2f} | **{h['my_expected_to_par']:+.2f}** | {h['p_birdie']:.0%} | "
                     f"{h['p_bogey']:.0%} | {h['p_double']:.0%} | {int(h['difficulty_rank'])} |")
    lines.append(f"| **Total** | {int(d['par'].sum())} | {int(d['length_ft'].sum()):,} | | "
                 f"{d['field_avg_to_par'].sum():+.1f} | **{d['my_expected_to_par'].sum():+.1f}** | "
                 f"{d['p_birdie'].sum():.1f} | {d['p_bogey'].sum():.1f} | {d['p_double'].sum():.1f} | |")
    return "\n".join(lines)


def notes_for(est, course):
    d = est[est["course"] == course]
    attack = d.sort_values("p_birdie", ascending=False).head(3)
    danger = d.sort_values("p_double", ascending=False).head(3)
    hardest = d.sort_values("my_expected_to_par", ascending=False).head(3)
    fmt = lambda rows, col: ", ".join(f"{int(h['hole'])} ({h[col]:.0%})" for _, h in rows.iterrows())
    out = [f"- **Best birdie chances:** holes {fmt(attack, 'p_birdie')}.",
           f"- **Blow-up risk (double bogey or worse):** holes {fmt(danger, 'p_double')}.",
           "- **Hardest for you:** holes " + ", ".join(
               f"{int(h['hole'])} ({h['my_expected_to_par']:+.2f})" for _, h in hardest.iterrows()) + "."]
    by_par = d.groupby("par")["my_expected_to_par"].agg(["sum", "size"])
    out.append("- **By par:** " + "; ".join(f"{int(n)} par {int(p)}s cost {s:+.1f}" for p, (s, n) in by_par.iterrows())
               + ".")
    return "\n".join(out)


def backtest_2025(places):
    """How players rated near mine actually finished in 2025 MA3, next to the simulation."""
    d = past[past["division"] == DIVISION]
    allr = rounds[(rounds["event_id"] == PAST) & (rounds["division"] == DIVISION)]
    totals = allr.groupby("player_key").agg(n=("round_score", "count"), total=("round_score", "sum"),
                                            rating=("event_rating", "first"))
    totals = totals[totals["n"] == 4]
    totals["place"] = totals["total"].rank(method="min")
    near = totals[(totals["rating"] - MY_RATING).abs() <= 7]
    return (f"In 2025, the {len(near)} MA3 players rated within 7 points of {MY_RATING} finished a median "
            f"{ordinal(near['place'].median())} of {len(totals)}, with 80% between {ordinal(near['place'].quantile(0.1))} "
            f"and {ordinal(near['place'].quantile(0.9))}, and {(near['place'] <= 10).mean():.0%} made the top 10. "
            f"The simulation gives {ordinal(np.median(places))}, {ordinal(np.percentile(places, 10))} to "
            f"{ordinal(np.percentile(places, 90))}, and {(places <= 10).mean():.0%}. Only {len(near)} players, on different courses with a different "
            f"field, so treat the comparison as rough.")


def write_report(est, model, lines, totals, places, me, my_by_course, style, n_style_holes):
    summary = {"median": int(np.median(places)), "p10": int(np.percentile(places, 10)),
               "p90": int(np.percentile(places, 90)), "mean": places.mean()}
    figs = {"cards": plot_course_cards(est), "finish": plot_finish(places, summary)}

    ranked = field.sort_values("rating", ascending=False).reset_index(drop=True)
    rating_rank = int((field["rating"] > MY_RATING).sum()) + 1
    my_total = totals[:, me] - PAR_TOTAL
    sorted_totals = np.sort(totals, axis=1) - PAR_TOTAL
    cut = lambda k: np.median(sorted_totals[:, k - 1])
    p = lambda k: (places <= k).mean()

    exp_course = {c: est.loc[est["course"] == c, "my_expected_to_par"].sum() for c in COURSES}
    par_course = {c: int(est.loc[est["course"] == c, "par"].sum()) for c in COURSES}
    sim_course = {c: my_by_course[c].mean() / ROUNDS_PER_COURSE - par_course[c] for c in COURSES}
    ssa_rounds = {c: [c0 + c1 * MY_RATING - par_course[c] for c0, c1 in lines[c]] for c in COURSES}

    p25 = past[past["division"].isin(["MA2", "MA3"])]
    by_player = (p25.groupby(["division", "player_key"])
                 .agg(name=("player_name", "first"), rounds=("round", "nunique"), to_par=("round_to_par", "sum")))
    by_player = by_player[by_player["rounds"] == 4].sort_values("to_par")
    winners = by_player.groupby("division").head(1)

    course_rows = []
    for course, division in COURSES.items():
        d = past[(past["course"] == course) & (past["division"] == division)]
        course_rows.append(f"| {course} | 2025 {division} | {d['player_key'].nunique()} | {d['event_rating'].median():.0f} | "
                           f"{d['round_to_par'].mean():+.1f} | {fmt_to_par(exp_course[course], 1)} | "
                           f"{fmt_to_par(sim_course[course], 1)} |")

    style_rows = "\n".join(
        f"| {r['type']} | {r['holes']} | {r['raw']:+.2f} | "
        + (f"{r['between_sd']:.2f} | {r['shrunk']:+.2f} |" if pd.notna(r["shrunk"]) else "too few | n/a |")
        for _, r in style.sort_values("type").iterrows())

    backtest = backtest_2025(places)
    report = f"""# NADGC 2026 scouting report: MA3 on Williamson Wilco and East Metro Shorts

2026 NADGT North American Disc Golf Championships (PDGA {NEXT}) · October 28-31, 2026 · Austin, Texas ·
built from the 2025 edition (PDGA {PAST})

For {ME}, registered in MA3 at **{MY_RATING}**.

## Bottom line

- **Expected scores:** about **{fmt_to_par(exp_course['Williamson Wilco'], 1)} per round on Wilco** (par {par_course['Williamson Wilco']}) and **{fmt_to_par(exp_course['East Metro Shorts'], 1)} on East Metro** (par {par_course['East Metro Shorts']}), so about **{fmt_to_par(ROUNDS_PER_COURSE * sum(exp_course.values()), 0)} for 4 rounds**, if conditions are like 2025's. The simulation gives a median of {fmt_to_par(np.median(my_total))}, with 80% of simulations between {fmt_to_par(np.percentile(my_total, 10))} and {fmt_to_par(np.percentile(my_total, 90))}.
- **Expected finish:** median **{ordinal(summary['median'])} of {N_FIELD}**, with 80% of simulations between {ordinal(summary['p10'])} and {ordinal(summary['p90'])}. Chance of a top 10: {p(10):.0%}; top 3: {p(3):.0%}; win: {p(1):.1%}.
- **You're rated {ordinal(rating_rank)} of {N_FIELD}** in MA3. The field's median is {field['rating'].median():.0f}, and the top rating is {ranked['rating'].iloc[0]:.0f}.
- **What it takes** (median across simulations): {fmt_to_par(cut(1))} to win, {fmt_to_par(cut(3))} for 3rd, {fmt_to_par(cut(10))} for 10th, and {fmt_to_par(cut(20))} for 20th.

## Where the numbers come from

2025 MA3 didn't play Wilco. In 2025, **MA2 played Wilco** (with Benbrook Ranch) and **MA3 played East Metro Shorts** (with North Town). Both 2026 layouts have the same par and length on every hole as in 2025. So Wilco is scouted from 2025 MA2 and East Metro from 2025 MA3. The per-hole models adjust each division's scores to your rating.

| Course | Scouted from | Players | Median rating | Their average round | You, from the hole models | You, from PDGA ratings |
|---|---|---|---|---|---|---|
{chr(10).join(course_rows)}

The two "you" columns are two separate estimates:

- **Hole models.** These add up the per-hole models below.
- **PDGA ratings.** This uses PDGA's 2025 rating-to-score line for each round (about {-1 / np.mean([c1 for c in COURSES for _, c1 in lines[c]]):.1f} rating points per stroke), at the round rating the 2025 MA3 model expects from a player rated {MY_RATING}.

The two estimates agree to within a stroke or so. 2025's round 1 was much harder on both courses. A round rated {MY_RATING} was {fmt_to_par(ssa_rounds['Williamson Wilco'][0], 1)} on Wilco in round 1 and {fmt_to_par(ssa_rounds['Williamson Wilco'][1], 1)} afterwards, and {fmt_to_par(ssa_rounds['East Metro Shorts'][0], 1)} vs {fmt_to_par(ssa_rounds['East Metro Shorts'][1], 1)} on East Metro. So a windy day could cost several strokes on its own.

For context, 2025 MA2 was won by {winners.loc['MA2', 'name'].iloc[0]} at {fmt_to_par(winners.loc['MA2', 'to_par'].iloc[0])} (Wilco and Benbrook), and MA3 by {winners.loc['MA3', 'name'].iloc[0]} at {fmt_to_par(winners.loc['MA3', 'to_par'].iloc[0])} (East Metro and North Town).

![Course cards]({figs['cards']})

## Williamson Wilco, hole by hole (scouted from 2025 MA2)

{hole_table(est, 'Williamson Wilco')}

{notes_for(est, 'Williamson Wilco')}

## East Metro Shorts, hole by hole (scouted from 2025 MA3)

{hole_table(est, 'East Metro Shorts')}

{notes_for(est, 'East Metro Shorts')}

How to read the tables:

- **2025 field** is that division's average score to par.
- **You (expected)** is the per-hole model's average for a player rated {MY_RATING}.
- **Birdie+, Bogey and Double+** are the chances of each result for you. Par is whatever is left.
- **Rank** is 1 for the hole that's hardest for you.
- **Type** uses the DGVT hole-type cutoffs (short, medium or long for the hole's par).

## Overall: MA3 placement

![Simulated finish]({figs['finish']})

Each simulation plays all {N_FIELD} registered MA3 players through 4 rounds, using their registration ratings:

- **Round ratings.** Each player's round rating comes from a model fit on 2025 MA3 players rated {field['rating'].min():.0f} or higher (the 2026 field's lowest rating): {model['a']:.0f} for a player rated {MY_RATING}, {model['b']:+.2f} points per rating point above or below that, a player-for-the-week effect (SD {model['sd_player']:.0f} points) and round-to-round noise (SD {model['sd_round']:.0f} points). Those players averaged {model['mean_vs_rating']:+.1f} points against their rating. The noise, not the ratings, is what makes the finish so uncertain: two players 10 points apart differ by about a stroke per round on average, while one player's 4-round total varies by about {np.std(totals[:, me]):.0f} strokes.
- **Strokes.** Round ratings are turned into strokes with one of the four 2025 rating-to-score lines for that course, One 2025 round's conditions are drawn per simulated round and used on both courses, since 2025's hard day was hard on both.
- **Pools.** Players are split into two pools that swap courses, as MA3 was in 2025.

**Check against 2025.** {backtest}

## Does your play style change the picture?

The project's style measure is style-adjusted strokes gained: strokes gained on a hole minus your average for that round, averaged by hole type. It comes from {n_style_holes} of your DGVT holes in 2026. Each estimate is shrunk toward 0 by how much DGVT players really differ on that hole type.

| Hole type | Your holes | Your average | Spread across DGVT players | Shrunk estimate |
|---|---|---|---|---|
{style_rows}

The spread across players is a few hundredths of a stroke per hole for most hole types, so your shrunk tilts are close to zero. **The per-hole estimates aren't adjusted for style.** The only sizable number is par 5s, from very few holes. Wilco has one par 5 (hole 9) and East Metro has none.

## Caveats

- **Wilco is scouted from MA2.** 2025 MA2 players were mostly rated 900-930, and the model adjusts down to {MY_RATING}. MA3 hasn't been seen on Wilco.
- **Conditions.** These are 2025's conditions, a single week. A windier or wetter week will shift every number here; the simulation includes 2025's spread between rounds, not anything worse.
- **Format.** The simulation assumes all MA3 players play each course twice. If MA3 pools play different courses in 2026, the placement numbers don't apply.
- **Ratings.** Registration ratings may be updated before the event, and the field may change. Rerun `python -m dgvt_styles.scrape --events {NEXT} --data-dir data/scouting`, then `pdpp run`.
- **No playoff.** Ties share a place.
"""
    (OUTPUT_DIR / "nadgc_report.md").write_text(report)
    print("saved nadgc_report.md")


def main():
    est = hole_estimates()
    est.to_csv(OUTPUT_DIR / "nadgc_hole_estimates.csv", index=False, float_format="%.4f")
    model, lines = performance_model(), score_lines()
    totals, places, me, my_by_course = simulate(model, lines)
    style, n_style_holes = style_profile()
    write_report(est, model, lines, totals, places, me, my_by_course, style, n_style_holes)


if __name__ == "__main__":
    main()
