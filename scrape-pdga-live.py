#!/usr/bin/env python3
"""
PDGA Live Detailed Scraper — DGVT play styles project

Builds the player x hole x round table for Disc Golf Vermont Tour (DGVT)
events, 2019-2026. It runs the first two stages of the project pipeline:

  1. Scrape: find DGVT events with the pdga.com event search, then download the
     raw PDGA Live JSON for every event, division and round, plus each event's
     results page (for player ratings at the time of the event). Every response
     is saved under data/raw/, so a page is never downloaded twice. Events that
     haven't finished yet are always re-downloaded.

  2. Parse: turn the cached raw files into tidy tables under data/processed/:
       events.csv       one row per event, with how much hole-by-hole data it has
       holes.csv        one row per layout x hole (par, length)
       rounds.csv       one row per player x round, with data-quality checks
       hole_scores.csv  one row per player x hole x round (the unit of analysis)

The PDGA Live React app reads two JSON endpoints, which we call directly:
  live_results_fetch_event?TournID={event}
      event metadata, divisions, rounds, and every layout used
  live_results_fetch_round?TournID={event}&Division={div}&Round={rnd}
      per-player hole scores; each player has their own LayoutID, since
      divisions in the same round can play different tees

Usage:
    python scrape-pdga-live.py                          # all DGVT tour events, 2019-2026
    python scrape-pdga-live.py --years 2024-2026        # a subset of seasons
    python scrape-pdga-live.py --events 98424,98552     # specific events (any event ID)
    python scrape-pdga-live.py --include-leagues        # also DGVT flex leagues
    python scrape-pdga-live.py --parse-only             # rebuild tables from data/raw, no network

The tables in data/processed always cover every event cached in data/raw, so
scraping one more event into an existing data folder adds it to the tables.
    python scrape-pdga-live.py --refresh                # ignore the cache and re-download
"""

import argparse, csv, json, logging, os, re, sys, time
from datetime import date

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
PDGA = "https://www.pdga.com"
SEARCH_URL = f"{PDGA}/tour/search"
RESULTS_URL = f"{PDGA}/tour/event"
LIVE_API = f"{PDGA}/apps/tournament/live-api"
EVENT_API = f"{LIVE_API}/live_results_fetch_event"
ROUND_API = f"{LIVE_API}/live_results_fetch_round"

DEFAULT_YEARS = (2019, 2026)
# Tour stops are named "DGVTour #3 ...", "DGVT #5 ...", "DGV Tour Finals ...".
DGVT_NAME = re.compile(r"^\s*DGV\s?T", re.IGNORECASE)
LEAGUE_TIER = "L"

REQUEST_DELAY = 1.0  # seconds between live requests; cached reads don't wait
DATA_DIR = "data"
UNFINISHED_SCORE = 999  # PDGA's placeholder score for an unfinished round
METERS_TO_FEET = 3.28084

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pdga-live")


