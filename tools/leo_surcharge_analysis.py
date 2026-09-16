#!/usr/bin/env python3
"""
Surcharge Probe Analysis — Leo Express

Analyzes hourly snapshots from data/surcharge/ to pinpoint the exact time
when the weekend surcharge starts and ends.

Compares each snapshot's prices against canonical tier values.
Reports: timestamp, surcharge active (yes/no), multiplier, affected classes.

Usage:
  python3 leo-surcharge-analysis.py              # Full analysis
  python3 leo-surcharge-analysis.py --timeline   # Compact timeline view
  python3 leo-surcharge-analysis.py --raw        # Raw price table per snapshot
"""

import json
import glob
import os
import sys
from datetime import datetime
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'leo', 'surcharge')

# Canonical price tiers for Weimar→Przemyśl EUR (from USE-CASE.md)
CANONICAL_TIERS = {
    'ECO': [34.5, 51.6, 68.7, 102.9],
    'BUS': [25.0, 44.5, 67.0, 89.1, 133.7],
    'ECOSLEEPER': [37.5, 68.7, 102.9, 137.0, 205.8],
    'ECOSLEEPERLADY': [37.5, 68.7, 102.9, 137.0, 205.8],
}

# Tolerance for matching canonical tier (0.5 EUR)
TOLERANCE = 0.5


