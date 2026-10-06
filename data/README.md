# DGVT events, 2019-2026

`dgvt_events_2019_2026.csv` lists 93 Disc Golf Vermont Tour events from 2019 to 2026, with the PDGA event ID, name, dates, tier, city and PDGA link for each. The 2021 to 2026 seasons look complete; 2019 and 2020 have gaps that still need to be filled.

| Season | Events | PDGA event IDs | Gaps |
|---|---|---|---|
| 2019 | 8 | 40642, 40643, 41154, 41155, 41384, 41156, 41157, 41158 | Stops #3 and #8 not found |
| 2020 | 9 | 45898, 46036, 46247, 46474, 46697, 46877, 47319, 47320, 47321 | Stop #1 not found (no PDGA live data) |
| 2021 | 13 | 49941-49945, 49951-49958 | None |
| 2022 | 15 | 57217, 57218, 57219, 57221, 55101, 57225, 57226, 57228, 57229, 57230, 62737, 57231, 57232, 57233, 57234 | None |
| 2023 | 12 | 67158, 67159, 67160, 67161, 67514, 67713, 67796, 68282, 68349, 68642, 68786, 68805 | None |
| 2024 | 12 | 77672, 77674, 77909, 77695, 76286, 78661, 78807, 78862, 78961, 79122, 79898, 79942 | None |
| 2025 | 12 | 87899, 87900, 88027, 88189, 86523, 88944, 90019, 90283, 90932, 91169, 91399, 91411 | None |
| 2026 | 12 | 98155, 98157, 98161, 98162, 98220, 97998, 98242, 98252, 98424, 98313, 98254, 98262 | None (98262 is the tour finals, October 10-11) |

## Scrape progress

Last scraped October 5, 2026, with `python -m dgvt_styles.scrape` (formerly `scrape-pdga-live.py`). All 93 events in the CSV were scraped except the 2026 Vermont State Championship (98262), which hasn't been played yet. Each season has its own folder:

```
data/<year>/
  raw/live/<event_id>/   PDGA Live JSON (event.json, <division>_r<round>.json) and the results page
  processed/             events.csv, holes.csv, rounds.csv, hole_scores.csv
  scrape.log
```

To re-run a season, pass that season's event IDs from the CSV with `--data-dir data/<year>`. Cached pages aren't downloaded again.

| Season | Events | With hole scores | Player-rounds | Usable rounds | Hole scores | Event-time rating |
|---|---|---|---|---|---|---|
| 2026 | 11 | 11 | 3,381 | 3,349 | 60,331 | 98% |
| 2025 | 12 | 12 | 3,500 | 3,428 | 61,776 | 98% |
| 2024 | 12 | 12 | 3,881 | 3,839 | 69,206 | 96% |
| 2023 | 12 | 11 | 3,928 | 3,867 | 69,624 | 94% |
| 2022 | 15 | 14 | 4,029 | 3,990 | 71,834 | 95% |
| 2021 | 13 | 13 | 3,543 | 3,301 | 59,452 | 90% |
| 2020 | 9 | 9 | 1,616 | 1,503 | 27,126 | 84% |
| 2019 | 8 | 2 | 1,376 | 179 | 3,237 | 95% |

