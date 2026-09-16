#!/usr/bin/env python3
"""
SJ Night Train Price Tier Analysis

Reconstructs the price tier ladder per (comfort class, flexibility) from snapshot
data. Unlike RDC/Leo, SJ uses very fine-grained tiers (40-65 steps in ~10 SEK
increments) and the ladder is route-specific. The API exposes tier boundaries via
`tier_jump_at` / `next_tier_price`, so this tool combines two views:

  1. Canonical ladder: distinct prices observed across all snapshots, augmented by
     `next_tier_price` values (which reveal tiers not yet seen as a start price).
  2. Live tier position: per travel date in the latest snapshot, the current price
     plus places-left-before-jump (from tier_jump_at) and the next tier price.

PRIVATE comfort types (SLEEPER_*_PRIVATE, COUCHETTE_PRIVATE) have different
semantics: price at n=1 is the full compartment price, and `next_tier_price` at a
jump is the marginal cost of an additional occupant, NOT the next tier. These are
reported separately and their next_tier_price is excluded from the ladder.

Data layout: results[travel_date].departures[].{seats,beds}[class][flex] =
  {price, tier_jump_at, next_tier_price}

Usage:
  python3 sj_tiers.py                          # all routes
  python3 sj_tiers.py stockholm-malmoe         # specific route
  python3 sj_tiers.py --class SECOND           # filter by comfort class
  python3 sj_tiers.py --flex NOFLEX            # filter by flexibility
"""

import json
import os
import sys
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from lib import loaders  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROVIDER = 'sj'

FLEX_ORDER = ['NOFLEX', 'SEMIFLEX', 'FULLFLEX']


def is_private(cls_name):
    """PRIVATE/SOLO comfort types have compartment pricing semantics."""
    return 'PRIVATE' in cls_name or 'SOLO' in cls_name


def discover_routes():
    """All SJ routes via the shared loader."""
    return [r for (prov, r) in loaders.get_all_routes() if prov == PROVIDER]


def load_all_data(route):
    """
    Load RAW snapshots for a route: [(snap_date, results_dict)].
    Uses lib.loaders for file discovery, but reads raw JSON because the tier
    fields (all flex levels + next_tier_price) are dropped by the lib SJ loader.
    """
    snapshots = []
    for f in loaders.find_files(PROVIDER, route):
        snap_date = loaders.extract_date_from_filename(f)
        with open(f, encoding='utf-8') as fh:
            data = json.load(fh)
        snapshots.append((snap_date, data))
    return snapshots


def collect_observations(snapshots, class_filter=None, flex_filter=None):
    """
    Collect per (class, flex) observations.

    Returns:
      observed:  {(cls, flex): set(prices)}          distinct start prices
      next_seen: {(cls, flex): set(next_tier_price)} distinct next-tier prices
      live:      {(cls, flex): {travel_date: (price, jump_at, next_price)}} latest snap
      private:   set of class names that are private (compartment pricing)
    """
    observed = defaultdict(set)
    next_seen = defaultdict(set)
    live = defaultdict(dict)
    private = set()

    latest_snap = snapshots[-1][0] if snapshots else None

    for snap_date, results in snapshots:
        if not isinstance(results, dict):
            continue
        for travel_date, entry in results.items():
            if not isinstance(entry, dict):
                continue
            for dep in entry.get('departures', []):
                for category in ('seats', 'beds'):
                    classes = dep.get(category) or {}
                    for cls, flexes in classes.items():
                        if class_filter and cls != class_filter:
                            continue
                        if is_private(cls):
                            private.add(cls)
                        for flex, info in flexes.items():
                            if flex_filter and flex != flex_filter:
                                continue
                            if not isinstance(info, dict):
                                continue
                            price = info.get('price')
                            jump = info.get('tier_jump_at')
                            nxt = info.get('next_tier_price')
                            key = (cls, flex)
                            if price is not None:
                                observed[key].add(price)
                            if nxt is not None:
                                next_seen[key].add(nxt)
                            if snap_date == latest_snap and price is not None:
                                live[key][travel_date] = (price, jump, nxt)
    return observed, next_seen, live, private


def build_ladder(observed_prices, next_prices, private):
    """
    Combine observed start prices with next_tier_prices to form the full ladder.
    For private classes, next_tier_price is marginal (extra occupant) -> exclude.
    """
    ladder = set(observed_prices)
    if not private:
        ladder |= next_prices
    return sorted(ladder)


def flex_sort_key(flex):
    return FLEX_ORDER.index(flex) if flex in FLEX_ORDER else 99


def analyze_route(route, class_filter=None, flex_filter=None):
    snapshots = load_all_data(route)
    if not snapshots:
        print(f"  No snapshots for {route}")
        return
    observed, next_seen, live, private = collect_observations(
        snapshots, class_filter, flex_filter)

    print(f"\n{'=' * 70}")
    print(f"  {route}  ({len(snapshots)} snapshots, SEK)")
    print(f"{'=' * 70}")

    if not observed:
        print("  No tier data.")
        return

    # group keys by class, then flex
    keys = sorted(observed.keys(), key=lambda k: (k[0], flex_sort_key(k[1])))
    current_cls = None
    for (cls, flex) in keys:
        if cls != current_cls:
            tag = ' (PRIVATE — compartment price)' if is_private(cls) else ''
            print(f"\n  -- {cls}{tag} --")
            current_cls = cls

        ladder = build_ladder(observed[(cls, flex)], next_seen[(cls, flex)],
                              is_private(cls))
        if not ladder:
            continue
        obs_only = sorted(observed[(cls, flex)])
        print(f"    {flex:9s}: {len(ladder)} steps  "
              f"range {ladder[0]}–{ladder[-1]} SEK  "
              f"(observed start prices: {len(obs_only)})")
        # show the ladder compactly
        shown = ladder if len(ladder) <= 14 else ladder[:12] + ['…', ladder[-1]]
        print(f"      {' → '.join(str(x) for x in shown)}")

        # live tier position: dates near a jump (tier_jump_at not null)
        near = [(d, p, j, n) for d, (p, j, n) in live[(cls, flex)].items()
                if j is not None]
        if near:
            near.sort(key=lambda x: x[0])
            print(f"      live (dates near a jump, latest snapshot):")
            for d, p, j, n in near[:5]:
                if is_private(cls):
                    extra = f"+{j-1} extra pax" if j else "extra pax"
                    cost = f"+{n} SEK/pax" if n is not None else "(no marginal price)"
                    print(f"        {d}: {p} SEK  {extra} → {cost}")
                else:
                    nxt = f"next {n} SEK" if n is not None else "(no next price)"
                    print(f"        {d}: {p} SEK  {j-1 if j else '?'} places left → {nxt}")


def main():
    ap = argparse.ArgumentParser(description="SJ night train price tier analysis")
    ap.add_argument('route', nargs='?', help="Route name (default: all)")
    ap.add_argument('--class', dest='cls', help="Filter by comfort class (e.g. SECOND)")
    ap.add_argument('--flex', help="Filter by flexibility (NOFLEX/SEMIFLEX/FULLFLEX)")
    args = ap.parse_args()

    routes = [args.route] if args.route else discover_routes()
    if not routes:
        print("No SJ routes found.")
        return
    for route in routes:
        analyze_route(route, args.cls, args.flex)


if __name__ == '__main__':
    main()
