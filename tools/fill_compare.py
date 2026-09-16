"""
Fill Curve Comparison — Leo Express vs European Sleeper

Compares how quickly classes sell across providers:
- Absolute fill rates (seats/day)
- Relative fill rates (% capacity/day)
- Time-to-sellout estimates
- Comparable class pairs (Sleeper ↔ Berth, ECO ↔ Couchette, etc.)

Usage:
  python3 tools/fill_compare.py                     # Summary comparison
  python3 tools/fill_compare.py --date 2026-09-15   # Specific departure date
  python3 tools/fill_compare.py --top 20            # Top N fastest-filling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.loaders import find_files, extract_date_from_filename, load_leo_snapshot, load_es_snapshot, get_all_routes
from datetime import date, timedelta
from collections import defaultdict
import argparse


# Class equivalence mapping for cross-provider comparison
CLASS_GROUPS = {
    'Sleeper/Berth': {
        'leo': ['ECOSLEEPER', 'ECOSLEEPERLADY'],
        'es': ['berth-double', 'berth-single', 'berth-triple', 'berth-triple-women-only'],
    },
    'Comfort': {
        'leo': [],
        'es': ['comfort-single', 'comfort-double', 'comfort-triple', 'comfort-triple-women-only'],
    },
    'Sitz/Couchette': {
        'leo': ['ECO', 'BUS'],
        'es': ['couchette-5', 'couchette-5-women-only', 'seat-second-class'],
    },
}


def compute_fill_curves(provider, route):
    """
    For each (travel_date, class), compute fill curve from snapshots.
    Returns: {(date, class): {'initial_cap': int, 'final_cap': int, 'sold': int,
              'days_observed': int, 'rate': float, 'sold_pct': float, 'price_first': float, 'price_last': float}}
    """
    files = find_files(provider, route)
    if not files:
        return {}

    # Collect capacity timeline per (travel_date, class)
    timelines = defaultdict(list)  # (travel_date, class) -> [(snap_date, cap, price)]

    for f in files:
        snap_str = extract_date_from_filename(f)
        snap_date = date(int(snap_str[:4]), int(snap_str[4:6]), int(snap_str[6:8]))
        loader = load_leo_snapshot if provider == 'leo' else load_es_snapshot
        data = loader(f)
        if not data:
            continue
        for travel_date_str, classes in data.items():
            for cls_name, vals in classes.items():
                cap = vals.get('capacity')
                price = vals.get('price')
                if cap is not None and cap > 0:
                    timelines[(travel_date_str, cls_name)].append((snap_date, cap, price))

    # Compute fill metrics
    curves = {}
    today = date.today()

    for (travel_date_str, cls_name), points in timelines.items():
        if len(points) < 2:
            continue
        points.sort()
        initial_cap = points[0][1]
        final_cap = points[-1][1]
        days_observed = (points[-1][0] - points[0][0]).days
        if days_observed < 1:
            continue

        sold = initial_cap - final_cap
        if sold < 0:
            sold = 0  # Capacity increase (wagon addition) — ignore for fill rate
            initial_cap = max(p[1] for p in points)
            sold = initial_cap - final_cap

        rate = sold / days_observed if days_observed > 0 else 0
        sold_pct = sold / initial_cap if initial_cap > 0 else 0

        try:
            travel_date = date.fromisoformat(travel_date_str)
            is_future = travel_date >= today
        except:
            is_future = True

        curves[(travel_date_str, cls_name)] = {
            'initial_cap': initial_cap,
            'final_cap': final_cap,
            'sold': sold,
            'days_observed': days_observed,
            'rate': rate,
            'sold_pct': sold_pct,
            'price_first': points[0][2],
            'price_last': points[-1][2],
            'is_future': is_future,
        }

    return curves


def main():
    parser = argparse.ArgumentParser(description='Fill Curve Comparison')
    parser.add_argument('--date', help='Filter to specific departure date')
    parser.add_argument('--top', type=int, default=15, help='Show top N fastest-filling')
    parser.add_argument('--future', action='store_true', default=True, help='Future dates only')
    parser.add_argument('--all-dates', action='store_true', help='Include past dates')
    args = parser.parse_args()

    routes = get_all_routes()

    # Compute fill curves for all routes
    all_curves = []  # [(provider, route, travel_date, class, metrics)]

    for provider, route in routes:
        curves = compute_fill_curves(provider, route)
        for (travel_date, cls_name), metrics in curves.items():
            if args.date and args.date not in travel_date:
                continue
            if not args.all_dates and not metrics['is_future']:
                continue
            if metrics['days_observed'] < 3:
                continue
            all_curves.append((provider, route, travel_date, cls_name, metrics))

    if not all_curves:
        print("Keine Daten gefunden.")
        return

    # Sort by fill rate (fastest filling first)
    all_curves.sort(key=lambda x: -x[4]['rate'])

    # === Top fastest-filling ===
    print(f"\n{'='*85}")
    print(f"  TOP {args.top} SCHNELLSTE FÜLLRATEN (beide Provider)")
    print(f"{'='*85}")
    print(f"  {'Provider':<5} {'Route':<22} {'Datum':<12} {'Klasse':<26} {'Rate':>7} {'Sold%':>6} {'Cap':>6}")
    print(f"  {'-'*5} {'-'*22} {'-'*12} {'-'*26} {'-'*7} {'-'*6} {'-'*6}")

    for provider, route, travel_date, cls_name, m in all_curves[:args.top]:
        p = provider.upper()[:3]
        r = route[:22]
        print(f"  {p:<5} {r:<22} {travel_date:<12} {cls_name:<26} {m['rate']:>5.1f}/d {m['sold_pct']*100:>5.0f}% {m['final_cap']:>5}")

    # === Per-group comparison ===
    print(f"\n{'='*85}")
    print(f"  VERGLEICH NACH KLASSEN-GRUPPE")
    print(f"{'='*85}")

    for group_name, mapping in CLASS_GROUPS.items():
        leo_rates = []
        es_rates = []
        for provider, route, travel_date, cls_name, m in all_curves:
            if provider == 'leo' and cls_name in mapping['leo']:
                leo_rates.append(m)
            elif provider == 'es' and cls_name in mapping['es']:
                es_rates.append(m)

        if not leo_rates and not es_rates:
            continue

        print(f"\n  {group_name}:")
        if leo_rates:
            avg_rate = sum(m['rate'] for m in leo_rates) / len(leo_rates)
            avg_pct = sum(m['sold_pct'] for m in leo_rates) / len(leo_rates)
            avg_cap = sum(m['initial_cap'] for m in leo_rates) / len(leo_rates)
            print(f"    Leo:  avg {avg_rate:.2f}/Tag, {avg_pct*100:.0f}% verkauft, "
                  f"Startcap ~{avg_cap:.0f} (n={len(leo_rates)} Beobachtungen)")
        if es_rates:
            avg_rate = sum(m['rate'] for m in es_rates) / len(es_rates)
            avg_pct = sum(m['sold_pct'] for m in es_rates) / len(es_rates)
            avg_cap = sum(m['initial_cap'] for m in es_rates) / len(es_rates)
            print(f"    ES:   avg {avg_rate:.2f}/Tag, {avg_pct*100:.0f}% verkauft, "
                  f"Startcap ~{avg_cap:.0f} (n={len(es_rates)} Beobachtungen)")

    # === Provider-level summary ===
    print(f"\n{'='*85}")
    print(f"  ZUSAMMENFASSUNG")
    print(f"{'='*85}")

    leo_all = [m for p, r, d, c, m in all_curves if p == 'leo']
    es_all = [m for p, r, d, c, m in all_curves if p == 'es']

    if leo_all:
        avg_rate = sum(m['rate'] for m in leo_all) / len(leo_all)
        avg_pct = sum(m['sold_pct'] for m in leo_all) / len(leo_all)
        max_rate = max(m['rate'] for m in leo_all)
        print(f"\n  Leo Express ({len(leo_all)} Klasse/Datum-Paare):")
        print(f"    Avg Verkaufsrate: {avg_rate:.2f} Plätze/Tag")
        print(f"    Avg bereits verkauft: {avg_pct*100:.0f}%")
        print(f"    Max Verkaufsrate: {max_rate:.1f} Plätze/Tag")

    if es_all:
        avg_rate = sum(m['rate'] for m in es_all) / len(es_all)
        avg_pct = sum(m['sold_pct'] for m in es_all) / len(es_all)
        max_rate = max(m['rate'] for m in es_all)
        print(f"\n  European Sleeper ({len(es_all)} Klasse/Datum-Paare):")
        print(f"    Avg Verkaufsrate: {avg_rate:.2f} Plätze/Tag")
        print(f"    Avg bereits verkauft: {avg_pct*100:.0f}%")
        print(f"    Max Verkaufsrate: {max_rate:.1f} Plätze/Tag")


if __name__ == '__main__':
    main()
