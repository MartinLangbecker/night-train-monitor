#!/usr/bin/env python3
"""
Leo Express Price Tier Analysis

Extracts canonical price tiers per route and class from snapshot data.
Identifies temporary surcharges (price deviations without capacity change).

CAVEAT: On 18.08.2026, Sleeper/Lady pricing switched from independent per-class
tier calculation (20-berth pools) to coupled pricing (shared 40-berth tier counter).
This tool analyzes capacity per individual class, which was correct for the pre-18.08.
regime. For the coupled regime, tier boundaries should be derived from combined
Sleeper+Lady capacity. See docs/pricing-model.md for details.

Usage:
  python3 leo-tiers.py                    # All routes
  python3 leo-tiers.py weimar-przemysl    # Specific route (matches both directions + currencies)
  python3 leo-tiers.py --class ECOSLEEPER # Filter by class
"""

import json
import os
import sys
from collections import defaultdict
from statistics import median

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from lib import loaders  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROVIDER = 'leo'

CLASS_ORDER = ['ECO', 'BUS', 'ECOSLEEPER', 'ECOSLEEPERLADY']
CLASS_NAMES = {
    'ECO': 'Economy',
    'BUS': 'Business',
    'ECOSLEEPER': 'Sleeper',
    'ECOSLEEPERLADY': 'Sleeper Lady',
}


def discover_routes():
    """All LEO routes (incl. CZK variants) via the shared loader."""
    return [r for (prov, r) in loaders.get_all_routes_all_currencies()
            if prov == PROVIDER]


def load_all_data(route):
    """
    Load RAW snapshots for a route: [(snap_date, results_dict)].
    Uses lib.loaders for file discovery; reads raw JSON because tier derivation
    needs per-class prices in the original currency (EUR and CZK variants).
    """
    snapshots = []
    for f in loaders.find_files(PROVIDER, route):
        snap_date = loaders.extract_date_from_filename(f)
        data = json.load(open(f, encoding='utf-8'))
        results = data.get('results', data)  # EUR files have top-level dict
        snapshots.append((snap_date, results))
    return snapshots


COUPLING_DATE = '20260818'  # Sleeper/Lady coupled from this snapshot onwards


def analyze_route(route, class_filter=None):
    """Analyze price tiers for a single route.

    For ECOSLEEPER/ECOSLEEPERLADY, splits into two regimes:
    - Pre-18.08.2026: independent per-class capacity (20-berth pools)
    - Post-18.08.2026: coupled combined capacity (40-berth pool)
    """
    snapshots = load_all_data(route)
    if not snapshots:
        return None

    # Collect all (price, capacity, snap_date, travel_date) per class
    observations = defaultdict(list)  # cls -> [(price, cap, snap, travel_date)]
    price_by_snap = defaultdict(lambda: defaultdict(set))  # cls -> snap -> set(prices)

    for snap_date, results in snapshots:
        # Build a lookup for combined sleeper capacity in this snapshot
        sleeper_caps = {}  # travel_date -> (sleeper_cap, lady_cap)
        if int(snap_date) >= int(COUPLING_DATE):
            for travel_date, entry in results.items():
                if not isinstance(entry, dict) or 'classes' not in entry:
                    continue
                s_cap = l_cap = None
                for c in entry['classes']:
                    if c['class'] == 'ECOSLEEPER':
                        s_cap = c.get('capacity')
                    elif c['class'] == 'ECOSLEEPERLADY':
                        l_cap = c.get('capacity')
                if s_cap is not None and l_cap is not None:
                    sleeper_caps[travel_date] = (s_cap, l_cap)

        for travel_date, entry in results.items():
            if not isinstance(entry, dict) or 'classes' not in entry:
                continue
            for c in entry['classes']:
                cls = c['class']
                if class_filter and cls != class_filter:
                    continue
                price = c.get('price')
                cap = c.get('capacity')
                if price is None:
                    continue

                # For coupled regime: use combined capacity for sleeper classes
                if cls in ('ECOSLEEPER', 'ECOSLEEPERLADY') and int(snap_date) >= int(COUPLING_DATE):
                    if travel_date in sleeper_caps:
                        s_cap, l_cap = sleeper_caps[travel_date]
                        cap = s_cap + l_cap  # Combined 40-berth pool

                observations[cls].append((price, cap, snap_date, travel_date))
                price_by_snap[cls][snap_date].add(price)

    return observations, price_by_snap, len(snapshots)