# ---------------------------------------------------------------------------
# HTTP with an on-disk cache
# ---------------------------------------------------------------------------
def create_session():
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    retry = Retry(total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_cached(session, url, params, path, refresh=False):
    """
    Return the response body for url, reading from path when it's cached.
    Returns None on a 404 (e.g. a round a division didn't play); nothing is cached then.
    """
    if not refresh and os.path.exists(path):
        with open(path) as f:
            return f.read()

    time.sleep(REQUEST_DELAY)
    resp = session.get(url, params=params, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(resp.text)
    return resp.text


def raw_dir(event_id):
    return os.path.join(DATA_DIR, "raw", "live", str(event_id))


def read_json(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def api_data(text):
    """PDGA Live responses look like {"data": {...}, "hash": "..."}."""
    if not text:
        return None
    raw = json.loads(text)
    return raw.get("data") if isinstance(raw, dict) else None


# ---------------------------------------------------------------------------
# Stage 1a: find DGVT events
# ---------------------------------------------------------------------------
def discover_events(session, years, include_leagues=False):
    """
    Search pdga.com for events named DGV* in the given years and return
    [{event_id, name, tier, location, dates}], keeping DGVT tour stops only
    (and flex leagues if include_leagues). Always hits the network, since the
    search results change as new events are added.
    """
    first, last = years
    params = {
        "OfficialName": "DGV",
        "date_filter[min][date]": f"{first}-01-01",
        "date_filter[max][date]": f"{last}-12-31",
    }
    events = []
    for page in range(50):
        time.sleep(REQUEST_DELAY)
        resp = session.get(SEARCH_URL, params={**params, "page": page}, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.select("table.views-table tbody tr"):
            link = row.select_one("td.views-field-OfficialName a")
            if not link:
                continue
            cell = lambda name: (row.select_one(f"td.views-field-{name}") or link).get_text(" ", strip=True)
            events.append({
                "event_id": link["href"].rstrip("/").split("/")[-1],
                "name": link.get_text(" ", strip=True),
                "tier": cell("Tier"),
                "location": cell("Location"),
                "dates": cell("StartDate"),
            })
        if not soup.select_one("li.pager-next"):
            break

    keep = [e for e in events
            if DGVT_NAME.match(e["name"])
            and "Vermont" in e["location"]
            and (include_leagues or e["tier"] != LEAGUE_TIER)]
    log.info(f"Found {len(events)} events named DGV*, kept {len(keep)} DGVT events")

    path = os.path.join(DATA_DIR, "raw", "dgvt_events.csv")
    write_csv(path, keep)
    return keep


# ---------------------------------------------------------------------------
# Stage 1b: download one event
# ---------------------------------------------------------------------------
def is_final(event):
    """True once an event is over and every round has been completed."""
    end = event.get("EndDate")
    if not end or date.fromisoformat(end) >= date.today():
        return False
    completed, final = event.get("HighestCompletedRound"), event.get("FinalRound")
    return completed is None or final is None or int(completed) >= int(final)


def event_rounds(event):
    """[(round number, label, date)] for every round in the event, finals included."""
    rounds_list = event.get("RoundsList")
    if isinstance(rounds_list, dict) and rounds_list:
        rounds = []
        for key, info in rounds_list.items():
            info = info if isinstance(info, dict) else {}
            rounds.append((int(info.get("Number", key)), info.get("Label"), info.get("Date")))
        return sorted(rounds)
    n = event.get("Rounds") or 0
    return [(r, f"Round {r}", None) for r in range(1, int(n) + 1)]


def scrape_event(session, event_id, refresh=False):
    """Download the raw event, round, and results pages for one event."""
    folder = raw_dir(event_id)
    event_path = os.path.join(folder, "event.json")

    # Re-download the event itself when the cached copy isn't final yet.
    cached = api_data(open(event_path).read()) if os.path.exists(event_path) else None
    stale = refresh or cached is None or not is_final(cached)
    event = api_data(fetch_cached(session, EVENT_API, {"TournID": event_id}, event_path, stale))
    if not event:
        log.warning(f"  {event_id}: no PDGA Live data")
        return

    start = event.get("StartDate")
    if start and date.fromisoformat(start) > date.today():
        log.info(f"  {event_id}: {event.get('Name')} hasn't started yet, skipping")
        return

    stale = refresh or not is_final(event)
    rounds = event_rounds(event)
    log.info(f"  {event_id}: {event.get('Name')} ({event.get('DateRange')}), "
             f"{len(event.get('Divisions') or [])} divisions, {len(rounds)} rounds"
             + ("" if is_final(event) else " [not final, re-downloading]"))

    for div in event.get("Divisions") or []:
        code = div.get("Division")
        latest = div.get("LatestRound")
        for rnd, _, _ in rounds:
            if latest is not None and rnd > int(latest):
                continue
            path = os.path.join(folder, f"{code}_r{rnd}.json")
            fetch_cached(session, ROUND_API,
                         {"TournID": event_id, "Division": code, "Round": rnd},
                         path, stale)

    fetch_cached(session, f"{RESULTS_URL}/{event_id}", None,
                 os.path.join(folder, "results.html"), stale)


# ---------------------------------------------------------------------------
# Stage 2: parse raw files into tidy tables
# ---------------------------------------------------------------------------
def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def score_or_none(value):
    """Round/total scores of 999 mean the round wasn't finished."""
    n = to_int(value)
    return None if n is None or n >= UNFINISHED_SCORE else n


def player_key(score):
    """PDGA number when the player has one, otherwise their name."""
    pdga = to_int(score.get("PDGANum"))
    return str(pdga) if pdga else f"name:{(score.get('Name') or '').strip().lower()}"


def parse_event_ratings(html):
    """
    {pdga_number: rating} from the results page. The live API's Rating field is
    the player's *current* rating; the results page has the rating at the time
    of the event.
    """
    if not html:
        return {}
    ratings = {}
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.select("tr"):
        num, rating = row.select_one("td.pdga-number"), row.select_one("td.player-rating")
        if num and rating:
            num, rating = to_int(num.get_text(strip=True)), to_int(rating.get_text(strip=True))
            if num and rating:
                ratings[num] = rating
    return ratings


def add_layout(layouts, L, details_key):
    """Merge one layout object into {layout_id: layout} with per-hole par and length."""
    layout_id = to_int(L.get("LayoutID"))
    if layout_id is None:
        return
    units = L.get("Units") or ""
    scale = METERS_TO_FEET if units.lower().startswith("m") else 1.0
    layout = layouts.setdefault(layout_id, {"holes": {}})
    layout.update({
        "layout_id": layout_id,
        "course_id": L.get("CourseID"),
        "course_name": L.get("CourseName") or layout.get("course_name"),
        "layout_name": L.get("Name"),
        "n_holes": to_int(L.get("Holes")),
        "layout_par": to_int(L.get("Par")),
        "layout_length_ft": round(L["Length"] * scale) if L.get("Length") else None,
    })
    for i, d in enumerate(L.get(details_key) or [], 1):
        ordinal = to_int(d.get("HoleOrdinal")) or to_int(str(d.get("Hole", "")).lstrip("H")) or i
        length = to_int(d.get("Length"))
        layout["holes"][ordinal] = {
            "hole": ordinal,
            "hole_label": d.get("Label") or str(ordinal),
            "par": to_int(d.get("Par")),
            "length_ft": round(length * scale) if length else None,
        }


def parse_event(event_id):
    """Parse one event's raw files into rows for each output table."""
    folder = raw_dir(event_id)
    event = api_data(open(os.path.join(folder, "event.json")).read())
    if not event:
        return None

    results_path = os.path.join(folder, "results.html")
    ratings = parse_event_ratings(open(results_path).read() if os.path.exists(results_path) else None)
    round_info = {rnd: (label, day) for rnd, label, day in event_rounds(event)}
    year = to_int((event.get("StartDate") or "")[:4])

    layouts = {}
    for L in event.get("Layouts") or []:
        add_layout(layouts, L, "Details")

    round_rows, hole_rows, seen = [], [], set()
    for fname in sorted(os.listdir(folder)):
        m = re.fullmatch(r"(.+)_r(\d+)\.json", fname)
        if not m:
            continue
        division, rnd = m.group(1), int(m.group(2))
        data = api_data(open(os.path.join(folder, fname)).read())
        if not isinstance(data, dict):
            continue
        for L in data.get("layouts") or []:
            add_layout(layouts, L, "Detail")  # round-level details have hole ordinals

        for s in data.get("scores") or []:
            # Only keep this round's scores, once per player.
            if to_int(s.get("Round")) != rnd:
                continue
            key = (s.get("ResultID") or player_key(s), rnd)
            if key in seen:
                continue
            seen.add(key)

            layout = layouts.get(to_int(s.get("LayoutID")), {"holes": {}})
            raw_holes = s.get("HoleScores")
            if raw_holes is None:  # older responses only have the padded string
                raw_holes = (s.get("Scores") or "").split(",")[: to_int(s.get("Holes")) or 0]
            pars = (s.get("Pars") or "").split(",")
            hole_scores = [to_int(v) for v in raw_holes]

            n_holes = to_int(s.get("Holes")) or layout.get("n_holes") or len(hole_scores)
            scored = [v for v in hole_scores if v is not None]
            raw_round_score = to_int(s.get("RoundScore"))
            round_score = score_or_none(raw_round_score)
            hole_sum = sum(scored) if scored else None
            all_holes = len(scored) == n_holes and n_holes > 0
            sum_matches = hole_sum is not None and hole_sum == round_score
            pdga = to_int(s.get("PDGANum"))
            label, round_date = round_info.get(rnd, (None, None))

            base = {
                "event_id": event_id,
                "year": year,
                "division": division,
                "round": rnd,
                "layout_id": to_int(s.get("LayoutID")),
                "player_key": player_key(s),
                "pdga_number": pdga,
                "event_rating": ratings.get(pdga),
            }
            round_rows.append({
                **base,
                "round_label": label,
                "round_date": round_date,
                "player_name": s.get("Name"),
                "current_rating": to_int(s.get("Rating")),
                "course_name": layout.get("course_name"),
                "layout_name": layout.get("layout_name"),
                "layout_par": layout.get("layout_par"),
                "n_holes": n_holes,
                "card_number": s.get("CardNum"),
                "tee_time": s.get("TeeTime"),
                "round_score": round_score,
                "round_to_par": to_int(s.get("RoundtoPar")) if round_score is not None else None,
                "round_rating": to_int(s.get("RoundRating")),
                "grand_total": score_or_none(s.get("GrandTotal")),
                "raw_completed": bool(s.get("Completed")),
                "unfinished_999": raw_round_score is not None and raw_round_score >= UNFINISHED_SCORE,
                "holes_scored": len(scored),
                "hole_score_sum": hole_sum,
                "all_holes_scored": all_holes,
                "hole_sum_matches": sum_matches,
                "usable": all_holes and sum_matches,
            })

            for i, score in enumerate(hole_scores, 1):
                if score is None:
                    continue
                hole = layout["holes"].get(i, {})
                par = hole.get("par") or (to_int(pars[i - 1]) if i <= len(pars) else None)
                hole_rows.append({
                    **base,
                    "hole": i,
                    "hole_label": hole.get("hole_label", str(i)),
                    "par": par,
                    "length_ft": hole.get("length_ft"),
                    "score": score,
                    "score_to_par": score - par if par else None,
                    "round_usable": all_holes and sum_matches,
                })

    layout_rows = [
        {"event_id": event_id, **{k: v for k, v in L.items() if k != "holes"}, **h}
        for L in layouts.values() for h in sorted(L["holes"].values(), key=lambda h: h["hole"])
    ]

    with_holes = sum(r["holes_scored"] > 0 for r in round_rows)
    usable = sum(r["usable"] for r in round_rows)
    event_row = {
        "event_id": event_id,
        "name": event.get("Name"),
        "year": year,
        "start_date": event.get("StartDate"),
        "end_date": event.get("EndDate"),
        "tier": event.get("Tier"),
        "location": event.get("Location"),
        "scoring_format": event.get("ScoringFormat"),
        "n_rounds": len(round_info),
        "n_divisions": len(event.get("Divisions") or []),
        "n_layouts": len({r["layout_id"] for r in round_rows}),
        "n_players": len({r["player_key"] for r in round_rows}),
        "n_player_rounds": len(round_rows),
        "n_rounds_with_holes": with_holes,
        "n_rounds_usable": usable,
        "n_unfinished_999": sum(r["unfinished_999"] for r in round_rows),
        "share_usable": round(usable / len(round_rows), 3) if round_rows else 0,
        "has_hole_scores": with_holes > 0,
        "is_final": is_final(event),
    }
    return event_row, layout_rows, round_rows, hole_rows


def parse_all(event_ids):
    """Parse every cached event and write the tidy tables."""
    events, holes, rounds, hole_scores = [], [], [], []
    for event_id in event_ids:
        if not os.path.exists(os.path.join(raw_dir(event_id), "event.json")):
            continue
        parsed = parse_event(event_id)
        if not parsed:
            continue
        e, h, r, s = parsed
        events.append(e)
        holes.extend(h)
        rounds.extend(r)
        hole_scores.extend(s)
        log.info(f"  {event_id:>7}  {e['year']}  {e['n_player_rounds']:4d} player-rounds, "
                 f"{e['n_rounds_usable']:4d} usable ({e['share_usable']:.0%}), "
                 f"{len(s):6d} hole scores  {e['name']}")

    out = os.path.join(DATA_DIR, "processed")
    write_csv(os.path.join(out, "events.csv"), events)
    write_csv(os.path.join(out, "holes.csv"), holes)
    write_csv(os.path.join(out, "rounds.csv"), rounds)
    write_csv(os.path.join(out, "hole_scores.csv"), hole_scores)

    usable = sum(r["usable"] for r in rounds)
    log.info(f"\n{len(events)} events ({sum(e['has_hole_scores'] for e in events)} with hole scores), "
             f"{len(rounds)} player-rounds ({usable} usable), {len(hole_scores)} hole scores")
    log.info(f"Unfinished (999) rounds: {sum(r['unfinished_999'] for r in rounds)}; "
             f"hole sum != round score: {sum(r['holes_scored'] > 0 and not r['hole_sum_matches'] for r in rounds)}")
    log.info(f"Tables -> {os.path.abspath(out)}")


def write_csv(path, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_years(text):
    first, _, last = text.partition("-")
    return int(first), int(last or first)


def cached_event_ids():
    folder = os.path.join(DATA_DIR, "raw", "live")
    if not os.path.isdir(folder):
        return []
    return sorted((d for d in os.listdir(folder) if d.isdigit()), key=int)


def main():
    global DATA_DIR, REQUEST_DELAY

    parser = argparse.ArgumentParser(description="Scrape PDGA Live hole-by-hole scores for DGVT events")
    parser.add_argument("--years", default=f"{DEFAULT_YEARS[0]}-{DEFAULT_YEARS[1]}",
                        help="Seasons to search, e.g. 2019-2026 or 2025 (default: %(default)s)")
    parser.add_argument("--events", default=None,
                        help="Comma-separated event IDs to scrape instead of searching")
    parser.add_argument("--include-leagues", action="store_true",
                        help="Also keep DGVT flex leagues (tier L)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-download pages even when they're cached")
    parser.add_argument("--parse-only", action="store_true",
                        help="Skip downloading; rebuild tables from every event in data/raw")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help="Seconds between requests (default: %(default)s)")
    parser.add_argument("--data-dir", default=DATA_DIR, help="Root data folder (default: %(default)s)")
    args = parser.parse_args()

    DATA_DIR, REQUEST_DELAY = args.data_dir, args.delay

    if not args.parse_only:
        session = create_session()
        if args.events:
            event_ids = [e.strip() for e in args.events.split(",")]
        else:
            event_ids = [e["event_id"] for e in
                         discover_events(session, parse_years(args.years), args.include_leagues)]

        log.info(f"Scraping {len(event_ids)} events")
        failed = []
        for event_id in event_ids:
            try:
                scrape_event(session, event_id, args.refresh)
            except (requests.RequestException, ValueError) as e:
                log.error(f"  {event_id}: failed ({e})")
                failed.append(event_id)
        if failed:
            log.warning(f"Failed events: {', '.join(failed)}")

    # Tables always cover every cached event, so adding one event keeps the rest.
    log.info("\nParsing raw files")
    parse_all(cached_event_ids())


if __name__ == "__main__":
    sys.exit(main())
