#!/usr/bin/env python3
"""
RDC EuroNight (EN 344/345) Price Tier Analysis

Derives canonical Normalpreis tiers per entity and booking mode (single/cabin)
from snapshot data, analogous to leo_tiers.py. Unlike Leo, RDC exposes the tier
boundary directly via the `tier_jump_at` / `next_tier_price` fields, so this tool
combines two views:

  1. Canonical tiers: data-driven from observed Normalpreis frequency (like Leo).
  2. Live tier position: per travel date, the current price + how many places
     remain before the next tier jump (from tier_jump_at).

Fare categories (Normalpreis=35, Sparpreis=34, Interrail=36) are analyzed
separately; tier derivation uses Normalpreis only (the reference price).
Spar/Interrail multipliers are reported empirically.

Entities: Sitz, Liege, Bett, Bett 1. Klasse.
Booking modes: single (shared compartment), cabin (private compartment).

Usage:
  python3 rdc_tiers.py                         # all routes
  python3 rdc_tiers.py hamburg-stockholm       # specific route
  python3 rdc_tiers.py --entity Liege          # filter by entity
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

PROVIDER = 'rdc'

# RDC fare categories (ID -> name)
FARE_NORMAL = '35'
FARE_SPAR = '34'
FARE_INTERRAIL = '36'
FARE_NAMES = {FARE_NORMAL: 'Normalpreis', FARE_SPAR: 'Sparpreis', FARE_INTERRAIL: 'Interrail'}

# Entity display order
ENTITY_ORDER = ['Sitz', 'Liege', 'Bett', 'Bett 1. Klasse']


def discover_routes():
    """All RDC routes via the shared loader."""
    return [r for (prov, r) in loaders.get_all_routes() if prov == PROVIDER]


def load_all_data(route):
    """
    Load RAW snapshots for a route: [(snap_date, results_dict)].
    Uses lib.loaders for file discovery; reads raw JSON because tier derivation
    needs the fare categories (Normalpreis/Sparpreis/Interrail) that the lib
    RDC loader collapses.
    """
    snapshots = []
    for f in loaders.find_files(PROVIDER, route):
        snap_date = loaders.extract_date_from_filename(f)
        with open(f, encoding='utf-8') as fh:
            data = json.load(fh)
        snapshots.append((snap_date, data))
    return snapshots


def fare_amount(fares, fare_id):
    """Return the Amount for a given fare ID, or None if not present."""
    for fare in fares:
        if fare.get('ID') == fare_id:
            return fare.get('Price', {}).get('Amount')
    return None


def collect_observations(snapshots, entity_filter=None):
    """
    Collect per (entity, mode) observations of the Normalpreis.

    Returns:
      observations: {(entity, mode): [(normal_price, snap_date, travel_date, jump_at, next_price)]}
      fare_ratios:  {(entity, mode): [(spar/normal, interrail/normal)]}
      live_tiers:   {(entity, mode): {travel_date: (normal_price, jump_at, next_price)}} (latest snap only)
    """
    observations = defaultdict(list)
    fare_ratios = defaultdict(list)
    live_tiers = defaultdict(dict)

    latest_snap = snapshots[-1][0] if snapshots else None

    for snap_date, results in snapshots:
        for travel_date, entry in results.items():
            if not isinstance(entry, dict) or 'entities' not in entry:
                continue  # info / error / no-service entries
            for ent in entry['entities']:
                title = ent.get('title', '')
                if entity_filter and title != entity_filter:
                    continue
                for mode in ('single', 'cabin'):
                    fares = ent.get(mode, [])
                    if not fares:
                        continue
                    normal = fare_amount(fares, FARE_NORMAL)
                    if normal is None:
                        continue  # no reference price -> skip tier derivation
                    spar = fare_amount(fares, FARE_SPAR)
                    interrail = fare_amount(fares, FARE_INTERRAIL)

                    tiers = ent.get(f'{mode}_tiers', [])
                    jump_at = tiers[0].get('tier_jump_at') if tiers else None
                    next_price = tiers[0].get('next_tier_price') if tiers else None

                    key = (title, mode)
                    observations[key].append((normal, snap_date, travel_date, jump_at, next_price))
                    if spar:
                        fare_ratios[key].append(('spar', round(spar / normal, 3)))
                    if interrail:
                        fare_ratios[key].append(('interrail', round(interrail / normal, 3)))
                    if snap_date == latest_snap:
                        live_tiers[key][travel_date] = (normal, jump_at, next_price)

    return observations, fare_ratios, live_tiers


def identify_tiers(observations):
    """
    Separate canonical tiers from temporary prices (like leo_tiers).

    A canonical tier is a Normalpreis seen on many snapshot days.
    Rare prices within 5% of a canonical tier are treated as noise/rounding;
    otherwise they form their own tier.
    """
    price_snaps = defaultdict(set)
    price_count = defaultdict(int)
    for normal, snap, dt, _, _ in observations:
        price_snaps[normal].add(snap)
        price_count[normal] += 1

    all_snaps = set(snap for _, snap, _, _, _ in observations)
    n_snaps = len(all_snaps)

    frequent = []
    rare = []
    for price in sorted(price_snaps):
        n_days = len(price_snaps[price])
        info = {'price': price, 'snap_days': n_days, 'count': price_count[price],
                'snap_dates': sorted(price_snaps[price])}
        if n_days >= max(2, n_snaps * 0.25):
            frequent.append(info)
        else:
            rare.append(info)

    canonical = list(frequent)
    noise = []
    for item in rare:
        nearest_diff = float('inf')
        for ft in frequent:
            diff_pct = abs(item['price'] - ft['price']) / ft['price'] * 100
            nearest_diff = min(nearest_diff, diff_pct)
        if nearest_diff <= 5:
            noise.append(item)
        else:
            canonical.append(item)

    canonical.sort(key=lambda x: x['price'])
    return canonical, noise


def print_analysis(route, entity_filter=None):
    snapshots = load_all_data(route)
    if not snapshots:
        print(f"  No data for route '{route}'")
        return

    observations, fare_ratios, live_tiers = collect_observations(snapshots, entity_filter)
    n_snaps = len(snapshots)

    print(f"\n{'='*70}")
    print(f"  {route}  ({n_snaps} snapshots, EUR)")
    print(f"{'='*70}")

    # Order keys: entity order, single before cabin
    def sort_key(k):
        title, mode = k
        ei = ENTITY_ORDER.index(title) if title in ENTITY_ORDER else 99
        return (ei, 0 if mode == 'single' else 1)

    for key in sorted(observations, key=sort_key):
        title, mode = key
        obs = observations[key]
        canonical, noise = identify_tiers(obs)

        mode_label = 'Single (geteilt)' if mode == 'single' else 'Cabin (privat)'
        print(f"\n  -- {title} / {mode_label} --")

        if canonical:
            print(f"\n  Canonical Normalpreis tiers ({len(canonical)}):")
            print(f"    {'Tier':<5} {'Price':>8}  {'Obs':>5}  {'Snap days':>10}")
            for i, t in enumerate(canonical, 1):
                print(f"    T{i:<4} {t['price']:>7}EUR  {t['count']:>5}  {t['snap_days']:>10}")
            if len(canonical) > 1:
                print(f"\n  Transitions:")
                for i in range(1, len(canonical)):
                    p_old, p_new = canonical[i-1]['price'], canonical[i]['price']
                    pct = (p_new / p_old - 1) * 100
                    print(f"    T{i} -> T{i+1}:  {p_old} -> {p_new}  (D={p_new-p_old:+}, {pct:+.0f}%)")
                spread = canonical[-1]['price'] / canonical[0]['price']
                print(f"    Total spread: x{spread:.2f} ({(spread-1)*100:.0f}%)")

        # Fare multipliers (empirical)
        ratios = fare_ratios.get(key, [])
        if ratios:
            spar_vals = [r for name, r in ratios if name == 'spar']
            ir_vals = [r for name, r in ratios if name == 'interrail']
            parts = []
            if spar_vals:
                parts.append(f"Spar x{median(spar_vals):.2f}")
            if ir_vals:
                parts.append(f"Interrail x{median(ir_vals):.2f}")
            if parts:
                print(f"    Fare multipliers (median): {', '.join(parts)}")

        if noise:
            noise_prices = ', '.join(f"{n['price']}EUR({n['snap_days']}d)" for n in noise)
            print(f"    Near-tier noise (<5%): {noise_prices}")

        # Live tier position: which future dates are at which tier + places remaining
        live = live_tiers.get(key, {})
        near_jump = [(dt, p, ja, nx) for dt, (p, ja, nx) in live.items()
                     if ja is not None]
        if near_jump:
            near_jump.sort(key=lambda x: x[2])  # by places remaining
            print(f"\n  Live tier position (latest snapshot, {len(near_jump)} dates near a jump):")
            print(f"    {'Date':<12} {'Price':>7}  {'Places left':>11}  {'Next tier':>9}")
            for dt, p, ja, nx in near_jump[:10]:
                left = ja - 1 if ja else '?'
                nx_str = f"{nx}EUR" if nx else 'sold out'
                print(f"    {dt:<12} {p:>6}EUR  {left:>11}  {nx_str:>9}")


def main():
    args = sys.argv[1:]
    entity_filter = None
    route_filter = None

    i = 0
    while i < len(args):
        if args[i] in ('-h', '--help'):
            print(__doc__.strip())
            sys.exit(0)
        elif args[i] == '--entity' and i + 1 < len(args):
            entity_filter = args[i + 1]
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

    for route in routes:
        print_analysis(route, entity_filter)


if __name__ == '__main__':
    main()
