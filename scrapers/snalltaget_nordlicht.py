#!/usr/bin/env python3
"""
Snälltåget Nordlicht scraper — Malmö ↔ Narvik (Arctic Circle night train).

Captures pricing/availability for Zug 20 (23 Nov) and Zug 21 (27 Nov 2026).
Two searchjourney calls:
  1. With oppositedate → return-trip prices (20% discount on compartments)
  2. Without oppositedate → single-trip prices (full price)

Output format matches the regular snalltaget scraper (date-keyed dict),
with an additional "direct_single" key for single-trip pricing.

Narvik = UIC 760002402.

Usage:
    python3 scrapers/snalltaget_nordlicht.py [-q] [-o DIR]

Output: YYYYMMDD_malmoe-narvik.json, YYYYMMDD_narvik-malmoe.json
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from snalltaget_common import get_token, fetch_calendar, fetch_searchjourney

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "data" / "snalltaget"

NARVIK = "760002402"
MALMOE = "Malmö C"

# Fixed dates for the Nordlicht train
OUTBOUND_DATE = "2026-11-23"  # Zug 20: Malmö C → Narvik
INBOUND_DATE = "2026-11-27"   # Zug 21: Narvik → Malmö C

# Service names (train numbers)
SVC_OUTBOUND = "20"
SVC_INBOUND = "21"


def extract_bundles(offer, service_name):
    """Extract bundle data for a specific service from searchjourney response."""
    for travel in offer.get("travels", []):
        for route in travel.get("routes", []):
            legs = route.get("legs", [])
            for leg in legs:
                if leg.get("serviceName") == service_name:
                    bundles = [
                        {"productFamilyId": b.get("productFamilyId"),
                         "price": b.get("price"),
                         "originalPrice": b.get("originalPrice")}
                        for b in route.get("bundles", [])
                    ]
                    return {
                        "serviceIdentifier": leg.get("serviceIdentifier"),
                        "bundles": bundles,
                    }
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Snälltåget Nordlicht train (Malmö ↔ Narvik)")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("-o", "--output-dir", default=str(DATA_DIR))
    args = parser.parse_args()

    today = datetime.now().date()
    date_prefix = today.strftime("%Y%m%d")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"[{datetime.now().isoformat()}] Snälltåget Nordlicht (Malmö ↔ Narvik)")

    token = get_token()

    # --- Calendar outbound: Malmö → Narvik ---
    cal_out = None
    try:
        data = fetch_calendar(token, MALMOE, NARVIK, "outbound",
                              OUTBOUND_DATE, OUTBOUND_DATE)
        cal_out = data.get("calendar", {}).get(OUTBOUND_DATE)
    except Exception as e:
        if not args.quiet:
            print(f"  Calendar outbound error: {e}")

    time.sleep(0.3)

    # --- Calendar inbound: Narvik → Malmö ---
    cal_in = None
    try:
        data = fetch_calendar(token, NARVIK, MALMOE, "inbound",
                              INBOUND_DATE, INBOUND_DATE)
        cal_in = data.get("calendar", {}).get(INBOUND_DATE)
    except Exception as e:
        if not args.quiet:
            print(f"  Calendar inbound error: {e}")

    time.sleep(0.3)

    # --- SearchJourney WITH oppositedate (return-trip, 20% discount) ---
    return_out = None
    return_in = None
    try:
        result = fetch_searchjourney(token, MALMOE, NARVIK, OUTBOUND_DATE,
                                     oppositedate=INBOUND_DATE)
        offer = result.get("offer", {})
        return_out = extract_bundles(offer, SVC_OUTBOUND)
        return_in = extract_bundles(offer, SVC_INBOUND)
    except Exception as e:
        if not args.quiet:
            print(f"  SearchJourney return-trip error: {e}")

    time.sleep(0.3)

    # --- SearchJourney WITHOUT oppositedate (single-trip, full price) ---
    single_out = None
    try:
        result = fetch_searchjourney(token, MALMOE, NARVIK, OUTBOUND_DATE)
        offer = result.get("offer", {})
        single_out = extract_bundles(offer, SVC_OUTBOUND)
    except Exception as e:
        if not args.quiet:
            print(f"  SearchJourney single outbound error: {e}")

    time.sleep(0.3)

    single_in = None
    try:
        result = fetch_searchjourney(token, NARVIK, MALMOE, INBOUND_DATE)
        offer = result.get("offer", {})
        single_in = extract_bundles(offer, SVC_INBOUND)
    except Exception as e:
        if not args.quiet:
            print(f"  SearchJourney single inbound error: {e}")

    # --- Build outbound file ---
    outbound_data = {}
    entry = {}
    if cal_out:
        entry["calendar"] = cal_out
    if return_out:
        entry["direct"] = return_out
    if single_out:
        entry["direct_single"] = single_out
    if entry:
        outbound_data[OUTBOUND_DATE] = entry

    out_file = out_dir / f"{date_prefix}_malmoe-narvik.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(outbound_data, f, indent=2, ensure_ascii=False)

    if not args.quiet:
        if return_out:
            prices = [b["price"] for b in return_out["bundles"]]
            print(f"  malmoe-narvik (return): {len(return_out['bundles'])} bundles, "
                  f"lowest {min(prices)} SEK, cap={cal_out.get('capacity') if cal_out else '?'}")
        if single_out:
            prices = [b["price"] for b in single_out["bundles"]]
            print(f"  malmoe-narvik (single): {len(single_out['bundles'])} bundles, "
                  f"lowest {min(prices)} SEK")
        if not return_out and not single_out:
            print(f"  malmoe-narvik: no data")

    # --- Build inbound file ---
    inbound_data = {}
    entry = {}
    if cal_in:
        entry["calendar"] = cal_in
    if return_in:
        entry["direct"] = return_in
    if single_in:
        entry["direct_single"] = single_in
    if entry:
        inbound_data[INBOUND_DATE] = entry

    in_file = out_dir / f"{date_prefix}_narvik-malmoe.json"
    with open(in_file, "w", encoding="utf-8") as f:
        json.dump(inbound_data, f, indent=2, ensure_ascii=False)

    if not args.quiet:
        if return_in:
            prices = [b["price"] for b in return_in["bundles"]]
            print(f"  narvik-malmoe (return): {len(return_in['bundles'])} bundles, "
                  f"lowest {min(prices)} SEK, cap={cal_in.get('capacity') if cal_in else '?'}")
        if single_in:
            prices = [b["price"] for b in single_in["bundles"]]
            print(f"  narvik-malmoe (single): {len(single_in['bundles'])} bundles, "
                  f"lowest {min(prices)} SEK")
        if not return_in and not single_in:
            print(f"  narvik-malmoe: no data")

    return 0


if __name__ == "__main__":
    sys.exit(main())
