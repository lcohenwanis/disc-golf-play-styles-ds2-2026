# Player Archetypes in Competitive Disc Golf

Final project for CSYS 6870 Data Science II, Fall 2026 (Luc Cohen-Wanis).

**Do competitive disc golfers fall into distinct playing styles beyond overall skill, and do those styles explain and predict how players score on different kinds of holes?**

The project uses hole-by-hole PDGA scores from Disc Golf Vermont Tour (DGVT) events, 2020-2026, to:

1. **Describe** play-style archetypes by clustering player profiles: strokes gained by hole type, the mix of birdies, pars and bogeys, and round-to-round consistency.
2. **Explain** how hole design favors each style, using a mixed-effects model with style x hole type interactions. Styles are assigned on 2020-2023 events and the model is fit on 2024-2026 events.
3. **Predict** each player's score category on each hole of held-out events, with and without style, to test whether styles carry real information.

## Training window

The project collects and preserves DGVT data from 2019-2026, but all strokes-gained features, player profiles, and models train on 2020-2026 only. In 2019, just 2 of the 8 events have hole-by-hole scores, and one of those has only partial player-round coverage. Starting in 2020 provides a substantially more consistent hole-level dataset and avoids making 2019's sparse coverage part of the training distribution. The 2019 tables remain in the combined CSVs for auditability and historical reference, but `hole_features.csv` excludes them.

## Hole feature decision

Hole type and hole difficulty are treated as separate features. `hole_type` describes length as short, medium, or long within each par, using length terciles. `field_avg_to_par` measures how the hole played for the field: the average score-to-par for each event, round, layout, and hole. Length and field difficulty are related but not interchangeable (their overall correlation is about 0.44), so the analysis keeps both rather than collapsing them into one combined hole type.

## Player profile threshold

Player profiles use 2020-2023 usable, rated rounds. The minimum is 2 events, 4 usable rated rounds, and 72 usable holes (4 x 18) per player. Two events provide repeated observations beyond one tournament while retaining enough players for exploratory clustering. Of 1,055 rated players eligible before this threshold, 604 (57.3%) were retained and 451 were excluded. Retained players had a median of 171 usable holes, ranging from 72 to 1,710. Profiles retain each player's median event-time `event_rating` as a skill reference; the separate `*_vs_skill` features are residuals from the current `add_skill_adjusted` calculation using strokes gained per 18.

The clustering methodology is documented in `notebooks/clustering_analysis.ipynb`. It standardizes skill-adjusted player-profile features, starts with two clusters, and compares K-means with Gaussian mixture models using silhouette scores and GMM BIC. The two-cluster K-means and GMM solutions agree moderately (ARI 0.585). Using only the more reliable score-mix and consistency features improves the GMM silhouette from 0.158 to 0.238. A stricter 3-event threshold gives similar assignments on common players (ARI 0.893), while bootstrap agreement with the original GMM is moderate (mean ARI 0.572). The first two PCA dimensions explain 39.7% of variation.

The current conclusion is a preliminary steady-versus-volatile scoring distinction, not sharply separated archetypes. Cluster differences are strongly related to skill and variance, so the project will treat continuous style dimensions and cluster stability as important complements to any categorical archetype labels.

## Status

As of October 11, 2026, data collection is done for the whole 2019-2026 tour, including the October 10-11 tour finals (98262).

| Stage | Status |
|---|---|
| 1. Scrape: download raw PDGA pages, cached so nothing is downloaded twice | Done for every DGVT event, 2019-2026. The tour finals (98262) were scraped on October 11. |
| 2. Parse and clean into tidy tables, with checks | Done. Tables for each season are in `data/<year>/processed/`; the `combine_seasons` task in the PDPP pipeline (`dgvt_styles/`) combines them and flags training rows. |
| 3. Build features: strokes gained, length-based hole types, field difficulty, style profiles | In progress. Strokes gained, style-adjusted strokes gained, length-based hole types, and `field_avg_to_par` are built by the PDPP pipeline for 2020-2026; style profiles are prototyped in `notebooks/dgvt-eda.ipynb`. |
| 4. Analyze in notebooks: clustering, regression, prediction | In progress. Preliminary clustering and stability checks are in `notebooks/clustering_analysis.ipynb`; regression and prediction remain. |

What's been done so far:

- **Event list.** [`data/dgvt_events_2019_2026.csv`](data/dgvt_events_2019_2026.csv) lists 93 DGVT tour events with their PDGA event IDs. Two of them were cancelled (57231, 68349).
- **Scraper.** [`dgvt_styles/scrape.py`](dgvt_styles/scrape.py) calls the PDGA Live JSON API directly. It replaces an earlier Selenium scraper whose output had duplicate rows, skipped some divisions, and recorded ratings as of the scrape date instead of the event.
- **Data.** Every played event is scraped and parsed into one folder per season. Each round is checked: unfinished rounds (scored 999 but still marked completed) are flagged, and no round's hole scores disagree with its round total.
- **Proposal.** The proposal and its preliminary figure (Kingdom Open, August 2026) are in `Documents/`.

## Data at a glance

The first table describes the full collected dataset, including 2019 audit rows. The second describes the usable feature data that enters analysis after applying the 2020 start-year rule.