def identify_tiers(observations):
    """
    Separate canonical tiers from temporary surcharges.

    A canonical tier is a price point that represents a distinct capacity band.
    A temporary surcharge is a price that appears briefly at the same capacity
    as a canonical tier (~3-5% above it).

    Logic:
    1. Group prices by snapshot frequency
    2. Prices seen on many days → canonical
    3. Rare prices: check if capacity overlaps with a nearby canonical tier
       - If yes and within 10%: surcharge
       - If no (different capacity band): separate tier (e.g. sold-out-fast tier)
    """
    price_snaps = defaultdict(set)  # price -> set of snap_dates
    price_caps = defaultdict(list)  # price -> [capacities]

    for price, cap, snap, dt in observations:
        price_snaps[price].add(snap)
        if cap is not None:
            price_caps[price].append(cap)

    all_snaps = set(snap for _, _, snap, _ in observations)
    n_snaps = len(all_snaps)

    # First pass: frequent prices are definitely canonical
    frequent = []
    rare = []

    for price in sorted(price_snaps.keys()):
        n_days = len(price_snaps[price])
        caps = price_caps[price]
        cap_med = median(caps) if caps else None

        info = {
            'price': price,
            'snap_days': n_days,
            'snap_dates': sorted(price_snaps[price]),
            'cap_min': min(caps) if caps else None,
            'cap_max': max(caps) if caps else None,
            'cap_median': cap_med,
            'count': len([x for x in observations if x[0] == price]),
        }

        if n_days >= max(3, n_snaps * 0.25):
            frequent.append(info)
        else:
            rare.append(info)

    # Second pass: classify rare prices as either tiers or surcharges
    canonical = list(frequent)
    surcharges = []

    for item in rare:
        # Find nearest frequent tier by price
        nearest = None
        nearest_diff_pct = float('inf')
        for ft in frequent:
            diff_pct = abs(item['price'] - ft['price']) / ft['price'] * 100
            if diff_pct < nearest_diff_pct:
                nearest_diff_pct = diff_pct
                nearest = ft

        # If within 10% of a canonical tier AND capacity ranges overlap → surcharge
        if nearest and nearest_diff_pct <= 10:
            cap_overlaps = (
                item['cap_min'] is not None and nearest['cap_min'] is not None and
                item['cap_min'] <= nearest['cap_max'] + 2 and
                item['cap_max'] >= nearest['cap_min'] - 2
            )
            if cap_overlaps:
                surcharges.append(item)
                continue

        # Otherwise: it's a distinct tier (e.g. quickly sold-out early tier)
        canonical.append(item)

    # Sort canonical by price
    canonical.sort(key=lambda x: x['price'])

    return canonical, surcharges


def print_analysis(route, class_filter=None):
    """Print full tier analysis for a route."""
    result = analyze_route(route, class_filter)
    if result is None:
        print(f"  No data for route '{route}'")
        return

    observations, price_by_snap, n_snaps = result
    currency = 'CZK' if route.endswith('-czk') else 'EUR'

    print(f"\n{'═'*70}")
    print(f"  {route}  ({n_snaps} snapshots, {currency})")
    print(f"{'═'*70}")

    for cls in CLASS_ORDER:
        if cls not in observations:
            continue

        obs = observations[cls]
        canonical, surcharges = identify_tiers(obs)

        print(f"\n  ── {CLASS_NAMES[cls]} ──")

        if canonical:
            print(f"\n  Canonical tiers ({len(canonical)}):")
            print(f"    {'Tier':<5} {'Price':>8}  {'Observations':>13}  {'Snap days':>10}  {'Capacity':>12}")
            for i, t in enumerate(canonical, 1):
                cap_str = f"{t['cap_min']}-{t['cap_max']}" if t['cap_min'] is not None else "?"
                print(f"    T{i:<4} {t['price']:>8.1f}  {t['count']:>13}  {t['snap_days']:>10}  {cap_str:>12}")

            # Transitions
            if len(canonical) > 1:
                print(f"\n  Transitions:")
                for i in range(1, len(canonical)):
                    p_old = canonical[i-1]['price']
                    p_new = canonical[i]['price']
                    delta = p_new - p_old
                    pct = (p_new / p_old - 1) * 100
                    print(f"    T{i} → T{i+1}:  {p_old:.1f} → {p_new:.1f}  (Δ={delta:+.1f}, {pct:+.0f}%)")
                spread = canonical[-1]['price'] / canonical[0]['price']
                print(f"    Total spread: ×{spread:.2f} ({(spread-1)*100:.0f}%)")

        if surcharges:
            print(f"\n  Temporary surcharges ({len(surcharges)}):")
            for s in surcharges:
                # Find nearest canonical tier
                nearest = None
                nearest_diff = float('inf')
                for t in canonical:
                    diff_pct = abs(s['price'] - t['price']) / t['price'] * 100
                    if diff_pct < nearest_diff:
                        nearest_diff = diff_pct
                        nearest = t
                near_str = f"≈T{canonical.index(nearest)+1} ({nearest['price']:.1f}) +{nearest_diff:.1f}%" if nearest else ""
                snaps_str = ','.join(s['snap_dates'])
                print(f"    {s['price']:>8.1f}  seen on [{snaps_str}]  cap={s['cap_min']}-{s['cap_max']}  {near_str}")


def main():
    args = sys.argv[1:]
    class_filter = None
    route_filter = None

    i = 0
    while i < len(args):
        if args[i] in ('-h', '--help'):
            print(__doc__.strip())
            sys.exit(0)
        elif args[i] == '--class' and i + 1 < len(args):
            class_filter = args[i + 1].upper()
            i += 2
        else:
            route_filter = args[i]
            i += 1

    routes = discover_routes()

    if route_filter:
        routes = [r for r in routes if route_filter in r]

    if not routes:
        print(f"No routes found matching '{route_filter}'")
        print(f"Available: {discover_routes()}")
        sys.exit(1)

    # Default: show EUR routes (CZK is supplementary)
    eur_routes = [r for r in routes if r.endswith('-eur')]
    czk_routes = [r for r in routes if r.endswith('-czk')]

    for route in eur_routes or routes:
        print_analysis(route, class_filter)

    # If CZK routes exist, show them in a compact format
    if eur_routes and czk_routes:
        print(f"\n{'═'*70}")
        print(f"  CZK REFERENCE (base currency)")
        print(f"{'═'*70}")
        for route in czk_routes:
            print_analysis(route, class_filter)


if __name__ == '__main__':
    main()
