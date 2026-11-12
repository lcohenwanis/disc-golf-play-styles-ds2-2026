---
title: "Player Archetypes in Competitive Disc Golf"
subtitle: "Halfway Check-In: CSYS 6870 Data Science II, Fall 2026"
author: "Luc Cohen-Wanis"
---

# 1. Introduction

Every competitive disc golfer has a PDGA rating: a single number that summarizes overall skill and decides which divisions a player can enter. A rating says nothing about *how* a player arrives at a score. One player might par nearly every hole, while another reaches the same total with a run of birdies offset by bogeys and the occasional triple. Players with the same total can also gain and lose strokes on very different kinds of holes. Figure 1 shows four MA2 players who all shot 128 at the 2026 Cold Hollow Classic. One gained over a stroke per round on the single long par 4 and gave it back on the long par 3s. Another gained on the medium par 4s and the par 5. A third was close to even everywhere.

The project asks:

> **Do competitive disc golfers fall into distinct playing styles beyond overall skill, and do those styles explain and predict how players score on different kinds of holes?**

The project has three parts. The *descriptive* part builds a style profile for each Disc Golf Vermont Tour (DGVT) player and tests whether the profiles cluster into archetypes. The *explanatory* part estimates whether the effect of hole type on strokes gained differs by style. The *predictive* part tests whether knowing a player's style improves hole-level score predictions beyond rating and hole difficulty. This check-in covers the first part. The data are collected and cleaned, the hole-level features are built and reproducible, and a first clustering is done and stress-tested. The clustering result is cautious: the data support a *steady-versus-volatile* scoring dimension more than sharply separated archetypes. That result changes how the second half of the project will be framed.