| | |
|---|---|
| Events with results | 91 (2019-2026, collected) |
| Player-rounds | 25,640 (combined audit tables) |
| Usable player-rounds (every hole scored, hole scores add up to the round total) | 23,838 (combined audit tables) |
| Player x hole scores | 429,462 (combined audit tables) |
| Players | 2,233 (combined audit tables) |
| Layouts (event x tees) with usable rounds | 253 (combined audit tables) |

| 2020+ analysis feature | Count |
|---|---:|
| Events represented in `hole_features.csv` | 82 |
| Usable player-rounds | 23,659 |
| Player x hole scores | 425,862 |
| Players | 2,108 |
| Layouts (event x tees) | 249 |

Caveats:

- 2019 has hole-by-hole scores for only 2 of 8 events, so it is retained for reference but excluded from training and feature generation. From 2020 on, nearly every event has hole-by-hole scores.
- Player ratings are from each event's results page, so they're the rating when the event was played. Some players were unrated at the time, and about 1,200 player-rounds are by players with no PDGA number.
- Divisions in the same round can play different tees, so par, hole length and any field average have to be computed per `layout_id`.

There's a summary for each season and a status row for every event in [`data/README.md`](data/README.md).

## Repository layout

```
dgvt_styles/                  Python package for the pipeline
  scrape.py                   stages 1-2: scrape PDGA Live and parse into tables
  features.py                 stage 3: strokes gained, field difficulty, style-adjusted SG, hole types, training flag
  dodo.py                     stage 3 as a PDPP workflow (run `pdpp run` from dgvt_styles/)
  _import_/                   symlinks to data/<year>/processed
  combine_seasons/            all seasons in one table each, with the training flag
  check_data_quality/         missing values and rating status
  build_hole_features/        hole x player x round features
  plot_case_study/            Cold Hollow Classic 2026 MA2 figures
  report_state_championship/  DGVT Finals 2026 (98262) event report
  report_nadgc_scouting/      NADGC 2026 (98248) MA3 scouting report, from the 2025 edition (87034)
  _export_/                   finished outputs (figures, tables)
data/
  README.md                   scrape progress and data notes, by season and event
  dgvt_events_2019_2026.csv   every DGVT tour event with its PDGA event ID
  scouting/                   non-DGVT events for scouting (NADGC 2025 and 2026), same tables
                              plus registrations.csv for events that haven't started
  <year>/
    processed/                tidy tables (tracked in git)
      events.csv              one row per event, with hole-score coverage
      holes.csv               one row per layout x hole: par, length
      rounds.csv              one row per player x round, with quality checks
      hole_scores.csv         one row per player x hole x round
    raw/                      cached PDGA responses (not in git, about 65 MB in all)
    scrape.log
Documents/                    proposal (LaTeX) and figures
requirements.txt
LICENSE
```

## The main tables

`hole_scores.csv` is the unit of analysis. Each row is one player on one hole in one round:

| Column | Meaning |
|---|---|
| `event_id`, `year`, `division`, `round` | Which event, season, division and round |
| `layout_id` | The tees this player played; use it to compare players on the same holes |
| `player_key` | PDGA number, or `name:<name>` for players without one |
| `event_rating` | PDGA rating at the time of the event (blank if unrated) |
| `hole`, `hole_label`, `par`, `length_ft` | The hole, from the player's layout |
| `score`, `score_to_par` | Strokes on the hole |
| `round_usable` | True when every hole in the round was scored and the scores add up to the round total |

`rounds.csv` has one row per player x round. It adds the player's name, course and layout names, round score and rating, and the quality checks behind `round_usable` (`unfinished_999`, `all_holes_scored`, `hole_sum_matches`). It also has `current_rating`, the player's rating today, which shouldn't be used as skill.

The combined CSV tables retain 2019 rows, unusable rounds, and their quality-check columns for auditability. The feature task is the analysis boundary: `hole_features.csv` contains only rows from 2020 onward where `round_usable` is `True`, so sparse-coverage 2019 events, unfinished `999` scores, and incomplete/mismatched hole totals cannot enter strokes-gained, style-profile, or clustering analyses. The original `hole_scores.csv` rows are still available for checking why a round was excluded.

## Setup and usage

Requires Python 3.10+.

```bash
pip install -r requirements.txt

# Scrape and parse events into a season's folder (cached pages aren't downloaded again)
python -m dgvt_styles.scrape --events 98262 --data-dir data/2026

# Rebuild a season's tables from its cached raw files, with no network
python -m dgvt_styles.scrape --parse-only --data-dir data/2026

# Find and scrape every DGVT event in a range of seasons
python -m dgvt_styles.scrape --years 2019-2026
```

Stage 3 is a [PDPP](https://github.com/UWNETLAB/pdpp) workflow. Each task folder has `input/`, `output/` and `src/`; its script runs from `src/`, reads only `../input/` and writes only `../output/`, and `.pdpp_task.yaml` says which upstream files are linked into `input/`. Tasks rerun only when their inputs or code change.

```bash
cd dgvt_styles
pdpp run      # combine_seasons -> check_data_quality, build_hole_features -> plot_case_study -> _export_
pdpp graph    # dependency diagrams (needs graphviz)
pdpp rig      # change a task's dependencies
```

PDPP 0.5 hard-links files into each task's `input/`, so the season files there are the same files as `data/<year>/processed`; don't edit them in place.

`python -m dgvt_styles.scrape --help` lists every option. The scraper waits 1 second between requests.

## Data attribution

Event data © PDGA ([pdga.com](https://www.pdga.com)), used here for non-commercial course research.

## License

MIT. See [LICENSE](LICENSE).
