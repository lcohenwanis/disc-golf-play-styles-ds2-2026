# Player Archetypes in Competitive Disc Golf

Final project for CSYS 6870 Data Science II, Fall 2026 (Luc Cohen-Wanis).

**Do competitive disc golfers fall into distinct playing styles beyond overall skill, and do those styles explain and predict how players score on different kinds of holes?**

The project uses hole-by-hole PDGA scores from Disc Golf Vermont Tour (DGVT) events, 2019-2026, to:

1. **Describe** play-style archetypes by clustering player profiles: strokes gained by hole type, the mix of birdies, pars and bogeys, and round-to-round consistency.
2. **Explain** how hole design favors each style, using a mixed-effects model with style x hole type interactions. Styles are assigned on 2020-2023 events and the model is fit on 2024-2026 events.
3. **Predict** each player's score category on each hole of held-out events, with and without style, to test whether styles carry real information.

## Status

As of October 5, 2026, data collection is done.

| Stage | Status |
|---|---|
| 1. Scrape: download raw PDGA pages, cached so nothing is downloaded twice | Done for every DGVT event that's been played, 2019-2026. The Oct 10-11 tour finals are still to come. |
| 2. Parse and clean into tidy tables, with checks | Done. Tables for each season are in `data/<year>/processed/`. Combining seasons and filtering to usable rounds is next. |
| 3. Build features: strokes gained, hole types, style profiles | Not started (week of Oct 19) |
| 4. Analyze in notebooks: clustering, regression, prediction | Not started |

What's been done so far:

- **Event list.** [`data/dgvt_events_2019_2026.csv`](data/dgvt_events_2019_2026.csv) lists 93 DGVT tour events with their PDGA event IDs. Two of them were cancelled (57231, 68349).
- **Scraper.** [`dgvt_styles/scrape.py`](dgvt_styles/scrape.py) calls the PDGA Live JSON API directly. It replaces an earlier Selenium scraper whose output had duplicate rows, skipped some divisions, and recorded ratings as of the scrape date instead of the event.
- **Data.** Every played event is scraped and parsed into one folder per season. Each round is checked: unfinished rounds (scored 999 but still marked completed) are flagged, and no round's hole scores disagree with its round total.
- **Proposal.** The proposal and its preliminary figure (Kingdom Open, August 2026) are in `Documents/`.

## Data at a glance

| | |
|---|---|
| Events with results | 90 (2019-2026) |
| Player-rounds | 25,254 |
| Usable player-rounds (every hole scored, hole scores add up to the round total) | 23,456 |
| Player x hole scores | 422,586 |
| Players | 2,202 |
| Layouts (event x tees) with usable rounds | 245 |

Caveats:

- 2019 has hole-by-hole scores for only 2 of 8 events. From 2020 on, nearly every event has them.
- Player ratings are from each event's results page, so they're the rating when the event was played. Some players were unrated at the time, and about 1,200 player-rounds are by players with no PDGA number.
- Divisions in the same round can play different tees, so par, hole length and any field average have to be computed per `layout_id`.

There's a summary for each season and a status row for every event in [`data/README.md`](data/README.md).

## Repository layout

```
dgvt_styles/                  Python package for the pipeline
  scrape.py                   stages 1-2: scrape PDGA Live and parse into tables
data/
  README.md                   scrape progress and data notes, by season and event
  dgvt_events_2019_2026.csv   every DGVT tour event with its PDGA event ID
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

`python -m dgvt_styles.scrape --help` lists every option. The scraper waits 1 second between requests.

## Data attribution

Event data © PDGA ([pdga.com](https://www.pdga.com)), used here for non-commercial course research.

## License

MIT. See [LICENSE](LICENSE).
