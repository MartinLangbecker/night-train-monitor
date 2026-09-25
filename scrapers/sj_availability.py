#!/usr/bin/env python3
"""SJ availability scraper for night-train-monitor.

Scans SJ night train routes with iterative binary search tier probing.

Each price tier boundary is found exactly via binary search over passenger
count (n). One POST /search per n returns all classes for both directions,
so the algorithm collects the superset of needed ns across all classes
per round, probes them, and narrows per-class intervals until convergence.

Worst case: 4 rounds (n=1, 9, 5, 3/7, 2/4/6/8) = 5 distinct n-values.
Most classes converge in 2-3 rounds (no jump or jump found early).

Optimizations:
- SJ_NT service type filter: only night trains returned
- Return journey: 2 dates + 2 directions per POST /search
- PATCH reuses session for date changes (not passenger changes)

Note: PATCH /search does NOT change passenger count — only date, route, and
filters. Each passenger count requires a fresh POST /search.

Usage:
    python sj_availability.py 740000001 740000003 --days 120 -q -o data/sj/
    # → data/sj/YYYYMMDD_stockholm-malmoe.json + YYYYMMDD_malmoe-stockholm.json
"""

import argparse
import json
import sys
import time
import http.client
import ssl
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "https://prod-api.adp.sj.se"
PATH_PREFIX = "/public/sales/booking/v3"
# Public client key of the SJ /public/ sales API, embedded in the SJ web app
# source (not a secret).
API_KEY = "d6625619def348d38be070027fd24ff6"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

NT_FILTER = {"onlyDirectJourneys": False, "allowedServiceTypes": ["SJ_NT"]}

# Max passengers to probe. SJ API has no hard cap per booking type (verified
# 2026-09-07: n=20 and n=40 both return prices; classes drop out only when the
# request exceeds the class's total contingent). A larger window makes absolute
# contingent sizes of the SHARED classes measurable — a class that disappears
# between n and n+1 has that many total places. Cost stays low: the binary search
# is logarithmic, so raising the ceiling from 9 to 40 adds only ~2 probes per
# date that has a jump (dates without a jump still cost just n=1 + n=MAX_N).
MAX_N = 40

# Station name mapping for output filenames
STATION_NAMES = {
    "740000001": "stockholm", "740000003": "malmoe", "740000308": "duved",
    "740000144": "umea", "740000190": "lulea", "740000115": "are",
    "740000002": "goeteborg", "740000080": "halmstad", "740000120": "lund",
}

SEAT_CLASSES = ["SECOND", "SECOND_CALM", "FIRST"]
FLEX_TIERS = ["NOFLEX", "SEMIFLEX", "FULLFLEX"]
BED_CATEGORIES = ["COUCHETTE", "SLEEPER"]
COMFORT_TYPES = [
    "COUCHETTE_SHARED", "COUCHETTE_PRIVATE",
    "SLEEPER_SECOND_SHARED", "SLEEPER_SECOND_PRIVATE",
    "SLEEPER_FIRST_PRIVATE", "SLEEPER_FIRST_PRIVATE_SOLO",
]

_api_calls = 0
_errors = 0
_conn = None


def _get_conn():
    """Get or create a persistent HTTPS connection (keep-alive)."""
    global _conn
    if _conn is None:
        ctx = ssl.create_default_context()
        _conn = http.client.HTTPSConnection("prod-api.adp.sj.se", timeout=30, context=ctx)
    return _conn


def api_request(method, path, body=None):
    """Make API request with keep-alive connection. Reconnects on failure."""
    global _api_calls, _conn
    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Connection": "keep-alive",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    full_path = PATH_PREFIX + path
    for attempt in range(2):
        try:
            conn = _get_conn()
            conn.request(method, full_path, body=data, headers=headers)
            resp = conn.getresponse()
            _api_calls += 1
            resp_body = resp.read().decode("utf-8")
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} on {method} {path}: {resp_body[:500]}")
            return json.loads(resp_body)
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            # Connection dropped — reconnect and retry once
            _conn = None
            if attempt == 0:
                continue
            raise


def search_pair(origin, destination, date_out, date_ret, num_passengers):
    """POST /search with return journey and SJ_NT filter.

    Returns (out_search_id, ret_search_id, pax_list_id) or raises.
    """
    body = {
        "origin": origin,
        "destination": destination,
        "departureDate": date_out,
        "passengers": [{"passengerCategory": {"type": "ADULT"}}] * num_passengers,
        "outboundAdditionalSearchFilters": NT_FILTER,
    }
    if date_ret:
        body["returnDate"] = date_ret
        body["inboundAdditionalSearchFilters"] = NT_FILTER

    time.sleep(0.05)
    session = api_request("POST", "/search", body)
    return (
        session["departureSearchId"],
        session.get("returnDepartureSearchId"),
        session["passengerListId"],
    )


