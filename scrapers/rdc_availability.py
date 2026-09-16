#!/usr/bin/env python3
"""
RDC EuroNight availability scraper — daily price snapshot with tier scanning.

GraphQL API at tickets.rdc-deutschland.de/booking (no auth required).
Fetches all bookable connections, then prices per entity type (Sitz/Liege/Bett)
for both single and cabin (Privatabteil) booking modes.

Tier scanning reveals remaining places in the current price tier by probing
AmountAdults=2..cap. A price jump at n=k means (k-1) places remain at the
current tier. This is the primary demand signal.

Optimized batching strategy per connection:
1. Batch all entity types at n=1 (baseline) — 1 request per booking mode
2. Batch all entity types at n=cap (ceiling) — 1 request per booking mode
3. Only if tier jump detected between n=1 and n=cap: scan n=2..cap-1 individually

Marks dates without service as {"info": "no service"} for consistency with
other scrapers (Leo Express, European Sleeper).

Usage:
    python3 rdc_availability.py 5 57 -q -o data/rdc
    # → data/rdc/YYYYMMDD_hamburg-stockholm.json

Options:
    DEP ARR     RDC station IDs (5=Hamburg, 57=Stockholm, 68=Berlin Lbg)
    -q          Quiet mode (suppress stdout)
    -o DIR      Output directory (default: data/rdc/)
    --days N    Fill no-service markers for N days ahead (default: 120)
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import http.client
import ssl

ENDPOINT = "https://tickets.rdc-deutschland.de/booking"
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "data" / "rdc"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/graphql-response+json, application/json",
    "NEX-Language": "de",
    "Origin": "https://www.nachtexpress.de",
    "Referer": "https://www.nachtexpress.de/",
    "x-booking-url": "https://www.nachtexpress.de/de/buchen/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}

# Per-booking caps (max places per single API request).
# Hardcoded from observed API behavior — identical across all connections/routes.
# Station name mapping for output filenames
STATION_NAMES = {
    5: "hamburg", 57: "stockholm", 68: "berlin-lichtenberg",
    67: "berlin-gesundbrunnen", 58: "norrkoping", 59: "linkoping",
    60: "naessjo", 61: "alvesta", 62: "haessleholm", 64: "lund",
    65: "koebenhavn-airport", 66: "padborg", 70: "moelndals-nedre",
}

ENTITY_CAPS = {
    "Z5RRRzb1J4": {"single": 5},                        # Sitz (no cabin option)
    "BKVpAEyGbm": {"single": 6, "cabin": 6},            # Liege
    "mkkJKnMnWm": {"single": 2, "cabin": 2},            # Bett
    "mdoeXD6Lj4": {"cabin": 3},                          # Bett 1. Klasse (cabin only)
}


_conn = None


def _get_conn():
    """Get or create persistent HTTPS connection to RDC."""
    global _conn
    if _conn is None:
        ctx = ssl.create_default_context()
        _conn = http.client.HTTPSConnection("tickets.rdc-deutschland.de", timeout=30, context=ctx)
    return _conn


def graphql(query, variables=None):
    global _conn
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {**HEADERS, "Connection": "keep-alive"}
    for attempt in range(2):
        try:
            conn = _get_conn()
            conn.request("POST", "/booking", body=body, headers=headers)
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            if "errors" in data and data.get("data") is None:
                raise Exception(f"GraphQL error: {data['errors'][0]['message']}")
            return data.get("data", {})
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            _conn = None
            if attempt == 0:
                continue
            raise


def get_train_connections(dep_id, arr_id):
    query = """query ReadTrainConnections($DepartureStationID: Int!, $ArrivalStationID: Int!, $VehiclesEnabled: Boolean!) {
  readTrainConnections(DepartureStationID: $DepartureStationID, ArrivalStationID: $ArrivalStationID, VehiclesEnabled: $VehiclesEnabled) {
    HashID StartDate DepartureNextDay UnreliableTimeSchedule
  }
}"""
    data = graphql(query, {"DepartureStationID": dep_id, "ArrivalStationID": arr_id, "VehiclesEnabled": False})
    return data.get("readTrainConnections", [])


def get_entity_types(hash_id):
    query = """query ReadEntityTypes($TrainConnectionHashID: ID!) {
  readEntityTypes(TrainConnectionHashID: $TrainConnectionHashID) {
    ID Title InfoPreview BookingOptions { Code Title }
  }
}"""
    data = graphql(query, {"TrainConnectionHashID": hash_id})
    return data.get("readEntityTypes", [])


PRICE_QUERY = """query ReadPriceCategories($input: PriceCategoryInput!) {
  readPriceCategories(input: $input) {
    RequestID
    PriceCategories { ID Title SubTitle Price { Amount Currency } SinglePrice { Amount Currency } }
  }
}"""


def get_prices_batch(dep_id, arr_id, hash_id, entity_requests, entity_type_ids):
    """Fetch prices for multiple entity requests in one API call."""
    variables = {"input": {
        "ArrivalStationID": arr_id, "ConsiderExpiryDate": True,
        "DepartureStationID": dep_id,
        "EntityRequests": entity_requests,
        "EntityTypeHashIDs": entity_type_ids,
        "TrainConnectionHashID": hash_id, "Vehicles": [],
    }}
    data = graphql(PRICE_QUERY, variables)
    return data.get("readPriceCategories", [])


def make_entity_request(entity_id, is_cabin, amount):
    """Create a single EntityRequest dict."""
    return {
        "AddOns": [], "AmountAdults": amount, "AmountBaby": 0, "AmountChildren": 0,
        "AmountSeniors": 0, "AmountStudents": 0, "CollectionTag": None,
        "ExpectedPrice": None, "IsCabinBooking": is_cabin, "Passes": [],
        "PriceCategory": None, "RequestID": str(uuid.uuid4()), "Type": entity_id,
    }


def extract_normal_single_price(price_categories):
    """Extract Normalpreis SinglePrice from a PriceCategories list."""
    for cat in (price_categories or []):
        if cat["ID"] == "35":
            return cat["SinglePrice"]["Amount"]
    return None


def scan_tiers_for_entity(dep_id, arr_id, hash_id, entity_id, is_cabin, cap, baseline_price):
    """Full tier scan for one entity. Finds where the price jumps within n=1..cap.

    Returns:
        tiers: list of {"tier_jump_at": n, "next_tier_price": price} for each tier boundary
        requests_made: number of API calls used
    """
    if cap <= 1 or baseline_price is None:
        return [], 0

    requests_made = 0

    # First check price at n=cap
    er_cap = make_entity_request(entity_id, is_cabin, cap)
    results = get_prices_batch(dep_id, arr_id, hash_id, [er_cap], [entity_id])
    requests_made += 1
    time.sleep(0.05)

    cap_price = None
    if results and results[0].get("PriceCategories"):
        cap_price = extract_normal_single_price(results[0]["PriceCategories"])

    # No jump (same price at n=1 and n=cap) → at least `cap` places remain in tier
    if cap_price is not None and cap_price == baseline_price:
        return [], requests_made

    # Sold out at cap or price jumped → scan n=2..cap-1 to find exact boundary
    tiers = []
    prev_price = baseline_price
    for n in range(2, cap + 1):
        if n == cap and cap_price is not None:
            # Already know the answer
            if cap_price != prev_price:
                tiers.append({"tier_jump_at": n, "next_tier_price": cap_price})
            break

        er = make_entity_request(entity_id, is_cabin, n)
        res = get_prices_batch(dep_id, arr_id, hash_id, [er], [entity_id])
        requests_made += 1
        time.sleep(0.05)

        if not res or not res[0].get("PriceCategories"):
            # Sold out at this n — boundary is at n
            tiers.append({"tier_jump_at": n, "next_tier_price": None, "sold_out_at": n})
            break

        price_at_n = extract_normal_single_price(res[0]["PriceCategories"])
        if price_at_n != prev_price:
            tiers.append({"tier_jump_at": n, "next_tier_price": price_at_n})
            prev_price = price_at_n
            # Only one tier jump expected within cap — stop scanning
            break

    return tiers, requests_made


def generate_date_range(today, days_ahead):
    """Generate all dates from today to today+days_ahead."""
    return [(today + timedelta(days=i)).isoformat() for i in range(days_ahead)]


def scrape_route(dep_id, arr_id, label, out_dir, date_prefix, days_ahead, quiet=False):
    """Scrape one route: connections → batched prices + tier scan."""
    route_errors = 0
    total_requests = 0
    today = datetime.now().date()

    try:
        connections = get_train_connections(dep_id, arr_id)
        total_requests += 1
    except Exception as e:
        if not quiet:
            print(f"  {label}: ERROR getting connections: {e}")
        return 0, 1

    # Entity types (same for all connections on a route)
    entities = []
    if connections:
        try:
            entities = get_entity_types(connections[0]["HashID"])
            total_requests += 1
        except Exception as e:
            if not quiet:
                print(f"  {label}: ERROR getting entity types: {e}")
            route_errors += 1

    # Determine single vs cabin entities
    single_entities = []
    cabin_entities = []
    for e in entities:
        options = [bo["Code"] for bo in e.get("BookingOptions", [])]
        if "Single" in options:
            single_entities.append(e)
        if "Cabin" in options:
            cabin_entities.append(e)

    # Collect dates with service
    service_dates = set()
    route_data = {}

    for conn in connections:
        hash_id = conn["HashID"]
        conn_date = conn["StartDate"]
        service_dates.add(conn_date)

        conn_data = {"hash_id": hash_id, "date": conn_date, "entities": []}

        # --- Step 1: Batch baseline (n=1) for single and cabin ---
        single_prices = {}
        if single_entities:
            reqs = []
            req_map = {}
            for ent in single_entities:
                er = make_entity_request(ent["ID"], False, 1)
                req_map[er["RequestID"]] = ent["ID"]
                reqs.append(er)
            try:
                results = get_prices_batch(dep_id, arr_id, hash_id, reqs, [e["ID"] for e in single_entities])
                total_requests += 1
                for res in results:
                    eid = req_map.get(res["RequestID"])
                    if eid:
                        single_prices[eid] = res.get("PriceCategories", [])
            except Exception as e:
                route_errors += 1
            time.sleep(0.05)

        cabin_prices = {}
        if cabin_entities:
            reqs = []
            req_map = {}
            for ent in cabin_entities:
                er = make_entity_request(ent["ID"], True, 1)
                req_map[er["RequestID"]] = ent["ID"]
                reqs.append(er)
            try:
                results = get_prices_batch(dep_id, arr_id, hash_id, reqs, [e["ID"] for e in cabin_entities])
                total_requests += 1
                for res in results:
                    eid = req_map.get(res["RequestID"])
                    if eid:
                        cabin_prices[eid] = res.get("PriceCategories", [])
            except Exception as e:
                route_errors += 1
            time.sleep(0.05)

        # --- Step 2: Tier scan for each entity/mode ---
        tier_data = {}  # (entity_id, mode) → tiers list
        for ent in entities:
            eid = ent["ID"]
            caps = ENTITY_CAPS.get(eid, {})

            # Single tier scan
            if "single" in caps and eid in single_prices and single_prices[eid]:
                baseline = extract_normal_single_price(single_prices[eid])
                if baseline is not None:
                    try:
                        tiers, reqs = scan_tiers_for_entity(
                            dep_id, arr_id, hash_id, eid, False, caps["single"], baseline
                        )
                        total_requests += reqs
                        if tiers:
                            tier_data[(eid, "single")] = tiers
                    except Exception:
                        route_errors += 1

            # Cabin tier scan
            if "cabin" in caps and eid in cabin_prices and cabin_prices[eid]:
                baseline = extract_normal_single_price(cabin_prices[eid])
                if baseline is not None:
                    try:
                        tiers, reqs = scan_tiers_for_entity(
                            dep_id, arr_id, hash_id, eid, True, caps["cabin"], baseline
                        )
                        total_requests += reqs
                        if tiers:
                            tier_data[(eid, "cabin")] = tiers
                    except Exception:
                        route_errors += 1

        # --- Assemble output per entity ---
        for ent in entities:
            eid = ent["ID"]
            entry = {"id": eid, "title": ent["Title"]}

            caps = ENTITY_CAPS.get(eid, {})

            if eid in single_prices:
                entry["single"] = single_prices[eid]
                t = tier_data.get((eid, "single"))
                if t:
                    entry["single_tiers"] = t
                if "single" in caps:
                    entry["single_probed_ns"] = list(range(1, caps["single"] + 1))

            if eid in cabin_prices:
                entry["cabin"] = cabin_prices[eid]
                t = tier_data.get((eid, "cabin"))
                if t:
                    entry["cabin_tiers"] = t
                if "cabin" in caps:
                    entry["cabin_probed_ns"] = list(range(1, caps["cabin"] + 1))

            conn_data["entities"].append(entry)

        route_data[conn_date] = conn_data
        time.sleep(0.1)

    # Fill no-service dates
    all_dates = generate_date_range(today, days_ahead)
    no_service_count = 0
    for d in all_dates:
        if d not in route_data:
            route_data[d] = {"info": "no service"}
            no_service_count += 1

    # Save
    out_file = out_dir / f"{date_prefix}_{label}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(route_data.items())), f, indent=2, ensure_ascii=False)

    if not quiet:
        n_conns = len(connections)
        n_tiers = sum(1 for v in tier_data.values() if v)
        print(f"  {label}: {n_conns} connections, {no_service_count} no-service, {n_tiers} tier jumps, {total_requests} requests → {out_file.name}")
    return total_requests, route_errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RDC EuroNight availability scraper with tier scanning")
    parser.add_argument("departure", type=int, help="Departure station ID (e.g. 5 for Hamburg)")
    parser.add_argument("arrival", type=int, help="Arrival station ID (e.g. 57 for Stockholm)")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-o", "--output-dir", default=str(DATA_DIR))
    parser.add_argument("--days", type=int, default=120, help="Days ahead for no-service markers")
    args = parser.parse_args()

    dep_name = STATION_NAMES.get(args.departure, str(args.departure))
    arr_name = STATION_NAMES.get(args.arrival, str(args.arrival))
    label = f"{dep_name}-{arr_name}"

    today = datetime.now().date()
    date_prefix = today.strftime("%Y%m%d")
    out_dir = Path(args.output_dir)

    if not args.quiet:
        print(f"[{datetime.now().isoformat()}] RDC EuroNight: {label}, {args.days} days")

    out_dir.mkdir(parents=True, exist_ok=True)

    reqs, errs = scrape_route(args.departure, args.arrival, label, out_dir, date_prefix, args.days, args.quiet)

    if not args.quiet:
        print(f"\n  Total: {reqs} requests. Errors: {errs}")

    return 0 if errs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
