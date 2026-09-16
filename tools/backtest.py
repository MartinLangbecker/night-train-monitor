#!/usr/bin/env python3
"""
Backtesting: replay all snapshots chronologically through the prediction system.

Simulates day-by-day operation:
  - For each snapshot date, pretend TODAY = that date
  - Load only snapshots up to and including that date
  - Run validate() on existing predictions
  - Run create_sellout_predictions() + add_new() with available data
  - Accumulate history

Result: a predictions dataset populated with real outcomes based on historical data.

Usage:
  python3 tools/backtest.py                 # dry run (DEFAULT): score only, write nothing
  python3 tools/backtest.py -o result.json  # write result to a file (live data untouched)
  python3 tools/backtest.py --write         # overwrite the live data/predictions.json

Safety: without -o or --write the run is a dry run and never touches the
production data/predictions.json.
"""

import sys
import os
import json
from datetime import datetime, date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import loaders, analysis, predictions


def get_snapshot_dates():
    """Find all unique snapshot dates across all providers."""
    dates = set()
    for provider in ('es', 'leo'):
        data_dir = loaders.get_data_dir(provider)
        import glob
        for f in glob.glob(os.path.join(data_dir, '*.json')):
            d = os.path.basename(f)[:8]
            if d.isdigit() and len(d) == 8:
                dates.add(d)
    return sorted(dates)


def load_snapshots_up_to(provider, route, up_to_date):
    """Load only snapshots with snap_date <= up_to_date."""
    files = loaders.find_files(provider, route)
    snapshots = []
    for f in files:
        snap_date = loaders.extract_date_from_filename(f)
        if snap_date <= up_to_date:
            data = loaders.load_snapshot(provider, f)
            if data:
                snapshots.append({'snap_date': snap_date, 'data': data})
    return snapshots


def main(output_path=None, dry_run=False):
    all_routes = loaders.get_all_routes()
    snap_dates = get_snapshot_dates()

    print(f"Backtesting: {len(snap_dates)} snapshot dates, {len(all_routes)} routes")
    print(f"Date range: {snap_dates[0]} — {snap_dates[-1]}")
    print()

    # Start fresh
    pred_data = {'predictions': [], 'history': []}

    # Need at least 3 days of data before predictions make sense
    min_snapshots_for_prediction = 3

    for day_idx, sim_date in enumerate(snap_dates):
        sim_today = datetime.strptime(sim_date, '%Y%m%d').date()

        # Monkey-patch TODAY in the predictions and analysis modules
        predictions.TODAY = sim_today
        analysis.TODAY = sim_today

        # Load snapshots up to this date for all routes
        all_snapshots = {}
        for provider, route in all_routes:
            snapshots = load_snapshots_up_to(provider, route, sim_date)
            if snapshots:
                all_snapshots[(provider, route)] = snapshots

        # Step 1: Validate existing predictions against current data
        resolved = predictions.validate(pred_data, all_snapshots)

        # Step 2: Generate new predictions (only if we have enough data)
        if day_idx >= min_snapshots_for_prediction - 1:
            all_new_preds = []
            for provider, route in all_routes:
                snapshots = all_snapshots.get((provider, route), [])
                if len(snapshots) >= min_snapshots_for_prediction:
                    curves = analysis.fill_curves(snapshots, future_only=True)
                    new_preds = predictions.create_sellout_predictions(curves, provider, route)
                    all_new_preds.extend(new_preds)

            added = predictions.add_new(pred_data, all_new_preds)
        else:
            added = 0

        # Progress
        n_open = len(pred_data['predictions'])
        n_hist = len(pred_data['history'])
        n_resolved = len(resolved)

        resolved_str = ""
        if n_resolved:
            outcomes = defaultdict(int)
            for r in resolved:
                outcomes[r.get('outcome', '?')] += 1
            resolved_str = " | resolved: " + ", ".join(f"{v}x {k}" for k, v in sorted(outcomes.items()))

        print(f"  {sim_date} | open={n_open:4d} | history={n_hist:3d} | +{added} new{resolved_str}")

    # Final stats
    print()
    print("=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)

    stats = predictions.accuracy_stats(pred_data)
    print(f"\n  Total predictions created & resolved: {stats['total']}")
    print(f"  Correct: {stats['correct']} (exact + late)")
    print(f"  Wrong: {stats['wrong']} (trend + reversal)")
    print(f"  Invalidated: {stats['invalidated']}")
    print(f"  Superseded: {stats['superseded']}")
    print(f"  Expired: {stats['expired']}")
    print(f"\n  Binary accuracy: {stats['accuracy_pct']}%")
    print(f"  Weighted score: {stats['weighted_score']}%")
    print(f"\n  Still open: {len(pred_data['predictions'])}")

    # Breakdown by outcome
    print("\n  Outcome details:")
    from collections import Counter
    outcome_counts = Counter(h.get('outcome') for h in pred_data['history'])
    for outcome, count in sorted(outcome_counts.items(), key=lambda x: -x[1]):
        print(f"    {outcome:<20} {count:4d}")

    # Persist result (or not, in dry-run)
    if dry_run:
        print("\n  Dry run — nothing written. "
              "Use -o PATH to save, or --write to overwrite the live file.")
    else:
        target = output_path or predictions.get_predictions_file()
        predictions.save(pred_data, target)
        print(f"\n  Saved to {target}")

    # Restore TODAY
    predictions.TODAY = date.today()
    analysis.TODAY = date.today()


def _parse_args():
    import argparse
    ap = argparse.ArgumentParser(
        description="Replay all snapshots through the prediction system and score accuracy.")
    ap.add_argument('-o', '--output', metavar='PATH',
                    help="Write the backtest result to PATH instead of the live predictions.json.")
    ap.add_argument('--write', action='store_true',
                    help="Overwrite the live data/predictions.json (production file).")
    ap.add_argument('--dry-run', action='store_true',
                    help="Run and score, but write nothing. This is the DEFAULT when neither "
                         "-o nor --write is given.")
    return ap.parse_args()


if __name__ == '__main__':
    _args = _parse_args()
    # Safe default: if the user gives neither an output path nor --write,
    # do not touch the production file.
    _dry = _args.dry_run or (not _args.output and not _args.write)
    if _args.output and _args.write:
        print("Warning: -o given, ignoring --write (writing only to the output path).")
    main(output_path=_args.output, dry_run=_dry)
