#!/usr/bin/env python3
"""
Snälltåget availability scraper — daily price snapshot for night trains.

Fetches calendar (service dates) then searchjourney per date, extracts:
- "direct": D 10300/10301 or D 300/301 (1 leg, STNIGHT) — Sitz + Berth + Compartment
- "transfer": D 300 + 3940 or 3943 + 301 (2 legs, STNIGHT+STTRAIN) — combined

Bidirectional route pairs share searchjourney calls via the `oppositedate` parameter.

## oppositedate optimization

The searchjourney endpoint accepts an `oppositedate` parameter (>= departure date).
When set, the response includes a second Travel with routes for the return direction
on that date. This halves the number of API requests for paired routes.

Algorithm (two-pointer):
1. Fetch calendar for both directions → sorted lists of service dates
2. Pair dates chronologically from both lists (one outbound + one inbound per request)
3. Constraint: oppositedate >= departure. If in_date < out_date, reverse the query
   direction (query inbound as departure, outbound as oppositedate)
4. Tail: unpaired dates from the longer list are queried individually

Optimal requests = max(len_outbound_dates, len_inbound_dates).

## Limitations

- Calendar includes day trains (Svc 306/307) which inflate service date counts.
  These dates produce no STNIGHT bundles but still cost a request.
- The travels array in the response is unordered. Direction is determined by
  matching the first leg's departure station against the known origin.
- Only STNIGHT services are extracted. STTRAIN-only routes (day trains) are ignored.

Usage:
    python3 snalltaget_availability.py --days 120 -q -o data/snalltaget

Output: YYYYMMDD_route.json per route (8 routes).
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from snalltaget_common import get_token, api_post, fetch_calendar, fetch_searchjourney

sys.stdout.reconfigure(encoding='utf-8')



# Station name mapping for output filenames
STATION_NAMES = {
    "740000001": "stockholm", "740000003": "malmoe",
    "Berlin": "berlin", "Hamburg": "hamburg", "Dresden": "dresden",
    "Malmö C": "malmoe", "Köpenhamn": "kopenhamn",
    "760000100": "oslo", "740000115": "are",
    "810000522": "innsbruck", "810000320": "zell-am-see",
}

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "data" / "snalltaget"





def extract_routes(offer, outbound_origin, inbound_origin):
    """Extract outbound and inbound routes from searchjourney offer.

    Direction is determined by checking if the first leg's departure station
    matches the outbound origin (by name substring or UIC code).

    Returns:
        outbound: (direct, transfer) or (None, None)
        inbound: (direct, transfer) or (None, None)
    """
    out_direct = None
    out_transfer = None
    in_direct = None
    in_transfer = None

    def matches_origin(station, origin):
        """Check if a station matches the given origin identifier."""
        name = station.get("name", "")
        uic = station.get("uicStationCode", "")
        # Exact match on UIC
        if origin == uic:
            return True
        # Origin is a name: check if station name starts with it (Berlin -> Berlin Hbf)
        if name.startswith(origin) or origin.startswith(name):
            return True
        return False

    for travel in offer.get("travels", []):
        for route in travel.get("routes", []):
            legs = route.get("legs", [])
            bundles = route.get("bundles", [])
            if not bundles or not legs:
                continue

            bundle_data = [
                {"productFamilyId": b.get("productFamilyId"),
                 "price": b.get("price"),
                 "originalPrice": b.get("originalPrice")}
                for b in bundles
            ]

            # Determine direction from first leg's departure station
            first_dep = legs[0].get("departureStation", {})
            is_outbound = matches_origin(first_dep, outbound_origin)

            if len(legs) == 1:
                leg = legs[0]
                svc_id = leg.get("serviceIdentifier", "")
                if "STNIGHT" in svc_id:
                    entry = {"serviceIdentifier": svc_id, "bundles": bundle_data}
                    if is_outbound:
                        out_direct = entry
                    else:
                        in_direct = entry

            elif len(legs) == 2:
                svc_id_0 = legs[0].get("serviceIdentifier", "")
                svc_id_1 = legs[1].get("serviceIdentifier", "")
                # Outbound: STNIGHT first, STTRAIN second (night + day continuation)
                # Inbound: STTRAIN first, STNIGHT second (day + night continuation)
                is_night_day = "STNIGHT" in svc_id_0 and "STTRAIN" in svc_id_1
                is_day_night = "STTRAIN" in svc_id_0 and "STNIGHT" in svc_id_1
                if is_night_day or is_day_night:
                    entry = {"serviceIdentifiers": [svc_id_0, svc_id_1], "bundles": bundle_data}
                    if is_outbound:
                        out_transfer = entry
                    else:
                        in_transfer = entry

    return (out_direct, out_transfer), (in_direct, in_transfer)


def get_all_calendar(token, origin, destination, direction, today, days_ahead):
    """Fetch calendar for all months in range, return dict of date -> entry."""
    all_calendar = {}
    months_ahead = max(1, (days_ahead + 29) // 30)
    current = today.replace(day=1)

    for _ in range(months_ahead):
        begin = current.isoformat()
        if current.month == 12:
            end_date = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

        try:
            data = fetch_calendar(token, origin, destination, direction, begin, end_date.isoformat())
            all_calendar.update(data.get("calendar", {}))
        except Exception:
            pass

        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return all_calendar


def scrape_pair(token, origin, destination, out_label, in_label, today, days_ahead, date_prefix, out_dir, quiet=False):
    """Scrape a bidirectional route pair using oppositedate optimization."""
    errors = 0
    requests_made = 0

    # Step 1: Calendar for both directions
    out_calendar = get_all_calendar(token, origin, destination, "outbound", today, days_ahead)
    in_calendar = get_all_calendar(token, destination, origin, "inbound", today, days_ahead)

    # Step 2: Build sorted date lists (only dates within our range)
    all_dates = set((today + timedelta(days=i)).isoformat() for i in range(days_ahead))
    out_service_dates = sorted(d for d in out_calendar if d in all_dates)
    in_service_dates = sorted(d for d in in_calendar if d in all_dates)

    # Step 3: Initialize output dicts with no-service markers
    out_data = {}
    in_data = {}
    for date in sorted(all_dates):
        if date not in out_calendar:
            out_data[date] = {"info": "no service"}
        if date not in in_calendar:
            in_data[date] = {"info": "no service"}

    # Step 4: Two-pointer pairing — minimize requests by pairing out/in dates
    # Rule: oppositedate must be >= departure. So:
    #   - If out_date <= in_date: query outbound (departure=out_date, oppositedate=in_date)
    #   - If in_date < out_date: query inbound (departure=in_date, oppositedate=out_date)
    # Both pointers always advance together → max(len_out, len_in) requests total.

    i_out = 0
    i_in = 0

    while i_out < len(out_service_dates) and i_in < len(in_service_dates):
        time.sleep(0.2)
        out_date = out_service_dates[i_out]
        in_date = in_service_dates[i_in]

        if out_date <= in_date:
            # Query outbound, piggyback inbound
            try:
                result = fetch_searchjourney(token, origin, destination, out_date, oppositedate=in_date)
                requests_made += 1
                offer = result.get("offer", {})
                (out_d, out_t), (in_d, in_t) = extract_routes(offer, origin, destination)

                entry = {"calendar": out_calendar[out_date]}
                if out_d:
                    entry["direct"] = out_d
                if out_t:
                    entry["transfer"] = out_t
                out_data[out_date] = entry

                entry_in = {"calendar": in_calendar[in_date]}
                if in_d:
                    entry_in["direct"] = in_d
                if in_t:
                    entry_in["transfer"] = in_t
                in_data[in_date] = entry_in

            except HTTPError as e:
                if e.code in (400, 404):
                    out_data[out_date] = {"error": e.code, "calendar": out_calendar[out_date]}
                    in_data[in_date] = {"error": e.code, "calendar": in_calendar[in_date]}
                else:
                    errors += 1
            except Exception:
                errors += 1

        else:
            # in_date < out_date: query inbound, piggyback outbound
            try:
                result = fetch_searchjourney(token, destination, origin, in_date, oppositedate=out_date)
                requests_made += 1
                offer = result.get("offer", {})
                # From inbound perspective: departure=destination→origin, opposite=origin→destination
                (in_d, in_t), (out_d, out_t) = extract_routes(offer, destination, origin)

                entry_in = {"calendar": in_calendar[in_date]}
                if in_d:
                    entry_in["direct"] = in_d
                if in_t:
                    entry_in["transfer"] = in_t
                in_data[in_date] = entry_in

                entry_out = {"calendar": out_calendar[out_date]}
                if out_d:
                    entry_out["direct"] = out_d
                if out_t:
                    entry_out["transfer"] = out_t
                out_data[out_date] = entry_out

            except HTTPError as e:
                if e.code in (400, 404):
                    in_data[in_date] = {"error": e.code, "calendar": in_calendar[in_date]}
                    out_data[out_date] = {"error": e.code, "calendar": out_calendar[out_date]}
                else:
                    errors += 1
            except Exception:
                errors += 1

        i_out += 1
        i_in += 1

    # Tail: remaining unpaired dates (one list is longer than the other)
    while i_out < len(out_service_dates):
        out_date = out_service_dates[i_out]
        time.sleep(0.2)
        try:
            result = fetch_searchjourney(token, origin, destination, out_date)
            requests_made += 1
            offer = result.get("offer", {})
            (out_d, out_t), _ = extract_routes(offer, origin, destination)

            entry = {"calendar": out_calendar[out_date]}
            if out_d:
                entry["direct"] = out_d
            if out_t:
                entry["transfer"] = out_t
            out_data[out_date] = entry

        except HTTPError as e:
            if e.code in (400, 404):
                out_data[out_date] = {"error": e.code, "calendar": out_calendar[out_date]}
            else:
                errors += 1
        except Exception:
            errors += 1
        i_out += 1

    while i_in < len(in_service_dates):
        in_date = in_service_dates[i_in]
        time.sleep(0.2)
        try:
            result = fetch_searchjourney(token, destination, origin, in_date)
            requests_made += 1
            offer = result.get("offer", {})
            (in_d, in_t), _ = extract_routes(offer, destination, origin)

            entry = {"calendar": in_calendar[in_date]}
            if in_d:
                entry["direct"] = in_d
            if in_t:
                entry["transfer"] = in_t
            in_data[in_date] = entry

        except HTTPError as e:
            if e.code in (400, 404):
                in_data[in_date] = {"error": e.code, "calendar": in_calendar[in_date]}
            else:
                errors += 1
        except Exception:
            errors += 1
        i_in += 1

    # Step 5: Save both files
    out_file = out_dir / f"{date_prefix}_{out_label}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    in_file = out_dir / f"{date_prefix}_{in_label}.json"
    with open(in_file, "w", encoding="utf-8") as f:
        json.dump(in_data, f, indent=2, ensure_ascii=False)

    if not quiet:
        out_with_data = len([d for d in out_data.values() if "direct" in d or "transfer" in d])
        in_with_data = len([d for d in in_data.values() if "direct" in d or "transfer" in d])
        print(f"  {out_label}: {out_with_data} dates | {in_label}: {in_with_data} dates | "
              f"{requests_made} requests (saved ~{len(out_service_dates) + len(in_service_dates) - requests_made})")

    return requests_made, errors


def station_name(code):
    """Resolve station code/name to short name for filenames."""
    if code in STATION_NAMES:
        return STATION_NAMES[code]
    return code.lower().replace(" ", "-").replace("ö", "oe").replace("ä", "ae")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Snälltåget availability scraper (bidirectional, oppositedate optimized)"
    )
    parser.add_argument("origin", help="Origin station (name or UIC code, e.g. Berlin or 740000001)")
    parser.add_argument("destination", help="Destination station (name or UIC code)")
    parser.add_argument("--days", type=int, default=120, help="Days ahead to scrape")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-o", "--output-dir", default=str(DATA_DIR))
    args = parser.parse_args()

    out_label = f"{station_name(args.origin)}-{station_name(args.destination)}"
    in_label = f"{station_name(args.destination)}-{station_name(args.origin)}"

    today = datetime.now().date()
    date_prefix = today.strftime("%Y%m%d")
    out_dir = Path(args.output_dir)

    if not args.quiet:
        print(f"[{datetime.now().isoformat()}] Snälltåget: {out_label} + {in_label}, {args.days} days")

    token = get_token()
    out_dir.mkdir(parents=True, exist_ok=True)

    requests, errs = scrape_pair(
        token, args.origin, args.destination, out_label, in_label,
        today, args.days, date_prefix, out_dir, args.quiet
    )

    if not args.quiet:
        print(f"\n  Total: {requests} API requests. Errors: {errs}")

    return 0 if errs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