def fetch_night_offers(search_id, pax_list_id):
    """GET departures + offers for all night trains found.

    Returns list of (departure_dict, offers_dict, dep_datetime).
    """
    time.sleep(0.05)
    dep_resp = api_request("GET", f"/departures/search/{search_id}")

    results = []
    for travel in dep_resp.get("travels", []):
        for dep in travel.get("departures", []):
            dep_id = dep.get("departureId")
            if not dep_id:
                continue
            dep_dt = dep.get("departureDateTime", "")
            time.sleep(0.05)
            try:
                offers = api_request(
                    "GET",
                    f"/departures/{dep_id}/offers?passengerListId={pax_list_id}",
                )
            except Exception:
                offers = None
            results.append((dep, offers, dep_dt))
    return results


def extract_prices(offers_resp, n):
    """Extract total journey prices. Returns {product_key: total_price_or_None}.

    We store totals (not per-person) so that tier boundary detection works
    correctly and next_tier_price can be derived as the marginal cost.
    Per-person price for output = total // n (at n=1, total == per-person).
    """
    prices = {}
    if not offers_resp:
        return prices

    seat_offers = offers_resp.get("seatOffers", {}).get("offers", {})
    for cls in SEAT_CLASSES:
        flexes = seat_offers.get(cls, {}).get("flexibilities", {})
        for flex in FLEX_TIERS:
            key = f"seat:{cls}:{flex}"
            offer = flexes.get(flex)
            if offer and offer.get("available"):
                amt = offer.get("journeyPrices", {}).get("price", {}).get("amount")
                prices[key] = int(amt) if amt is not None else None
            else:
                prices[key] = None

    bed_offers = offers_resp.get("bedOffers", {}).get("offers", {})
    for ct in COMFORT_TYPES:
        for cat in BED_CATEGORIES:
            ct_data = bed_offers.get(cat, {}).get("comfortTypes", {}).get(ct, {})
            if ct_data:
                flexes = ct_data.get("flexibilities", {})
                for flex in FLEX_TIERS:
                    key = f"bed:{ct}:{flex}"
                    offer = flexes.get(flex)
                    if offer and offer.get("available"):
                        amt = offer.get("journeyPrices", {}).get("price", {}).get("amount")
                        prices[key] = int(amt) if amt is not None else None
                    else:
                        prices[key] = None
                break
        else:
            for flex in FLEX_TIERS:
                prices[f"bed:{ct}:{flex}"] = None

    return prices


def search_and_extract(origin, destination, date_out, date_ret, n):
    """Search with n passengers, return (out_raw, ret_raw, out_prices, ret_prices).

    out_prices/ret_prices: {dep_datetime: {product_key: price} or None (sold out)}
    out_raw/ret_raw: [(dep_dict, offers_dict, dep_dt)] from fetch_night_offers
    """
    out_search, ret_search, pax_id = search_pair(
        origin, destination, date_out, date_ret, n
    )

    out_prices = {}
    out_raw = fetch_night_offers(out_search, pax_id)
    for dep, offers, dep_dt in out_raw:
        if offers and offers.get("departureStatus") != "SOLD_OUT":
            out_prices[dep_dt] = extract_prices(offers, n)
        elif offers and offers.get("departureStatus") == "SOLD_OUT":
            out_prices[dep_dt] = None
        # else: no offers at all

    ret_prices = {}
    ret_raw = []
    if ret_search:
        ret_raw = fetch_night_offers(ret_search, pax_id)
        for dep, offers, dep_dt in ret_raw:
            if offers and offers.get("departureStatus") != "SOLD_OUT":
                ret_prices[dep_dt] = extract_prices(offers, n)
            elif offers and offers.get("departureStatus") == "SOLD_OUT":
                ret_prices[dep_dt] = None

    return out_raw, ret_raw, out_prices, ret_prices, n


