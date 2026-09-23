#!/usr/bin/env python3
"""
NOX Mobility availability scraper — daily price + capacity snapshot.

NOX (noxmobility.com) is a German night-train startup. Single route so far:
Hamburg Hbf <-> München Hbf (train 1791 southbound, 1790 northbound), season
2027-03-23 .. 2027-12-10, ~6 days/week (one rest day per week).

Unlike the tier-scanning providers (LEO/RDC/SJ), NOX exposes real remaining
capacity directly: search returns availability.{available,total,status}. No
multi-passenger probing needed — one GET per date.

Flow per direction:
  1. fare-calendar (from,to,dateFrom,dateTo,adults=1) -> per-day status
     (available|no_service). Cheap way to skip no-service days.
  2. search (from,to,date,adults=1) only on available days -> trip with
     availability + per-tariff prices.

Public REST/JSON, no auth. Origin header only.

Snapshot format (unified with other scrapers):
  { "YYYY-MM-DD": { "info": "no service" }
                 | { "trainNumber": "1791", "available": 46, "total": 78,
                     "status": "available",
                     "classes": [ {"type": "Basic", "price": 66},
                                  {"type": "Flex",  "price": 116} ] }
                 | { "__error__": "..." } }

Usage:
    python3 nox_availability.py <fromId> <toId> --days 300 -q -o data/nox

fromId/toId are NOX municipality UUIDs:
  Hamburg  aa8c46ab-660f-4a1d-9422-1dd1d1d8e045
  München  9fb61762-46bf-462f-9e1a-a859d96a87ac
  Bremen   9b341d10-f83b-4a5a-bf31-88b19fdb2d00
  Augsburg 6469cec1-d997-4e19-a7ff-ba4a0e85e769
"""
import argparse
import http.client
import json
import os
import ssl
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

API_HOST = "api.noxmobility.com"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")

# municipality UUID -> short filename token
STATION_NAMES = {
    "aa8c46ab-660f-4a1d-9422-1dd1d1d8e045": "hamburg",
    "9fb61762-46bf-462f-9e1a-a859d96a87ac": "muenchen",
    "9b341d10-f83b-4a5a-bf31-88b19fdb2d00": "bremen",
    "6469cec1-d997-4e19-a7ff-ba4a0e85e769": "augsburg",
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "nox"

_conn = None
_api_calls = 0
_errors = 0


def station_name(uuid):
    return STATION_NAMES.get(uuid, uuid[:8])


def _get_conn():
    global _conn
    if _conn is None:
        ctx = ssl.create_default_context()
        _conn = http.client.HTTPSConnection(API_HOST, timeout=30, context=ctx)
    return _conn


def api_get(path):
    """GET with keep-alive and a single reconnect retry. Returns parsed JSON."""
    global _conn, _api_calls
    headers = {
        "User-Agent": USER_AGENT,
        "Origin": "https://noxmobility.com",
        "Accept": "application/json",
        "Accept-Language": "de",
        "Connection": "keep-alive",
    }
    for attempt in range(2):
        try:
            conn = _get_conn()
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode("utf-8")
            _api_calls += 1
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
            return json.loads(body)
        except (http.client.RemoteDisconnected, ConnectionResetError,
                BrokenPipeError, OSError):
            _conn = None
            if attempt == 0:
                continue
            raise


def fetch_calendar(from_id, to_id, date_from, date_to):
    path = (f"/api/trips/fare-calendar?from={from_id}&to={to_id}"
            f"&dateFrom={date_from}&dateTo={date_to}&adults=1")
    return api_get(path)


def fetch_search(from_id, to_id, date):
    path = (f"/api/trips/search?from={from_id}&to={to_id}"
            f"&date={date}&adults=1&limit=5")
    return api_get(path)


def extract_trip(search_resp):
    """Pick the first bookable result and reduce it to the snapshot shape.

    Returns a dict with trainNumber/available/total/status/classes, or None
    when the day has no result (should not happen for calendar-available days).
    """
    results = search_resp.get("results", [])
    if not results:
        return None
    t = results[0]
    avail = t.get("availability", {}) or {}
    classes = []
    for p in t.get("prices", []):
        classes.append({"type": p.get("tariffClassName"), "price": p.get("amount")})
    return {
        "trainNumber": t.get("trainNumber"),
        "available": avail.get("available"),
        "total": avail.get("total"),
        "status": avail.get("status"),
        "classes": classes,
    }


def main():
    ap = argparse.ArgumentParser(description="NOX Mobility availability scraper")
    ap.add_argument("from_id", help="Origin municipality UUID")
    ap.add_argument("to_id", help="Destination municipality UUID")
    ap.add_argument("--days", type=int, default=300,
                    help="Days ahead to scan (default 300; season ends 2027-12-10)")
    ap.add_argument("-q", "--quiet", action="store_true")
    ap.add_argument("-o", "--output", help="Output directory (default data/nox)")
    args = ap.parse_args()

    from_id, to_id = args.from_id, args.to_id
    route = f"{station_name(from_id)}-{station_name(to_id)}"
    out_dir = Path(args.output) if args.output else DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    start = datetime.now().date() + timedelta(days=1)
    end = start + timedelta(days=args.days - 1)

    global _api_calls, _errors
    _api_calls = 0
    _errors = 0
    t0 = time.time()

    if not args.quiet:
        print(f"NOX scraper: {route}, {args.days} days from {start}")

    # 1) fare-calendar over the whole window (chunked by 62 days — the API
    #    rejects any fare-calendar range > 62 days with HTTP 400)
    day_status = {}  # date_str -> "available" | "no_service"
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=61), end)
        try:
            cal = fetch_calendar(from_id, to_id,
                                 chunk_start.strftime("%Y-%m-%d"),
                                 chunk_end.strftime("%Y-%m-%d"))
            for d in cal.get("days", []):
                day_status[d["date"]] = d.get("status", "no_service")
        except Exception as e:  # noqa: BLE001
            _errors += 1
            if not args.quiet:
                print(f"  calendar {chunk_start}..{chunk_end} ERROR: {e}")
        chunk_start = chunk_end + timedelta(days=1)

    # 2) search only on available days
    snapshot = {}
    avail_days = [d for d, s in day_status.items() if s == "available"]
    for date_str in sorted(day_status):
        if day_status[date_str] != "available":
            snapshot[date_str] = {"info": "no service"}
            continue
        try:
            resp = fetch_search(from_id, to_id, date_str)
            trip = extract_trip(resp)
            if trip is None:
                snapshot[date_str] = {"info": "no service"}
            else:
                snapshot[date_str] = trip
                if not args.quiet:
                    print(f"  {date_str} {trip['trainNumber']} "
                          f"{trip['available']}/{trip['total']}")
        except Exception as e:  # noqa: BLE001
            _errors += 1
            snapshot[date_str] = {"__error__": str(e)}
            if not args.quiet:
                print(f"  {date_str} ERROR: {e}")

    today_prefix = datetime.now().strftime("%Y%m%d")
    fp = out_dir / f"{today_prefix}_{route}.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(snapshot.items())), f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t0
    if not args.quiet:
        print(f"\n  -> {fp.name} ({len(avail_days)} service days)")
        print(f"Done. {_api_calls} API calls in {elapsed:.0f}s. Errors: {_errors}")

    return 0 if _errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