- **Usable rounds** have every hole scored, and the hole scores add up to the round score. Across all seasons, no scored round has hole scores that disagree with its round total. Unfinished rounds (round score 999, still marked completed) are counted as unusable.
- **Event-time rating** is the share of players with a PDGA number who have a rating from the event's results page, which shows their rating when the event was played. The rest were unrated at the time. The live API's current rating is kept separately as `current_rating` and shouldn't be used as skill.
- **2019 has almost no hole-by-hole data.** Only stops #9 and the Finals have hole scores, and #9 only for about half its player-rounds. From 2020 on, almost every event has them. The exceptions are 49954 (2021 North Calais Open, 4 of 214 player-rounds) and 46877 (2020 Wrightsville Beach Open, 88 of 184).
- **Two events were cancelled:** 57231 (2022 #11 Vista Beast Challenge) and 68349 (2023 #9 Magic Mountain Open). They're listed on PDGA but have no players or results.

### 2026

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 98155 | DGVTour #1 - South Shire Shootout | 310 | 305 (98%) | Yes |  |
| 2 | 98157 | DGVTour #2 - Battle of Pittsford | 180 | 179 (99%) | Yes |  |
| 3 | 98161 | DGVTour #3 - Gnomes Challenge | 238 | 237 (100%) | Yes |  |
| 4 | 98162 | DGVTour #4 - Quarries Throwdown + WGE | 314 | 313 (100%) | Yes |  |
| 5 | 98220 | DGVTour #5 - Sap Bucket Open | 170 | 169 (99%) | Yes |  |
| 6 | 97998 | DGVTour #6 - Brewster Ridge Open Driven by Innova - DGPT Q-Series | 1059 | 1043 (98%) | Yes |  |
| 7 | 98242 | DGVTour #7 - Black Falls Open | 222 | 222 (100%) | Yes |  |
| 8 | 98252 | DGVTour #8 - North Calais Open | 252 | 249 (99%) | Yes |  |
| 9 | 98424 | DGVTour #9 - Kingdom Open | 208 | 206 (99%) | Yes |  |
| 10 | 98313 | DGVTour #10 - Capital City Cup | 126 | 126 (100%) | Yes |  |
| 11 | 98254 | DGVTour #11 - Cold Hollow Classic | 302 | 300 (99%) | Yes |  |
| Finals | 98262 | DGVTour Finals - Vermont State Championship | 0 | | | Not played yet (October 10-11) |

### 2025

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 87899 | DGVTour #1 - South Shire Shootout | 268 | 266 (99%) | Yes |  |
| 2 | 87900 | DGVTour #2 - Gnomes Challenge XVII | 226 | 225 (100%) | Yes |  |
| 3 | 88027 | DGVTour #3 - Quarries Throwdown | 308 | 302 (98%) | Yes |  |
| 4 | 88189 | DGVTour #4 - Battle of Pittsford | 160 | 159 (99%) | Yes |  |
| 5 | 86523 | DGVTour #5 - Brewster Ridge Open | 1050 | 1004 (96%) | Yes |  |
| 6 | 88944 | DGVTour #6 - Black Falls Open | 236 | 232 (98%) | Yes |  |
| 7 | 90019 | DGVTour #7 - Lincoln Peak Open | 104 | 103 (99%) | Yes |  |
| 8 | 90283 | DGVTour #8 - North Calais Open | 250 | 247 (99%) | Yes |  |
| 9 | 90932 | DGVTour #9 - Sap Bucket Open XXIII | 144 | 143 (99%) | Yes |  |
| 10 | 91169 | DGVTour #10 - Horace Hill Huck | 86 | 84 (98%) | Yes |  |
| 11 | 91399 | DGVTour #11 - Cold Hollow Classic | 308 | 306 (99%) | Yes |  |
| Finals | 91411 | DGVTour Finals - Vermont State Championship | 360 | 357 (99%) | Yes |  |

### 2024

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 77672 | DGVTour #1 - South Shire Shootout | 318 | 315 (99%) | Yes |  |
| 2 | 77674 | DGVTour #2 - Gnomes Challenge XVI | 266 | 266 (100%) | Yes |  |
| 3 | 77909 | DGVTour #3 - Quarries Throwdown | 322 | 317 (98%) | Yes |  |
| 4 | 77695 | DGVTour #4 - Sap Bucket Open XXII | 298 | 296 (99%) | Yes |  |
| 5 | 76286 | DGVTour #5 - Brewster Ridge Open | 1029 | 1012 (98%) | Yes |  |
| 6 | 78661 | DGVTour #6 - Sugarbush Huk | 174 | 174 (100%) | Yes |  |
| 7 | 78807 | DGVTour #7 - Jeezum Crow Jam | 90 | 87 (97%) | Yes |  |
| 8 | 78862 | DGVTour #8 - North Calais Open | 238 | 238 (100%) | Yes |  |
| 9 | 78961 | DGVTour #9 - Black Falls Open | 246 | 243 (99%) | Yes |  |
| 10 | 79122 | DGVTour #10 - Pittsford Fling | 152 | 151 (99%) | Yes |  |
| 11 | 79898 | DGVTour #11 - Cold Hollow Classic | 338 | 337 (100%) | Yes |  |
| Finals | 79942 | DGVTour Finals - Vermont State Championship | 410 | 403 (98%) | Yes |  |

### 2023

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 67158 | DGVTour Opener - South Shire Shootout | 290 | 285 (98%) | Yes |  |
| 2 | 67159 | DGVTour #2 - Gnomes Challenge XV | 268 | 265 (99%) | Yes |  |
| 3 | 67160 | DGVTour #3 - Quarries Throwdown | 304 | 301 (99%) | Yes |  |
| 4 | 67161 | DGVTour #4 - Sap Bucket Open XXI | 340 | 339 (100%) | Yes |  |
| 5 | 67514 | DGVTour #5 - Brewster Ridge Open Driven by Innova | 1008 | 979 (97%) | Yes |  |
| 6 | 67713 | DGVTour #6 - Jeezum Crow Jam | 146 | 144 (99%) | Yes |  |
| 7 | 67796 | DGVTour #7 - Black Falls Open | 292 | 291 (100%) | Yes |  |
| 8 | 68282 | DGVTour #8 - North Calais Open | 256 | 253 (99%) | Yes |  |
| 9 | 68349 | DGVTour #9 - Magic Mountain Open | 0 | | | Cancelled |
| 10 | 68642 | DGVTour #10 - Cold Hollow Classic | 350 | 348 (99%) | Yes |  |
| 11 | 68786 | DGVTour #11 - The Hills Are Alive | 214 | 214 (100%) | Yes |  |
| Finals | 68805 | DGVTour Finals - Vermont State Championship | 460 | 448 (97%) | Yes |  |

### 2022

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 57217 | DGVTour Opener - South Shire Open | 302 | 301 (100%) | Yes |  |
| 2 | 57218 | DGVTour #2 - Hometown Huck | 178 | 178 (100%) | Yes |  |
| 3 | 57219 | DGVTour #3 - Quarries Throwdown | 326 | 321 (98%) | Yes |  |
| 4 | 57221 | DGVTour #4 - 20th Annual Sap Bucket Open | 362 | 355 (98%) | Yes |  |
| 5 | 55101 | Brewster Ridge Open Driven by Innova | 957 | 947 (99%) | Yes |  |
| 6 | 57225 | DGVTour #6 - Gnomes Challenge | 206 | 206 (100%) | Yes |  |
| 7 | 57226 | DGVTour #7 - Black Falls Open | 280 | 277 (99%) | Yes |  |
| 8 | 57228 | DGVTour #8 - Lincoln Peak Open | 144 | 143 (99%) | Yes |  |
| 9 | 57229 | DGVTour #9 - 30th Annual North Calais Open | 264 | 258 (98%) | Yes |  |
| 10 | 57230 | DGVTour #10 - Magic Mountain Open | 180 | 178 (99%) | Yes |  |
| 11 | 62737 | DGVTour #11 Jay Peak Open | 106 | 106 (100%) | Yes |  |
| 11 | 57231 | DGVTour #11 - Vista Beast Challenge | 0 | | | Cancelled |
| 12 | 57232 | DGVTour #12 - The Hills Are Alive | 174 | 173 (99%) | Yes |  |
| 13 | 57233 | DGVTour #13 - Cold Hollow Classic | 268 | 266 (99%) | Yes |  |
| Finals | 57234 | DGVTour Finals - Vermont State Championship | 282 | 281 (100%) | Yes |  |

### 2021

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 49941 | DGVTour #1 South Shire Open | 334 | 330 (99%) | Yes |  |
| 2 | 49942 | DGVTour #2 Stone Village Shootout + WGE | 172 | 168 (98%) | Yes |  |
| 3 | 49943 | DGVTour #3 Quarries Throwdown | 298 | 296 (99%) | Yes |  |
| 4 | 49944 | DGVTour #4 Sap Bucket Open XVIII | 360 | 355 (99%) | Yes |  |
| 5 | 49945 | DGVTour #5 Brewster Ridge Open | 756 | 754 (100%) | Yes |  |
| 6 | 49951 | DGVTour #6 Gnomes Challenge | 186 | 186 (100%) | Yes |  |
| 7 | 49952 | DGVTour #7 Run for the Border | 303 | 298 (98%) | Yes |  |
| 8 | 49953 | DGVTour #8 Magic Mountain Open | 252 | 250 (99%) | Yes |  |
| 9 | 49954 | DGVTour #9 North Calais Open | 214 | 0 (0%) | Yes | Hole scores for only 4 of 214 player-rounds |
| 10 | 49955 | DGVTour #10 Base Camp Open | 120 | 119 (99%) | Yes |  |
| 11 | 49956 | DGVTour #11 Vista Beast Challenge | 132 | 132 (100%) | Yes |  |
| 12 | 49957 | DGVTour #12 Rotary Southern Vermont Championship | 128 | 127 (99%) | Yes |  |
| Finals | 49958 | DGVTour Finals Vermont State Championship | 288 | 286 (99%) | Yes |  |

### 2020

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 2 | 45898 | DGVTour #2 - The BRO | 268 | 268 (100%) | Yes |  |
| 3 | 46036 | DGVT #3 - Sap Bucket Open XVII | 256 | 256 (100%) | Yes |  |
| 4 | 46247 | DGVT #4 Run for the Border | 184 | 182 (99%) | Yes |  |
| 5 | 46474 | DGVT #5 Gnomes Challenge XIII | 190 | 190 (100%) | Yes |  |
| 6 | 46697 | DGVTour #6 - North Calais Open | 170 | 169 (99%) | Yes |  |
| 7 | 46877 | DGVT #7 Wrightsville Beach Open | 184 | 78 (42%) | Yes | Hole scores for only 88 of 184 player-rounds |
| 8 | 47319 | DGVT #8 Stone Village Shootout | 96 | 96 (100%) | Yes |  |
| 9 | 47320 | DGVT #9 Vista Beast Challenge | 154 | 150 (97%) | Yes |  |
| Finals | 47321 | DGVT Vermont State Championship/Tour Finals | 114 | 114 (100%) | Yes |  |

### 2019

| Stop | Event ID | Event | Player-rounds | Usable | Hole scores | Notes |
|---|---|---|---|---|---|---|
| 1 | 40642 | DGVTour #1 Sap Bucket Open | 178 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 2 | 40643 | DGVTour #2 Quarries Throwdown | 172 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 4 | 41154 | DGVTour #4 Black Falls Open | 176 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 5 | 41155 | DGVTour #5 Base Camp Open | 150 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 6 | 41384 | DGVTour #6 Brewster Ridge Open | 276 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 7 | 41156 | DGVTour #7 Wrightsville Beach Open | 166 | 0 (0%) | No | No hole-by-hole scores on PDGA Live |
| 9 | 41157 | DGVTour #9 Bolton Valley Vista Beast | 140 | 73 (52%) | Yes | Hole scores for only 74 of 140 player-rounds |
| Finals | 41158 | DGV Tour Finals VT State Championships | 118 | 106 (90%) | Yes | Hole scores for only 106 of 118 player-rounds |