def build_tier_result(totals_n1, all_probes, probed_ns):
    """Build tier result from binary search probes.

    Args:
        totals_n1: {product_key: total_price} at n=1 (= per-person baseline)
        all_probes: {n: {product_key: total_price} or None} for all probed ns > 1
        probed_ns: sorted list of all ns that were probed (including 1)

    Returns:
        {product_key: {"price": int, "tier_jump_at": int|None, "next_tier_price": int|None}}

    price = per-person price at n=1 (baseline tier)
    tier_jump_at = exact n where the price tier changes (or None)
    next_tier_price = per-person price in the next tier (marginal cost at jump point)
    """
    result = {}
    for key in totals_n1:
        baseline = totals_n1[key]  # total at n=1 = per-person price
        if baseline is None:
            result[key] = {"price": None, "tier_jump_at": None, "next_tier_price": None}
            continue

        # tier_jump_at and next_tier_price will be set by interval refinement later.
        # Here we just do a preliminary scan for sold-out detection.
        jump_at = None
        next_price = None

        for n in sorted(all_probes.keys()):
            pd = all_probes[n]
            if pd is None:
                jump_at = n
                break
            pn = pd.get(key)
            if pn is None:
                jump_at = n
                break
            # Compare total at n with n * baseline (no-jump expectation)
            if pn != baseline * n:
                jump_at = n
                # Marginal cost: total@n - total@(n-1)
                # We need total@(n-1). If n-1 is in probes, use it; else assume baseline*(n-1)
                prev_total = all_probes.get(n - 1, {})
                if isinstance(prev_total, dict):
                    prev_total = prev_total.get(key)
                if prev_total is None:
                    prev_total = baseline * (n - 1)
                next_price = pn - prev_total
                break

        result[key] = {"price": baseline, "tier_jump_at": jump_at, "next_tier_price": next_price}
    return result


def format_departure(dep_dict, tier_result, probed_ns):
    """Format a single departure entry for the output JSON."""
    dep_dt = dep_dict.get("departureDateTime", "")
    legs = dep_dict.get("legs", [])
    service = legs[0].get("serviceName", "") if legs else ""

    seats = {}
    beds = {}
    for key, info in tier_result.items():
        if info["price"] is None:
            continue
        kind, category, flex = key.split(":")
        target = seats if kind == "seat" else beds
        target.setdefault(category, {})[flex] = info

    status = ["AVAILABLE"] if (seats or beds) else ["NO_OFFERS"]
    return {
        "departureDateTime": dep_dt,
        "serviceName": service,
        "nightTrain": True,
        "seats": seats,
        "beds": beds,
        "probed_ns": probed_ns,
        "status": status,
    }


