#!/usr/bin/env python3
"""
Snälltåget Tier Probing PoC — Reserve → Measure → Cancel

Books a single seat on a far-future date (high capacity), checks if quota/price
change, then immediately cancels. No payment = no actual ticket.

Usage:
    python scrapers/snalltaget_tier_probe.py [--date 2026-11-20] [--origin Berlin] [--dry-run]

Default: picks a November date with high capacity on berlin-stockholm.
"""
import json
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://apiv2.snalltaget.se"
TOKEN_URL = "https://www.snalltaget.se/token/v2"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {
    "User-Agent": UA,
    "Origin": "https://www.snalltaget.se",
    "Referer": "https://www.snalltaget.se/",
    "Content-Type": "application/json",
}

# EVA numbers for booking (9-digit with leading 8000)
EVA = {
    'Berlin': '800010100',
    'Hamburg': '800062600',
    'Stockholm': '740000001',
    'Dresden': '800016305',
    'Malmö': '740000003',
}


def get_token():
    req = Request(TOKEN_URL, headers={"User-Agent": UA})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def api(token, method, path, body=None):
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    data = json.dumps(body).encode() if body else None
    if method == 'DELETE' and not data:
        data = b''  # DELETE with empty body
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"  HTTP {e.code}: {body[:500]}")
        return None


def search(token, origin, destination, date):
    return api(token, 'POST', '/orientation/searchjourney', {
        "origin": origin,
        "destination": destination,
        "departure": date,
        "passengers": [{"type": "AD"}],
        "travelWithpet": False,
    })


def get_calendar_entry(token, origin, destination, date):
    """Get calendar data for a specific month containing the date."""
    d = datetime.fromisoformat(date)
    begin = d.replace(day=1).strftime('%Y-%m-%d')
    if d.month == 12:
        end_d = d.replace(year=d.year + 1, month=1, day=1)
    else:
        end_d = d.replace(month=d.month + 1, day=1)
    from datetime import timedelta
    end = (end_d - timedelta(days=1)).strftime('%Y-%m-%d')

    result = api(token, 'POST', '/orientation/calendar', {
        "direction": "outbound",
        "origin": origin,
        "destination": destination,
        "begin": begin,
        "end": end,
        "passengers": ["AD"],
    })
    if result and 'calendar' in result:
        return result['calendar'].get(date)
    return None


def create_booking(token, origin_eva, dest_eva, departure_dt, service_name, service_id, tariff, count=1):
    passengers = [{"id": f"passenger_{i+1}", "type": "AD", "travelDocuments": []}
                  for i in range(count)]
    items = [{"passengerId": f"passenger_{i+1}", "tariffCode": tariff}
             for i in range(count)]
    return api(token, 'POST', '/booking', {
        "segments": [{
            "origin": origin_eva,
            "destination": dest_eva,
            "direction": "outbound",
            "departure": departure_dt,
            "serviceName": service_name,
            "serviceIdentifier": service_id,
            "items": items,
            "optionItems": [],
        }],
        "passengers": passengers,
    })


