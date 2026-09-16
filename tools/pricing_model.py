"""
Unified Pricing Model Analysis — Leo Express vs European Sleeper

Compares pricing mechanisms across providers by correlating price with:
- Remaining capacity (Leo's primary driver)
- Lead time / days until departure (ES's primary driver)
- Capacity changes over time (direction detection)

Usage:
  python3 tools/pricing_model.py                    # All routes, summary
  python3 tools/pricing_model.py --route hamburg-paris-eur  # Specific route
  python3 tools/pricing_model.py --class couchette-5        # Specific class
  python3 tools/pricing_model.py --detail                   # Full correlation tables
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.loaders import find_files, extract_date_from_filename, load_leo_snapshot, load_es_snapshot, get_all_routes
from collections import defaultdict
from datetime import date
import json
import argparse


def load_snapshots(provider, route):
    """Load all snapshots for a route into unified format with metadata."""
    files = find_files(provider, route)
    snapshots = []  # [(snap_date, {travel_date: {class: {capacity, price}}})]
    for f in files:
        snap_date_str = extract_date_from_filename(f)
        snap_date = date(int(snap_date_str[:4]), int(snap_date_str[4:6]), int(snap_date_str[6:8]))
        if provider == 'leo':
            data = load_leo_snapshot(f)
        else:
            data = load_es_snapshot(f)
        if data:
            snapshots.append((snap_date, data))
    return snapshots


def collect_observations(snapshots):
    """
    From snapshots, collect (price, capacity, lead_days) triples per class.
    Returns: {class_name: [(price, capacity, lead_days)]}
    """
    obs = defaultdict(list)
    for snap_date, data in snapshots:
        for travel_date_str, classes in data.items():
            try:
                td = date.fromisoformat(travel_date_str)
            except (ValueError, TypeError):
                continue
            lead_days = (td - snap_date).days
            if lead_days < 0:
                continue
            for cls_name, vals in classes.items():
                price = vals.get('price')
                cap = vals.get('capacity')
                if price and price > 0 and cap is not None:
                    obs[cls_name].append((price, cap, lead_days))
    return obs


def correlation(xs, ys):
    """Pearson correlation coefficient."""
    n = len(xs)
    if n < 3:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def r_squared(xs, ys):
    """R² (coefficient of determination)."""
    r = correlation(xs, ys)
    return r * r


def analyze_class(name, observations, detail=False):
    """Analyze pricing model for one class."""
    if len(observations) < 20:
        return None

    prices = [p for p, c, l in observations]
    caps = [c for p, c, l in observations]
    leads = [l for p, c, l in observations]

    r2_cap = r_squared(caps, prices)
    r2_lead = r_squared(leads, prices)
    corr_cap = correlation(caps, prices)
    corr_lead = correlation(leads, prices)

    # Determine model type
    if r2_cap > 0.5 and r2_cap > r2_lead * 1.5:
        model = "CAPACITY"
    elif r2_lead > 0.3 and r2_lead > r2_cap * 1.5:
        model = "LEAD_TIME"
    elif r2_cap > 0.3 and r2_lead > 0.3:
        model = "HYBRID"
    else:
        model = "UNCLEAR"

    # Price direction detection: does price ever decrease for same travel date?
    # Group by (travel_date approximation using lead_days buckets from same snap)
    price_decreases = 0
    price_increases = 0
    # Simple: sort by lead_days descending (early bookings first), check price trend
    by_lead = sorted(observations, key=lambda x: -x[2])
    prev_price = None
    for p, c, l in by_lead:
        if prev_price is not None:
            if p < prev_price:
                price_decreases += 1
            elif p > prev_price:
                price_increases += 1
        prev_price = p

    decrease_ratio = price_decreases / max(1, price_decreases + price_increases)

    result = {
        'name': name,
        'n': len(observations),
        'r2_cap': r2_cap,
        'r2_lead': r2_lead,
        'corr_cap': corr_cap,
        'corr_lead': corr_lead,
        'model': model,
        'price_range': (min(prices), max(prices)),
        'cap_range': (min(caps), max(caps)),
        'tiers': len(set(prices)),
        'decrease_ratio': decrease_ratio,
    }

    if detail:
        # Capacity buckets
        cap_buckets = defaultdict(list)
        for p, c, l in observations:
            bucket = (c // 10) * 10
            cap_buckets[bucket].append(p)
        result['cap_buckets'] = {k: (min(v), sum(v)/len(v), max(v), len(v)) 
                                  for k, v in sorted(cap_buckets.items())}
        # Lead time buckets
        lead_buckets = defaultdict(list)
        for p, c, l in observations:
            bucket = (l // 14) * 14
            lead_buckets[bucket].append(p)
        result['lead_buckets'] = {k: (min(v), sum(v)/len(v), max(v), len(v))
                                   for k, v in sorted(lead_buckets.items())}

    return result


def print_summary(provider, route, results):
    """Print summary for one route."""
    print(f"\n{'='*70}")
    print(f"  {provider.upper()}: {route}")
    print(f"{'='*70}")
    print(f"  {'Klasse':<28} {'R²cap':>6} {'R²lead':>7} {'Modell':<10} {'Tiers':>5} {'Preis':>14} {'↓%':>5}")
    print(f"  {'-'*28} {'-'*6} {'-'*7} {'-'*10} {'-'*5} {'-'*14} {'-'*5}")

    for r in results:
        pmin, pmax = r['price_range']
        print(f"  {r['name']:<28} {r['r2_cap']:>5.2f}  {r['r2_lead']:>6.2f}  {r['model']:<10} {r['tiers']:>5} "
              f"{pmin:>6.0f}–{pmax:<6.0f} {r['decrease_ratio']*100:>4.0f}%")


def print_detail(result):
    """Print detailed correlation for one class."""
    print(f"\n  --- {result['name']} (n={result['n']}) ---")
    print(f"  Modell: {result['model']}")
    print(f"  R² Kapazität→Preis: {result['r2_cap']:.3f} (r={result['corr_cap']:.3f})")
    print(f"  R² Vorlaufzeit→Preis: {result['r2_lead']:.3f} (r={result['corr_lead']:.3f})")
    print(f"  Preissenkungen: {result['decrease_ratio']*100:.0f}% aller Übergänge")

    if 'cap_buckets' in result:
        print(f"\n  Kapazität → Preis:")
        for cap, (pmin, pavg, pmax, n) in result['cap_buckets'].items():
            print(f"    cap {cap:>3}–{cap+9}: avg €{pavg:>6.1f} (€{pmin:.0f}–{pmax:.0f}, n={n})")

    if 'lead_buckets' in result:
        print(f"\n  Vorlaufzeit → Preis:")
        for lead, (pmin, pavg, pmax, n) in result['lead_buckets'].items():
            print(f"    {lead:>3}–{lead+13}d: avg €{pavg:>6.1f} (€{pmin:.0f}–{pmax:.0f}, n={n})")


def print_comparison(all_results):
    """Print cross-provider comparison."""
    print(f"\n{'='*70}")
    print(f"  VERGLEICH: Pricing-Modelle")
    print(f"{'='*70}")

    leo_results = [(p, r, res) for p, r, res in all_results if p == 'leo']
    es_results = [(p, r, res) for p, r, res in all_results if p == 'es']

    if leo_results and es_results:
        leo_r2_caps = [res['r2_cap'] for _, _, res in leo_results]
        leo_r2_leads = [res['r2_lead'] for _, _, res in leo_results]
        es_r2_caps = [res['r2_cap'] for _, _, res in es_results]
        es_r2_leads = [res['r2_lead'] for _, _, res in es_results]
        leo_decreases = [res['decrease_ratio'] for _, _, res in leo_results]
        es_decreases = [res['decrease_ratio'] for _, _, res in es_results]

        print(f"\n  {'Metrik':<35} {'Leo Express':>12} {'Eur. Sleeper':>13}")
        print(f"  {'-'*35} {'-'*12} {'-'*13}")
        print(f"  {'Avg R² Kapazität→Preis':<35} {sum(leo_r2_caps)/len(leo_r2_caps):>11.3f}  {sum(es_r2_caps)/len(es_r2_caps):>12.3f}")
        print(f"  {'Avg R² Vorlaufzeit→Preis':<35} {sum(leo_r2_leads)/len(leo_r2_leads):>11.3f}  {sum(es_r2_leads)/len(es_r2_leads):>12.3f}")
        print(f"  {'Avg Preissenkungsanteil':<35} {sum(leo_decreases)/len(leo_decreases)*100:>10.0f}%  {sum(es_decreases)/len(es_decreases)*100:>11.0f}%")
        print(f"  {'Klassen analysiert':<35} {len(leo_results):>12}  {len(es_results):>13}")

        # Conclusion
        leo_cap_dominant = sum(1 for r in leo_r2_caps if r > 0.3) / len(leo_r2_caps)
        es_lead_dominant = sum(1 for r in es_r2_leads if r > 0.1) / len(es_r2_leads)

        print(f"\n  Fazit:")
        print(f"    Leo Express: {'Kapazitätsgetrieben' if sum(leo_r2_caps)/len(leo_r2_caps) > 0.3 else 'Unklar'}")
        print(f"    European Sleeper: {'Hybrid (Vorlaufzeit + Nachfrage)' if sum(es_r2_leads)/len(es_r2_leads) > 0.05 else 'Unklar'}")


def main():
    parser = argparse.ArgumentParser(description='Pricing Model Analysis')
    parser.add_argument('--route', help='Specific route to analyze')
    parser.add_argument('--provider', choices=['leo', 'es'], help='Filter by provider')
    parser.add_argument('--class', dest='cls', help='Filter by class name (substring)')
    parser.add_argument('--detail', action='store_true', help='Show detailed buckets')
    args = parser.parse_args()

    routes = get_all_routes()
    if args.route:
        routes = [(p, r) for p, r in routes if args.route in r]
    if args.provider:
        routes = [(p, r) for p, r in routes if p == args.provider]

    all_results = []

    for provider, route in routes:
        snapshots = load_snapshots(provider, route)
        if not snapshots:
            continue

        observations = collect_observations(snapshots)
        results = []

        for cls_name in sorted(observations.keys()):
            if args.cls and args.cls.lower() not in cls_name.lower():
                continue
            result = analyze_class(cls_name, observations[cls_name], detail=args.detail)
            if result:
                results.append(result)
                all_results.append((provider, route, result))

        if results:
            print_summary(provider, route, results)
            if args.detail:
                for r in results:
                    print_detail(r)

    if not args.route and not args.provider:
        print_comparison(all_results)


if __name__ == '__main__':
    main()