def scan_date_pair(origin, destination, date_out, date_ret, quiet):
    """Scan a date pair with iterative binary search.

    Strategy:
    1. Probe n=1 (baseline) and n=MAX_N (ceiling) — always.
    2. Per (departure, product_key), maintain a binary search interval [low, high].
       - low: largest n where price == baseline
       - high: smallest n where price != baseline (or MAX_N+1 if no jump)
    3. Each round: collect union of all mid-points needed, probe them.
    4. Repeat until all intervals have high - low <= 1.

    Each probe level costs ~5 API calls (1 POST + 2 GET deps + 2 GET offers).
    Max rounds: ceil(log2(MAX_N)) + 1 = 6-7 rounds for MAX_N=40 (only for dates
    that actually have a jump; no-jump dates converge after the n=MAX_N ceiling probe).
    """
    global _errors

    # Step 1: Probe n=1 (baseline)
    try:
        out_raw_1, ret_raw_1, out_p1, ret_p1, _ = search_and_extract(
            origin, destination, date_out, date_ret, 1
        )
    except Exception as e:
        _errors += 1
        err = {"info": f"error: {e}"}
        return err, err

    if not out_raw_1 and not ret_raw_1:
        no_dep = {"info": "no night train departures"}
        return no_dep, no_dep if date_ret else None

    # Merge both directions for unified probing
    # all_p1: {dep_dt: {key: price}} for all departures in both directions
    all_p1 = {}
    all_p1.update(out_p1)
    all_p1.update(ret_p1)

    # Step 2: Probe n=MAX_N (ceiling)
    all_probes = {}  # n -> {dep_dt: {key: total_price} or None}
    try:
        _, _, out_pmax, ret_pmax, _ = search_and_extract(
            origin, destination, date_out, date_ret, MAX_N
        )
        all_probes[MAX_N] = {**out_pmax, **ret_pmax}
    except Exception:
        _errors += 1
        all_probes[MAX_N] = {}

    # Initialize binary search intervals per (dep_dt, key)
    # intervals[dep_dt][key] = (low, high)
    #   low = largest probed n where price == baseline (starts at 1)
    #   high = smallest probed n where price != baseline (starts at MAX_N or MAX_N+1)
    intervals = {}
    probed_set = {1, MAX_N}

    for dep_dt, p1 in all_p1.items():
        if p1 is None:
            continue  # sold out at n=1
        intervals[dep_dt] = {}
        pmax_dict = all_probes[MAX_N].get(dep_dt)

        for key, baseline in p1.items():
            if baseline is None:
                continue

            if pmax_dict is None:
                # Sold out at MAX_N
                intervals[dep_dt][key] = (1, MAX_N)
            else:
                total_at_max = pmax_dict.get(key)
                if total_at_max is None:
                    # This class sold out at MAX_N
                    intervals[dep_dt][key] = (1, MAX_N)
                elif total_at_max != baseline * MAX_N:
                    # Jump somewhere in 2..MAX_N
                    intervals[dep_dt][key] = (1, MAX_N)
                else:
                    # No jump — at least MAX_N places remain
                    intervals[dep_dt][key] = (1, MAX_N + 1)  # converged: no jump

    # Step 3: Iterative binary search
    max_rounds = 10  # safety cap
    for _ in range(max_rounds):
        # Collect all mid-points needed across all (dep_dt, key) intervals
        needed_ns = set()
        for dep_dt, keys in intervals.items():
            for key, (low, high) in keys.items():
                if high - low <= 1:
                    continue  # converged
                mid = (low + high) // 2
                needed_ns.add(mid)

        if not needed_ns:
            break  # all converged

        # Probe all needed ns
        for n in sorted(needed_ns):
            if n in probed_set:
                continue
            try:
                _, _, out_pn, ret_pn, _ = search_and_extract(
                    origin, destination, date_out, date_ret, n
                )
                all_probes[n] = {**out_pn, **ret_pn}
            except Exception:
                _errors += 1
                all_probes[n] = {}
            probed_set.add(n)

        # Narrow intervals based on new probe results
        for dep_dt, keys in intervals.items():
            p1 = all_p1[dep_dt]
            if p1 is None:
                continue

            for key in list(keys.keys()):
                low, high = keys[key]
                if high - low <= 1:
                    continue

                baseline = p1[key]  # total at n=1 = per-person price
                mid = (low + high) // 2

                probe_data = all_probes.get(mid, {}).get(dep_dt)
                if probe_data is None:
                    # Sold out at mid
                    keys[key] = (low, mid)
                else:
                    total_at_mid = probe_data.get(key)
                    if total_at_mid is None:
                        # This class sold out at mid
                        keys[key] = (low, mid)
                    elif total_at_mid != baseline * mid:
                        # Jump at or before mid
                        keys[key] = (low, mid)
                    else:
                        # No jump at mid — jump is above mid
                        keys[key] = (mid, high)

    # Step 4: Assemble results
    all_probed_ns = sorted(probed_set)

    def assemble_direction(raw_list, p1_map):
        """Build departure entries for one direction."""
        departures = []
        for dep, offers, dep_dt in raw_list:
            prices_n1 = p1_map.get(dep_dt)

            # Determine status
            if prices_n1 is None:
                svc = dep.get("legs", [{}])[0].get("serviceName", "") if dep.get("legs") else ""
                status = "SOLD_OUT" if dep_dt in p1_map else "NO_OFFERS"
                departures.append({
                    "departureDateTime": dep_dt, "serviceName": svc,
                    "nightTrain": True, "seats": {}, "beds": {},
                    "probed_ns": [1], "status": [status],
                })
                continue

            if not any(v is not None for v in prices_n1.values()):
                svc = dep.get("legs", [{}])[0].get("serviceName", "") if dep.get("legs") else ""
                departures.append({
                    "departureDateTime": dep_dt, "serviceName": svc,
                    "nightTrain": True, "seats": {}, "beds": {},
                    "probed_ns": [1], "status": ["NO_OFFERS"],
                })
                continue

            # Build probes dict for this departure (only ns that have data for this dep_dt)
            dep_probes = {}
            dep_probed = [1]
            for n in sorted(all_probes.keys()):
                probe_for_dt = all_probes[n].get(dep_dt)
                # Include if we have data OR if the departure was probed (sold out = None)
                if dep_dt in all_probes[n] or probe_for_dt is not None:
                    dep_probes[n] = probe_for_dt
                    dep_probed.append(n)

            # Override tier_jump_at with exact values from binary search
            tier_result = build_tier_result(prices_n1, dep_probes, sorted(set(dep_probed)))

            # Refine tier_jump_at using converged intervals
            dep_intervals = intervals.get(dep_dt, {})
            for key, info in tier_result.items():
                if info["price"] is None:
                    continue
                iv = dep_intervals.get(key)
                if iv is None:
                    continue
                low, high = iv
                baseline = prices_n1[key]  # total at n=1 = per-person price
                if high > MAX_N:
                    # No jump found
                    info["tier_jump_at"] = None
                    info["next_tier_price"] = None
                elif high - low <= 1:
                    # Exact: jump is at high
                    info["tier_jump_at"] = high
                    # Compute next_tier_price as marginal cost:
                    # total@high - total@(high-1), where total@(high-1) = baseline * (high-1)
                    probe_at_high = all_probes.get(high, {}).get(dep_dt)
                    if probe_at_high is not None:
                        total_at_high = probe_at_high.get(key)
                        if total_at_high is not None:
                            # Use actual total@(high-1) if probed, else derive from baseline
                            prev_probe = all_probes.get(high - 1, {})
                            if isinstance(prev_probe, dict):
                                prev_total = prev_probe.get(dep_dt, {})
                                if isinstance(prev_total, dict):
                                    prev_total = prev_total.get(key)
                                else:
                                    prev_total = None
                            else:
                                prev_total = None
                            if prev_total is None:
                                prev_total = baseline * (high - 1)
                            info["next_tier_price"] = total_at_high - prev_total
                        else:
                            info["next_tier_price"] = None  # sold out at boundary
                    else:
                        info["next_tier_price"] = None  # sold out at boundary

            entry = format_departure(dep, tier_result, sorted(set(dep_probed)))
            departures.append(entry)

        return {"departures": departures} if departures else {"info": "no night train departures"}

    out_data = assemble_direction(out_raw_1, out_p1)
    ret_data = assemble_direction(ret_raw_1, ret_p1) if date_ret else None

    return out_data, ret_data