def load_snapshots():
    """Load all surcharge probe snapshots, sorted by timestamp."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, '*_weimar-przemysl-eur.json')))
    snapshots = []
    for f in files:
        basename = os.path.basename(f)
        # Extract timestamp from filename: 20260811_2223_weimar-przemysl-eur.json
        ts_part = basename.split('_weimar')[0]  # e.g. "20260811_2223"
        try:
            ts = datetime.strptime(ts_part, '%Y%m%d_%H%M')
        except ValueError:
            # Daily snapshot format: 20260811_weimar-przemysl-eur.json
            try:
                ts = datetime.strptime(ts_part, '%Y%m%d')
            except ValueError:
                continue

        with open(f) as fh:
            data = json.load(fh)

        snapshots.append({
            'timestamp': ts,
            'file': basename,
            'results': data.get('results', {}),
        })

    return snapshots


def find_nearest_tier(price, class_name):
    """Find the nearest canonical tier for a price. Returns (tier_price, deviation_pct)."""
    tiers = CANONICAL_TIERS.get(class_name, [])
    if not tiers:
        return None, None

    best_tier = min(tiers, key=lambda t: abs(t - price))
    deviation = (price - best_tier) / best_tier * 100
    return best_tier, deviation


def analyze_snapshot(snap):
    """Analyze a single snapshot for surcharge. Returns per-class surcharge info."""
    results = snap['results']
    class_deviations = defaultdict(list)

    for date_str, val in results.items():
        if 'classes' not in val:
            continue
        for cls_data in val['classes']:
            cls_name = cls_data['class']
            price = cls_data['price']
            if price is None:
                continue

            tier, deviation = find_nearest_tier(price, cls_name)
            if tier is not None and abs(deviation) > TOLERANCE:
                class_deviations[cls_name].append({
                    'date': date_str,
                    'price': price,
                    'nearest_tier': tier,
                    'deviation_pct': deviation,
                    'capacity': cls_data['capacity'],
                })

    return class_deviations


def compute_global_surcharge(snap):
    """Compute the median deviation across all classes and dates.
    Returns (is_surcharge, median_pct, sample_count)."""
    results = snap['results']
    deviations = []

    for date_str, val in results.items():
        if 'classes' not in val:
            continue
        for cls_data in val['classes']:
            cls_name = cls_data['class']
            price = cls_data['price']
            if price is None:
                continue

            tier, deviation = find_nearest_tier(price, cls_name)
            if tier is not None:
                deviations.append(deviation)

    if not deviations:
        return False, 0.0, 0

    med = sorted(deviations)[len(deviations) // 2]
    # Surcharge active if median deviation > 1%
    is_surcharge = med > 1.0
    return is_surcharge, med, len(deviations)


def print_timeline(snapshots):
    """Compact timeline: one line per snapshot showing surcharge status."""
    print(f"{'Timestamp':<18} {'Surcharge':<10} {'Median %':<10} {'Samples':<8} Status")
    print("-" * 65)

    prev_state = None
    for snap in snapshots:
        is_surcharge, med_pct, n_samples = compute_global_surcharge(snap)
        ts_str = snap['timestamp'].strftime('%Y-%m-%d %H:%M')

        state = "ON" if is_surcharge else "OFF"
        marker = ""
        if prev_state is not None and state != prev_state:
            marker = " ← CHANGE"
        prev_state = state

        indicator = "🔴" if is_surcharge else "🟢"
        print(f"{ts_str:<18} {indicator} {state:<7} {med_pct:>+6.1f}%    {n_samples:<8}{marker}")

    # Summary
    print()
    on_times = [s['timestamp'] for s in snapshots if compute_global_surcharge(s)[0]]
    off_times = [s['timestamp'] for s in snapshots if not compute_global_surcharge(s)[0]]

    if on_times and off_times:
        first_on = min(on_times)
        last_on = max(on_times)
        print(f"Surcharge window: {first_on.strftime('%a %H:%M')} — {last_on.strftime('%a %H:%M')}")
        print(f"Duration: ~{(last_on - first_on).total_seconds() / 3600:.0f}h")

        # Find transitions
        transitions = []
        for i in range(1, len(snapshots)):
            s1 = compute_global_surcharge(snapshots[i-1])[0]
            s2 = compute_global_surcharge(snapshots[i])[0]
            if s1 != s2:
                t1 = snapshots[i-1]['timestamp']
                t2 = snapshots[i]['timestamp']
                direction = "OFF→ON" if s2 else "ON→OFF"
                transitions.append((direction, t1, t2))

        if transitions:
            print(f"\nTransitions (between consecutive snapshots):")
            for direction, t1, t2 in transitions:
                print(f"  {direction}: between {t1.strftime('%a %H:%M')} and {t2.strftime('%a %H:%M')}")
    elif not on_times:
        print("No surcharge detected in any snapshot.")
    else:
        print("Surcharge active in ALL snapshots (no off-state captured).")


def print_raw(snapshots):
    """Raw price table: shows actual prices per class for a sample travel date."""
    # Pick a stable travel date (far future, likely same tier throughout)
    # Use a date ~30 days out that's in all snapshots
    sample_dates = None
    for snap in snapshots:
        dates_with_classes = [d for d, v in snap['results'].items() if 'classes' in v]
        if sample_dates is None:
            sample_dates = set(dates_with_classes)
        else:
            sample_dates &= set(dates_with_classes)

    if not sample_dates:
        print("No common travel dates across all snapshots.")
        return

    # Pick a date in the middle of the range
    common = sorted(sample_dates)
    sample_date = common[len(common) // 2]
    print(f"Sample travel date: {sample_date}")
    print()

    classes = ['ECO', 'BUS', 'ECOSLEEPER', 'ECOSLEEPERLADY']
    header = f"{'Timestamp':<18}" + "".join(f" {c:<16}" for c in classes)
    print(header)
    print("-" * len(header))

    for snap in snapshots:
        val = snap['results'].get(sample_date, {})
        if 'classes' not in val:
            continue

        prices = {c['class']: c['price'] for c in val['classes']}
        ts_str = snap['timestamp'].strftime('%Y-%m-%d %H:%M')
        row = f"{ts_str:<18}"
        for cls in classes:
            p = prices.get(cls)
            if p is not None:
                tier, dev = find_nearest_tier(p, cls)
                if abs(dev) > 1.0:
                    row += f" {p:>6.1f}(+{dev:.1f}%) "
                else:
                    row += f" {p:>6.1f}         "
            else:
                row += f" {'—':>6}         "
        print(row)


def print_full_analysis(snapshots):
    """Full analysis with details."""
    print_timeline(snapshots)
    print("\n" + "=" * 65)
    print("RAW PRICES (sample date)\n")
    print_raw(snapshots)


def main():
    snapshots = load_snapshots()

    if not snapshots:
        print(f"No snapshot files found in {DATA_DIR}")
        print("Probe runs Sa 16.08. 02:00 — Mo 18.08. 20:00 (hourly)")
        print("Check back after Saturday morning.")
        sys.exit(0)

    print(f"Surcharge Probe Analysis — {len(snapshots)} snapshots")
    print(f"Range: {snapshots[0]['timestamp']} — {snapshots[-1]['timestamp']}")
    print()

    if '--timeline' in sys.argv:
        print_timeline(snapshots)
    elif '--raw' in sys.argv:
        print_raw(snapshots)
    else:
        print_full_analysis(snapshots)


if __name__ == '__main__':
    main()