def cancel_booking(token, pnr):
    return api(token, 'POST', f'/booking/{pnr}/cancel', {})


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Snälltåget Tier Probing PoC')
    parser.add_argument('--date', default='2026-11-20', help='Travel date (YYYY-MM-DD)')
    parser.add_argument('--origin', default='Berlin', help='Origin station name')
    parser.add_argument('--destination', default='Stockholm', help='Destination (default: Stockholm)')
    parser.add_argument('--count', type=int, default=1, help='Number of seats to book')
    parser.add_argument('--dry-run', action='store_true', help='Only search, do not book')
    args = parser.parse_args()

    origin = args.origin
    dest = args.destination
    target_date = args.date

    origin_search = origin
    dest_search = EVA.get(dest, dest) if dest in EVA else dest

    print(f"\n{'='*70}")
    print(f"Snälltåget Tier Probe — {origin} → {dest} on {target_date}")
    print(f"{'='*70}\n")

    # Step 1: Get token
    token = get_token()
    print("✓ Token acquired\n")

    # Step 2: Check calendar BEFORE
    print("─── BEFORE booking ───")
    cal_before = get_calendar_entry(token, origin_search, dest_search, target_date)
    if not cal_before:
        print(f"  No calendar data for {target_date}. No service?")
        return
    print(f"  Calendar: amount={cal_before.get('amount')} SEK  "
          f"capacity={cal_before.get('capacity')}  quota={cal_before.get('quota')}")

    # Step 3: Search for trains to get service details
    result = search(token, origin_search, dest_search, target_date)
    if not result or 'offer' not in result:
        print("  No search results.")
        return

    # Find direct STNIGHT route
    service_id = None
    service_name = None
    departure_dt = None
    bundles_before = {}

    for travel in result['offer'].get('travels', []):
        for route in travel.get('routes', []):
            legs = route.get('legs', [])
            bundles = route.get('bundles', [])
            if len(legs) == 1 and 'STNIGHT' in legs[0].get('serviceIdentifier', ''):
                service_id = legs[0]['serviceIdentifier']
                service_name = service_id.split('|')[1] if '|' in service_id else ''
                departure_dt = legs[0].get('departure') or legs[0].get('departureTime')
                # Extract departure from serviceIdentifier if not in leg
                if not departure_dt and '|' in service_id:
                    parts = service_id.split('|')
                    if len(parts) >= 5:
                        departure_dt = parts[4]  # e.g., 2026-11-20T20:53
                bundles_before = {b['productFamilyId']: b['price'] for b in bundles}
                break

    if not service_id:
        # Try transfer route
        for travel in result['offer'].get('travels', []):
            for route in travel.get('routes', []):
                legs = route.get('legs', [])
                bundles = route.get('bundles', [])
                if len(legs) >= 1:
                    for leg in legs:
                        if 'STNIGHT' in leg.get('serviceIdentifier', ''):
                            service_id = leg['serviceIdentifier']
                            service_name = service_id.split('|')[1] if '|' in service_id else ''
                            departure_dt = leg.get('departure')
                            bundles_before = {b['productFamilyId']: b['price'] for b in bundles}
                            break
                    if service_id:
                        break

    if not service_id:
        print("  No STNIGHT service found.")
        return

    print(f"  Service: {service_name} ({service_id[:50]}...)")
    print(f"  Departure: {departure_dt}")
    print(f"  Bundles:")
    for prod, price in sorted(bundles_before.items()):
        print(f"    {prod:<10} {price:>8.0f} SEK")

    if args.dry_run:
        print("\n  [DRY RUN] Stopping before booking.")
        return

    # Step 4: Create booking (1 seat, semi-flex)
    origin_eva = EVA.get(origin)
    dest_eva = EVA.get(dest)
    if not origin_eva or not dest_eva:
        print(f"  No EVA number for {origin} or {dest}.")
        return

    # Extract tariff code for SPSF from the search result bundles
    tariff = None
    for travel in result['offer'].get('travels', []):
        for route in travel.get('routes', []):
            legs = route.get('legs', [])
            if len(legs) == 1 and 'STNIGHT' in legs[0].get('serviceIdentifier', ''):
                for b in route.get('bundles', []):
                    if b.get('productFamilyId') == 'SPSF':
                        for ri in b.get('requiredItems', []):
                            for pf in ri.get('passengerFares', []):
                                tariff = pf.get('tariffCode')
                                break
                break

    if not tariff:
        print("  Could not extract tariff code from search results.")
        return

    # Get departure timestamp from the leg's departureStation
    if not departure_dt:
        for travel in result['offer'].get('travels', []):
            for route in travel.get('routes', []):
                legs = route.get('legs', [])
                if len(legs) == 1 and 'STNIGHT' in legs[0].get('serviceIdentifier', ''):
                    dep_station = legs[0].get('departureStation', {})
                    departure_dt = dep_station.get('departureTimestamp')
                    break

    print(f"\n─── BOOKING ───")
    print(f"  Creating booking: {args.count}× {tariff} / SPSF ({origin} → {dest})")

    booking = create_booking(token, origin_eva, dest_eva, departure_dt,
                             service_name, service_id, tariff, count=args.count)
    if not booking:
        print("  Booking failed!")
        return

    pnr = booking.get('bookingNumber', '')
    print(f"  ✓ Booking created: PNR={pnr}")

    # Step 5: Wait briefly, then check calendar+prices AFTER
    print(f"\n─── AFTER booking (waiting 3s) ───")
    time.sleep(3)

    cal_after = get_calendar_entry(token, origin_search, dest_search, target_date)
    if cal_after:
        print(f"  Calendar: amount={cal_after.get('amount')} SEK  "
              f"capacity={cal_after.get('capacity')}  quota={cal_after.get('quota')}")

        # Compare
        for field in ['amount', 'capacity', 'quota']:
            before = cal_before.get(field)
            after = cal_after.get(field)
            if before != after:
                print(f"  ★ {field} changed: {before} → {after}")

    result_after = search(token, origin_search, dest_search, target_date)
    if result_after and 'offer' in result_after:
        for travel in result_after['offer'].get('travels', []):
            for route in travel.get('routes', []):
                legs = route.get('legs', [])
                bundles = route.get('bundles', [])
                if len(legs) == 1 and 'STNIGHT' in legs[0].get('serviceIdentifier', ''):
                    bundles_after = {b['productFamilyId']: b['price'] for b in bundles}
                    print(f"  Bundles after:")
                    for prod in sorted(set(list(bundles_before.keys()) + list(bundles_after.keys()))):
                        bp = bundles_before.get(prod)
                        ap = bundles_after.get(prod)
                        changed = " ★ CHANGED" if bp != ap else ""
                        bp_s = f"{bp:.0f}" if bp else "-"
                        ap_s = f"{ap:.0f}" if ap else "-"
                        print(f"    {prod:<10} {bp_s:>8} → {ap_s:>8}{changed}")
                    break

    # Step 6: Cancel immediately
    print(f"\n─── CANCEL ───")
    print(f"  Cancelling PNR={pnr}...")
    cancel_result = cancel_booking(token, pnr)
    print(f"  ✓ Booking cancelled")

    # Step 7: Check recovery
    print(f"\n─── AFTER cancel (waiting 3s) ───")
    time.sleep(3)

    cal_recovered = get_calendar_entry(token, origin_search, dest_search, target_date)
    if cal_recovered:
        print(f"  Calendar: amount={cal_recovered.get('amount')} SEK  "
              f"capacity={cal_recovered.get('capacity')}  quota={cal_recovered.get('quota')}")
        for field in ['amount', 'capacity', 'quota']:
            before = cal_before.get(field)
            recovered = cal_recovered.get(field)
            if before != recovered:
                print(f"  ⚠ {field} NOT recovered: {before} → {recovered}")
            else:
                print(f"  ✓ {field} recovered: {recovered}")

    print(f"\n{'='*70}")
    print("Done.")


if __name__ == '__main__':
    main()