def station_name(code):
    """Resolve station code to short name for filenames."""
    return STATION_NAMES.get(code, code)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="SJ night train availability scraper with binary search tier probing"
    )
    parser.add_argument("origin", help="Origin station UIC code (e.g. 740000001)")
    parser.add_argument("destination", help="Destination station UIC code (e.g. 740000003)")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output directory (default: data/sj/ relative to project)")
    args = parser.parse_args()

    origin = args.origin
    destination = args.destination
    out_name = f"{station_name(origin)}-{station_name(destination)}"
    ret_name = f"{station_name(destination)}-{station_name(origin)}"

    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = Path(__file__).resolve().parent.parent / "data" / "sj"
    out_dir.mkdir(parents=True, exist_ok=True)

    start_date = datetime.now().date() + timedelta(days=1)
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]

    if not args.quiet:
        print(f"SJ scraper: {out_name} + {ret_name}, {args.days} days from {start_date}")

    global _api_calls, _errors
    _api_calls = 0
    _errors = 0
    t0 = time.time()

    def count_jumps(data):
        c = 0
        for dep in data.get("departures", []):
            for cls_data in list(dep.get("seats", {}).values()) + list(dep.get("beds", {}).values()):
                for flex_data in cls_data.values():
                    if flex_data.get("tier_jump_at"):
                        c += 1
        return c

    all_out = {}
    all_ret = {}

    for date_str in dates:
        if not args.quiet:
            print(f"  {date_str}", end="", flush=True)

        out_data, ret_data = scan_date_pair(
            origin, destination, date_str, date_str, args.quiet
        )

        all_out[date_str] = out_data
        if ret_data:
            all_ret[date_str] = ret_data

        if not args.quiet:
            oj = count_jumps(out_data)
            rj = count_jumps(ret_data) if ret_data else 0
            out_info = out_data.get("info", "")
            ret_info = ret_data.get("info", "") if ret_data else ""

            parts = []
            if out_info:
                parts.append(f"out:{out_info}")
            elif oj:
                parts.append(f"out:{oj}j")
            else:
                parts.append("out:\u2713")

            if ret_info:
                parts.append(f"ret:{ret_info}")
            elif rj:
                parts.append(f"ret:{rj}j")
            else:
                parts.append("ret:\u2713")

            print(f" {' '.join(parts)}")

    today_prefix = datetime.now().strftime("%Y%m%d")

    fp_out = out_dir / f"{today_prefix}_{out_name}.json"
    with open(fp_out, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(all_out.items())), f, indent=2, ensure_ascii=False)

    fp_ret = out_dir / f"{today_prefix}_{ret_name}.json"
    with open(fp_ret, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(all_ret.items())), f, indent=2, ensure_ascii=False)

    if not args.quiet:
        print(f"\n  \u2192 {fp_out.name}, {fp_ret.name}")

    elapsed = time.time() - t0
    if not args.quiet:
        print(f"Done. {_api_calls} API calls in {elapsed:.0f}s. Errors: {_errors}")

    return 0 if _errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