![**Figure 1.** Four MA2 players who all shot 128 over two rounds at the 2026 Cold Hollow Classic (DGVT #11, Long layout). Bars show each player's average style-adjusted strokes gained (defined in Section 3) on each par × length type. Same score, different routes there. The single-hole categories are noisy, which motivates pooling across many events below.](figures/cold_hollow_MA2_tied_128.png)

# 2. Data

## 2.1 Source and collection

The data are hole-by-hole scores from PDGA Live for every DGVT tour event from 2019 to 2026. I built the event list by hand: 93 events with their PDGA event IDs, two of which (2022 #11 and 2023 #9) were cancelled. The scraper (`dgvt_styles/scrape.py`) calls the PDGA Live JSON API directly and caches every raw response, so nothing is downloaded twice. It replaced an earlier Selenium scraper whose output had duplicate rows, skipped some divisions, and recorded each player's rating as of the scrape date instead of the event date. For example, only 1 of 91 players' stored ratings matched the event-time rating at one 2025 event. The current scraper takes ratings from each event's results page, so a player's rating is the one they held when they played. That matters because ratings are the skill reference throughout the project.

The raw JSON is parsed into four tidy tables per season (`events`, `holes`, `rounds`, `hole_scores`). A PDPP pipeline (`dgvt_styles/dodo.py`) then combines the seasons, runs data-quality checks, and builds the hole-level feature table. The unit of analysis is **one player on one hole in one round**.

## 2.2 Cleaning and quality checks

- **Usable rounds.** A round is usable only if every hole has a score and the hole scores add up to the recorded round total. Across all seasons, no scored round has hole scores that disagree with its total. Unfinished rounds are stored with a score of 999 but still flagged "completed" by PDGA, so the pipeline marks them unusable.
- **Layouts, not divisions.** Divisions in the same round often play different tees, so par, length, and every field average are computed per `layout_id`, never per division.
- **Unrated players.** About 9% of hole scores come from players with no event-time rating: 1,222 player-rounds by players with no PDGA number and 1,333 by players who had a number but were unrated at the time. These scores count toward field averages, since they are part of the field a player competed against, but they are excluded from profiles and models.
- **Missing hole lengths.** About 1.4% of hole scores, mostly from a few early courses, have no hole length. They have no length-based hole type but still contribute to everything else.

## 2.3 Coverage and the 2020 start

Table 1 summarizes coverage by season. In 2019 only 2 of 8 events have hole-by-hole scores, and one of those covers only about half its player-rounds. Including 2019 would make a sparse, unrepresentative season part of the training distribution. The 2019 rows are therefore kept in the combined tables for auditability, but every feature and model uses **2020–2026** only. From 2020 on, nearly every event has hole scores. The two exceptions are a 2020 event at 48% coverage and a 2021 event at 2%.

| Season | Events | With hole scores | Player-rounds | Usable rounds | Hole scores | Event-time rating |
|---|--:|--:|--:|--:|--:|--:|
| 2019 | 8 | 2 | 1,376 | 179 | 3,237 | 95% |
| 2020 | 9 | 9 | 1,616 | 1,503 | 27,126 | 84% |
| 2021 | 13 | 13 | 3,543 | 3,301 | 59,452 | 90% |
| 2022 | 15 | 14 | 4,029 | 3,990 | 71,834 | 95% |
| 2023 | 12 | 11 | 3,928 | 3,867 | 69,624 | 94% |
| 2024 | 12 | 12 | 3,881 | 3,839 | 69,206 | 96% |
| 2025 | 12 | 12 | 3,500 | 3,428 | 61,776 | 98% |
| 2026 | 12 | 12 | 3,767 | 3,731 | 67,207 | 98% |

: **Table 1.** DGVT coverage by season. "Event-time rating" is the share of players with a PDGA number who were rated when the event was played. The cancelled events have no rows.

The 2020–2026 analysis table contains **425,862 player × hole scores** from 23,659 usable player-rounds, 2,108 players, 82 events, and 249 layouts. It is split in time. Styles are defined on **2020–2023** (195,570 usable, rated hole scores), and **2024–2026** is held out for the explanatory and predictive analyses, so no style is ever evaluated on the scores that defined it.

# 3. Methods

## 3.1 Hole-level features

**Strokes gained.** For each hole score, strokes gained is the field's mean score on that hole minus the player's score. The field is everyone who played that hole on that layout in that round of that event, across divisions and including unrated players. The median field has 87 players. Positive values mean the player beat the field.

**Style-adjusted strokes gained.** This subtracts the player's own mean strokes gained for that round. It removes overall skill and that day's form, leaving only the *shape* of the round: where the player gained and lost relative to their own average. Each player-round's style-adjusted values sum to zero.

**Hole type and hole difficulty.** Hole type is a length tercile (short, medium, or long) *within par*. The cutoffs are computed over distinct layout × hole combinations, so that heavily used courses don't dominate. Par 3 cutoffs, for example, are 225 and 294 ft. Difficulty is measured separately as `field_avg_to_par`, the field's mean score to par on that hole in that round. The two are kept apart on purpose (Figure 2). Longer holes do play harder on average, but the overall correlation is only about 0.44, and 0.29 to 0.40 within each par. Two par 4s of similar length can play a full stroke apart.

![**Figure 2.** Hole length versus field difficulty for every layout hole, 2020–2026. Left: mean field score to par against length, by par. Right: difficulty by length tercile within par. Length shifts difficulty but leaves wide overlap, so hole type and difficulty are separate features.](figures/eda_length_vs_field_difficulty.png)

## 3.2 Player style profiles

Each player gets one profile from their 2020–2023 usable, rated scores. The profile has ten features in three groups:

1. **Strokes gained by hole type:** mean style-adjusted strokes gained on short, medium, and long holes, plus the par 3 minus par 4+ difference. Each mean is shrunk toward zero as if the player had 50 extra holes at zero, so players with few holes of one type don't produce extreme values.
2. **Score mix:** the share of holes scored birdie or better, par, bogey, and double bogey or worse.
3. **Consistency:** hole volatility (the SD of style-adjusted strokes gained) and round-to-round SD of strokes gained per 18.

**Minimum data.** Players need at least 2 events, 4 usable rated rounds, and 72 usable holes. Two events give repeated observations beyond a single tournament while keeping enough players to cluster. Of 1,055 eligible rated players, **604 (57%)** meet the threshold. Retained players have a median of 4 events, 10 rounds, and 171 holes, with a range of 72 to 1,710.

**Removing skill.** Raw profile features largely restate skill. Better players birdie more and blow up less, so raw birdie rate correlates 0.80 with strokes gained per 18. Each feature is therefore regressed on strokes gained per 18 with a quadratic fit, and the residual becomes the style feature. A positive `pct_birdie_or_better_vs_skill`, for example, means more birdies than players of the same performance level. The residual features are standardized before clustering.

**Reliability.** A style should describe the *player*, not one weekend. To check, I split each player's events into two alternating halves, so that both halves span the same seasons. I rebuilt the profile on each half and computed the Spearman correlation between halves, projected to full length with Spearman–Brown (Figure 3). Skill adjustment removes most of the skill correlation, as intended, but it also lowers reliability. After adjustment, the most stable features are hole volatility (0.47), par rate (0.36), and birdie rate (0.32). Strokes gained by hole type is barely reliable at all. After adjustment, the short, medium, and long features have no measurable split-half reliability, and the par 3 minus par 4+ difference reaches only 0.13. This was the first sign that hole-type preferences, the most intuitive notion of "style", are the weakest signal in the data.

![**Figure 3.** Reliability of each profile feature (split-half, Spearman–Brown) against its correlation with skill (|ρ| with strokes gained per 18). Hollow points are raw features, filled points are skill-adjusted, and lines connect each pair. Good style features sit top-left. Score-mix and consistency features keep moderate reliability after adjustment, while strokes gained by hole type does not.](figures/eda_feature_reliability.png)

## 3.3 Clustering and validation

I compared K-means (50 initializations) and Gaussian mixture models (GMM; full covariance, 10 initializations) on the ten standardized style features. K-means and GMM were compared with silhouette scores, and the GMMs also with BIC. Since a style label is only useful if it is robust, I then ran five checks on the two-cluster solution:

1. agreement between the K-means and GMM partitions (adjusted Rand index, ARI);
2. re-clustering on only the more reliable score-mix and consistency features;
3. a stricter threshold of 3 events, 6 rounds, and 108 holes;
4. 50 bootstrap resamples of players, each refit and then used to relabel the original players;
5. a PCA projection, to see whether the structure looks like groups or a continuum.

Throughout, raw rating and strokes gained per 18 were *not* clustering inputs. They are used afterwards to test whether the clusters just recover skill.

# 4. Results so far

## 4.1 Choosing the number of clusters

Table 2 shows the sweep over 2 to 8 clusters. BIC is lowest at three components, but silhouette scores are low everywhere (≤ 0.165) and fall quickly for GMMs beyond three. The first pass used the BIC-best three-cluster GMM. Its smallest cluster held 56 players with a median rating of 821, and it was mostly separated by round-to-round variance: the lowest-rated, most erratic players. That looked like a skill tier, not a style. I therefore moved to two clusters as the more conservative test. If two groups don't separate cleanly, more groups are unlikely to be real archetypes.

| k | K-means silhouette | GMM silhouette | GMM BIC |
|--:|--:|--:|--:|
| 2 | **0.165** | **0.158** | 8,878 |
| 3 | 0.122 | 0.145 | **8,754** |
| 4 | 0.120 | 0.104 | 8,986 |
| 5 | 0.125 | 0.033 | 9,135 |
| 6 | 0.122 | −0.010 | 9,376 |
| 8 | 0.117 | 0.015 | 9,880 |

: **Table 2.** Model sweep on the ten skill-adjusted features, 604 players (k = 7 omitted; it follows the same trend). Silhouette above about 0.5 would indicate well-separated clusters. Every value here is far below that.

## 4.2 The two-cluster solution: steady versus volatile

The two-cluster GMM splits the 604 players into 194 (cluster 0) and 410 (cluster 1). Figure 4 shows what separates them. Cluster 0 makes fewer pars (−0.7 SD) and birdies (−0.4 SD) than players of similar performance, and more bogeys (+0.6 SD) and doubles or worse (+0.9 SD). Its holes are more volatile (+0.7 SD). Cluster 1 is the mirror image, at smaller magnitude because it is larger. The hole-type columns are close to zero for both clusters. The split is about *how evenly* players score, not *where* they score well.

![**Figure 4.** Standardized mean of each skill-adjusted profile feature by two-cluster GMM. Cluster 0 (n = 194) is volatile: more bogeys and big numbers and fewer pars than skill predicts. Cluster 1 (n = 410) is steady. Strokes gained by hole type barely differs.](figures/clustering_profile_centroids.png)

The clusters are **not independent of skill** (Figure 5). The volatile cluster has a *higher* median event-time rating (915 vs. 888) but *lower* median strokes gained per 18 (0.66 vs. 0.89). Its round-to-round SD (4.49 vs. 4.00) and hole volatility (0.82 vs. 0.73) are both higher. At a given rating, volatile players tend to gain fewer strokes on the field than steady players. Their rating overstates their typical round, which fits a high-variance scorer whose rating is held up by good rounds. Part of this gap may also be a field-strength effect: higher-rated players often share layouts with stronger divisions, and strokes gained is relative to whoever else played that layout. Either way, the split can't be presented as a purely stylistic category.

![**Figure 5.** Left: median event-time rating by cluster. Right: strokes gained per 18 against rating, colored by cluster. The clusters overlap across the whole rating range. At a given rating, volatile (cluster 0) players tend to sit below steady (cluster 1) players.](figures/clustering_rating_comparison.png)

## 4.3 Robustness

Table 3 summarizes the stability checks. The split survives a change of algorithm and threshold *moderately to well*. It is noticeably cleaner when clustering only on the reliable score-mix and consistency features, where silhouette rises from 0.158 to 0.238. The bootstrap is the weakest result. Mean agreement with the original partition is only 0.57, and at least one resample produced an essentially unrelated partition (ARI −0.01). The first two principal components explain only 39.7% of variance (22.9% and 16.8%). In that projection the two clusters are two sides of one cloud, divided mainly along PC1, not two separate groups (Figure 6).

| Check | Result |
|---|---|
| K-means vs. GMM (same features) | ARI 0.585 |
| Reliable features only (6 score-mix and consistency features) | GMM silhouette 0.238 (vs. 0.158); ARI 0.625 with all-feature GMM |
| Stricter threshold: 3 events, 6 rounds, 108 holes (432 players) | ARI 0.893 on common players |
| Bootstrap, 50 resamples | mean ARI 0.572, median 0.623, min −0.012 |
| PCA, first two components | 39.7% of variance |

: **Table 3.** Stability of the two-cluster solution.

![**Figure 6.** Skill-adjusted profiles projected onto the first two principal components (39.7% of variance), colored by GMM cluster. The clusters split one continuous cloud, mostly along PC1, so a continuous dimension describes the structure better than two groups.](figures/clustering_pca.png)

**Summary of results.** Players do differ, beyond skill, in how evenly they score. That difference is moderately reliable within players and gives a reproducible two-way split. But the split is a cut through a continuum, it is entangled with the gap between rating and performance, and it says little about hole-type preferences. The current evidence supports a **steady-versus-volatile style dimension**, not discrete, named archetypes.

# 5. Discussion

## 5.1 How the project has gone

The engineering half of the project went better than planned. The proposal assumed that older events might lack hole-level data and that I might have to fall back to round-level features. In the end every DGVT event from 2019 to 2026 was scraped and checked, and 2020–2026 has nearly complete hole-level coverage. Rewriting the scraper against the JSON API was the most important decision of the first half. The original scraper's ratings were wrong in a way that would have quietly corrupted every skill adjustment, and catching that early was worth the extra week. The PDPP pipeline means the feature table can be rebuilt from raw JSON with one command, which made it cheap to change definitions later. Hole types were redefined as length terciles once it was clear that length and difficulty disagree.

The analysis half produced a less tidy answer than I hoped. The proposal's framing was about naming archetypes, like the 13 NBA positions in [2]. The data so far don't support that. Two lessons came out of it. First, **reliability should come before clustering**. The split-half check showed that the features most people would call "style", such as being better on long holes or on par 3s, are close to noise at this sample size: most players have under 200 holes in the profile window. Second, **removing skill is not a one-step fix**. Even after residualizing on strokes gained per 18, cluster membership tracks the gap between rating and performance.

None of this is a failure of the project. The proposal's contingency plan anticipated both outcomes ("the clusters just recover skill" and "there aren't distinct groups") and named continuous style dimensions as the fallback. That fallback is now the main path, and the minimum viable project is still in reach. The player × hole table, strokes gained, style profiles, and a validated clustering are done. The style × hole type estimate and the prediction comparison remain.

## 5.2 Limitations and risks

- **Selection.** Players choose which events, and therefore which courses, to enter. A profile partly reflects course mix and division. Player effects in the explanatory model will absorb some of this, and all estimates apply only to players who showed up.
- **Field strength.** Strokes gained is relative to the layout's field, so it is not perfectly comparable across layouts with stronger or weaker fields. This likely contributes to the rating-versus-performance pattern in Figure 5.
- **Sample size.** The 2-event threshold keeps 57% of eligible players, but many are near the minimum, so their profiles are noisy. The stricter threshold agrees well (ARI 0.89), but it can't fix low reliability for hole-type features.
- **Skill entanglement.** Rating and strokes gained per 18 are strongly related. Residualizing on one leaves structure related to the other.
- **Label instability.** Given the low silhouette and moderate bootstrap agreement, cluster labels shouldn't be treated as fixed player identities.

## 5.3 Plan for the rest of the semester

The plan keeps the proposal's structure and timeline. The main change is that style enters the later models primarily as a **continuous volatility score**, with the two-cluster label as a secondary, interpretable version.

| Week of | Work | Deliverable |
|---|---|---|
| Nov 2 | Finish stability checks: season-to-season (2020–21 vs. 2022–23) agreement; define the continuous style score (PC1 or a volatility index) and compare it with the cluster label; adjust strokes gained for field strength | Final style dimensions |
| Nov 9 | Mixed-effects model on held-out 2024–2026 scores: strokes gained ~ hole type × style + difficulty, with player and layout-round-hole random effects | Explanatory results |
| Nov 16 | Predict score category (birdie or better, par, bogey, double or worse) on held-out events with rating + difficulty, then with style added; compare log loss and calibration | Predictive results |
| Nov 23 | Buffer (Thanksgiving); README, license, documentation; stretch goal: does a bad hole carry over to the next? | Clean repository |
| Nov 30 | Write the final report | Report draft |
| Dec 7 | Revise and present | **Report (Dec 8), presentation (Dec 9)** |

Two of these steps follow directly from the results here. First, the explanatory model will test the volatility dimension against field difficulty as well as hole length. A steady player's advantage plausibly appears on holes where the field often makes big numbers, not on long holes as such. Second, the predictive comparison is the real test of whether style exists. If adding the volatility score improves held-out predictions of *double bogey or worse*, the category where the clusters differ most, then style is a real, transferable property of a player. If it doesn't, the final report will say so: the profile differences would then be descriptive variation, not stable style.

**References.**
[1] M. Broadie. Assessing golfer performance on the PGA TOUR. *Interfaces*, 42(2):146–165, 2012.
[2] M. Alagappan. From 5 to 13: Redefining the positions in basketball. *MIT Sloan Sports Analytics Conference*, 2012.

*Code and data:* the `dgvt_styles/` pipeline, plus `notebooks/dgvt-eda.ipynb` (features, profiles, reliability) and `notebooks/clustering_analysis.ipynb` (clustering and validation). All figures in this report are produced by these notebooks.
