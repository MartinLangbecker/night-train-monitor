#!/usr/bin/env python3
"""
Parameterized backtesting: run multiple variants and compare results.
"""

import sys
import os
import json
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import loaders, analysis, predictions
import glob


def get_snapshot_dates():
    dates = set()
    for provider in ('es', 'leo'):
        data_dir = loaders.get_data_dir(provider)
        for f in glob.glob(os.path.join(data_dir, '*.json')):
            d = os.path.basename(f)[:8]
            if d.isdigit() and len(d) == 8:
                dates.add(d)
    return sorted(dates)


def load_snapshots_up_to(provider, route, up_to_date):
    files = loaders.find_files(provider, route)
    snapshots = []
    for f in files:
        snap_date = loaders.extract_date_from_filename(f)
        if snap_date <= up_to_date:
            data = loaders.load_snapshot(provider, f)
            if data:
                snapshots.append({'snap_date': snap_date, 'data': data})
    return snapshots


def run_backtest(all_routes, snap_dates, params):
    """Run a single backtest with given parameters. Returns (pred_data, stats)."""
    supersede_days = params['supersede_days']
    halflife = params['halflife']
    min_points = params['min_points']

    pred_data = {'predictions': [], 'history': []}

    for day_idx, sim_date in enumerate(snap_dates):
        sim_today = datetime.strptime(sim_date, '%Y%m%d').date()
        predictions.TODAY = sim_today
        analysis.TODAY = sim_today

        # Load snapshots up to this date
        all_snapshots = {}
        for provider, route in all_routes:
            snapshots = load_snapshots_up_to(provider, route, sim_date)
            if snapshots:
                all_snapshots[(provider, route)] = snapshots

        # Validate
        predictions.validate(pred_data, all_snapshots)

        # Generate (only if enough days have passed)
        if day_idx >= min_points - 1:
            all_new_preds = []
            for provider, route in all_routes:
                snapshots = all_snapshots.get((provider, route), [])
                if len(snapshots) >= min_points:
                    curves = analysis.fill_curves(snapshots, future_only=True)
                    new_preds = predictions.create_sellout_predictions(curves, provider, route)
                    all_new_preds.extend(new_preds)

            # Use custom supersede threshold
            predictions.add_new(pred_data, all_new_preds,
                                supersede_days_threshold=supersede_days)

    # Final stats
    stats = predictions.accuracy_stats(pred_data)
    stats['still_open'] = len(pred_data['predictions'])
    outcome_counts = Counter(h.get('outcome') for h in pred_data['history'])
    stats['outcome_breakdown'] = dict(outcome_counts)

    # Restore
    predictions.TODAY = date.today()
    analysis.TODAY = date.today()

    return pred_data, stats


def main():
    all_routes = loaders.get_all_routes()
    snap_dates = get_snapshot_dates()

    variants = [
        {'name': 'A (current)', 'supersede_days': 2, 'halflife': 7.0, 'min_points': 3},
        {'name': 'B (stable)',  'supersede_days': 5, 'halflife': 14.0, 'min_points': 5},
        {'name': 'C (conservative)', 'supersede_days': 7, 'halflife': 14.0, 'min_points': 7},
    ]

    print(f"Backtesting {len(variants)} variants across {len(snap_dates)} days, {len(all_routes)} routes")
    print(f"Date range: {snap_dates[0]} — {snap_dates[-1]}")
    print()

    results = []

    for variant in variants:
        # Patch halflife in analysis module
        # We need to temporarily modify sellout_prediction behavior
        # Store original and patch
        original_halflife = 7.0  # default in code

        # Monkey-patch the halflife by modifying the function's behavior
        # Since halflife is hardcoded, we patch at the source
        analysis._BACKTEST_HALFLIFE = variant['halflife']

        print(f"  Running variant {variant['name']}...", end='', flush=True)
        pred_data, stats = run_backtest(all_routes, snap_dates, variant)
        results.append((variant, stats))
        print(f" done")

    # Comparison table
    print()
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    print(f"{'Variant':<20} {'Supersede':<10} {'Halflife':<10} {'MinPts':<8} "
          f"{'Accuracy':<10} {'Weighted':<10} {'Correct':<8} {'Wrong':<8} "
          f"{'Inval':<8} {'Super':<8} {'Open':<6}")
    print("-" * 116)

    for variant, stats in results:
        print(f"{variant['name']:<20} {variant['supersede_days']:<10} "
              f"{variant['halflife']:<10} {variant['min_points']:<8} "
              f"{stats['accuracy_pct']:<10} {stats['weighted_score']:<10} "
              f"{stats['correct']:<8} {stats['wrong']:<8} "
              f"{stats['invalidated']:<8} {stats['superseded']:<8} "
              f"{stats['still_open']:<6}")

    print()
    print("Outcome breakdown:")
    for variant, stats in results:
        print(f"\n  {variant['name']}:")
        for outcome, count in sorted(stats['outcome_breakdown'].items(), key=lambda x: -x[1]):
            print(f"    {outcome:<20} {count:4d}")


if __name__ == '__main__':
    main()
