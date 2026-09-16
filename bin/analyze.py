#!/usr/bin/env python3
"""
Nighttrain Monitor — Unified analysis tool.

Combines anomaly detection (formerly train-analysis.py) with predictive
forecasting (formerly train-forecast.py) into a single entry point.

Usage:
  python3 bin/analyze.py [OPTIONS]

Modes:
  all         Full analysis (default: alert + sellout + anomaly)
  anomaly     Price anomalies across snapshots
  fill        Capacity fill curves
  sellout     Sellout prognosis
  booking     Optimal booking window (lead-time vs price)
  heatmap     Weekday price patterns
  alert       Tier deviation alerts (unusually cheap/expensive)
  predict     Prediction tracking only
  diff        Latest snapshot diff (quick day-over-day)

Options:
  --route R     Specific route (default: all EUR routes)
  --operator O  Filter by operator (es,leo,rdc,sj,snalltaget). Comma-separated for multiple.
  --date D      Specific travel date YYYY-MM-DD
  --mode M      Analysis mode (default: all)
  --all         Include past travel dates (default: future only)
  --top N       Top N results per section (default: 10)
  --since N     Only use last N days of snapshots (anomaly mode)
  -q, --quiet   Suppress progress messages
  -h, --help    Show this help
"""

import sys
import os

# Add parent dir to path for lib imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from lib import loaders, analysis, predictions, formatting


def main():
    args = sys.argv[1:]

    # Parse arguments
    route_filter = None
    operator_filter = None
    date_filter = None
    mode = 'all'
    future_only = True
    top_n = 10
    since_days = None
    quiet = False

    i = 0
    while i < len(args):
        if args[i] == '--route' and i + 1 < len(args):
            route_filter = args[i + 1]; i += 2
        elif args[i] == '--operator' and i + 1 < len(args):
            operator_filter = [o.strip() for o in args[i + 1].split(',')]; i += 2
        elif args[i] == '--date' and i + 1 < len(args):
            date_filter = args[i + 1]; i += 2
        elif args[i] == '--mode' and i + 1 < len(args):
            mode = args[i + 1]; i += 2
        elif args[i] == '--all':
            future_only = False; i += 1
        elif args[i] == '--top' and i + 1 < len(args):
            top_n = int(args[i + 1]); i += 2
        elif args[i] == '--since' and i + 1 < len(args):
            since_days = int(args[i + 1]); i += 2
        elif args[i] in ('-q', '--quiet'):
            quiet = True; i += 1
        elif args[i] in ('-h', '--help'):
            print(__doc__.strip())
            sys.exit(0)
        else:
            i += 1

    # Discover routes
    all_routes = loaders.get_all_routes()
    if operator_filter:
        all_routes = [(p, r) for p, r in all_routes if p in operator_filter]
    if route_filter:
        all_routes = [(p, r) for p, r in all_routes if route_filter in r]

    if not all_routes:
        filters = []
        if operator_filter:
            filters.append(f"operator={','.join(operator_filter)}")
        if route_filter:
            filters.append(f"route={route_filter}")
        hint = f" matching {' '.join(filters)}" if filters else ''
        print(f"No routes found{hint}.")
        sys.exit(1)

    from datetime import date as date_cls
    today = date_cls.today()

    if not quiet:
        print(f"Nighttrain Monitor — {today.isoformat()}")
        print(f"Routes: {len(all_routes)}, Mode: {mode}, "
              f"Filter: {'future only' if future_only else 'all dates'}")

    # Load all snapshots
    all_snapshots = {}
    for provider, route in all_routes:
        snapshots = loaders.load_all_snapshots(provider, route)
        if snapshots:
            all_snapshots[(provider, route)] = snapshots

    # === Prediction Tracking (always runs) ===
    pred_data = predictions.load()
    resolved = predictions.validate(pred_data, all_snapshots)

    if mode in ('all', 'predict'):
        formatting.section("PREDICTION TRACKING")
        formatting.print_prediction_results(resolved, pred_data)

    # === Per-route analysis ===
    all_new_preds = []

    for provider, route in all_routes:
        snapshots = all_snapshots.get((provider, route), [])
        if not snapshots:
            continue

        label = formatting.route_label(provider, route)

        # Anomaly
        if mode in ('all', 'anomaly'):
            formatting.section(f"{label} — ANOMALIES")
            anomalies = analysis.anomaly_scan(snapshots, future_only=future_only,
                                              since_days=since_days, provider=provider)
            formatting.print_anomaly_summary(anomalies, top_n)

        # Diff (day-over-day snapshot comparison)
        if mode == 'diff':
            formatting.section(f"{label} — DIFF (last 2 snapshots)")
            anomalies = analysis.anomaly_scan(snapshots, future_only=future_only,
                                              since_days=2, provider=provider)
            formatting.print_anomaly_summary(anomalies, top_n)

        # Fill curves (needed for sellout too)
        curves = None
        if mode in ('all', 'fill', 'sellout', 'predict'):
            curves = analysis.fill_curves(snapshots, future_only=future_only,
                                          target_date=date_filter)

        if mode in ('all', 'fill'):
            formatting.section(f"{label} — FILL CURVES")
            formatting.print_fill_summary(curves, top_n)

        if mode in ('all', 'sellout'):
            formatting.section(f"{label} — SELLOUT PROGNOSIS")
            formatting.print_sellout_predictions(curves, top_n)

        if mode in ('all', 'booking'):
            formatting.section(f"{label} — BOOKING WINDOW")
            window = analysis.booking_window(snapshots, future_only=future_only)
            formatting.print_booking_window(window)

        if mode in ('all', 'heatmap'):
            formatting.section(f"{label} — WEEKDAY HEATMAP")
            heatmap = analysis.weekday_heatmap(snapshots, future_only=future_only)
            formatting.print_weekday_heatmap(heatmap)

        if mode in ('all', 'alert'):
            formatting.section(f"{label} — TIER ALERTS")
            alerts = analysis.tier_alerts(snapshots, future_only=future_only)
            formatting.print_tier_alerts(alerts, top_n)

        # Generate new predictions
        if curves and mode in ('all', 'predict', 'sellout'):
            new_preds = predictions.create_sellout_predictions(curves, provider, route)
            all_new_preds.extend(new_preds)

    # Save predictions
    added = predictions.add_new(pred_data, all_new_preds)
    predictions.save(pred_data)

    if not quiet and added > 0:
        print(f"\n  📝 {added} new predictions saved.")

    # Summary
    if mode == 'all' and not quiet:
        formatting.section("SUMMARY")
        print(f"  Routes analyzed: {len(all_snapshots)}")
        print(f"  Open predictions: {len(pred_data['predictions'])}")
        stats = predictions.accuracy_stats(pred_data)
        if stats['correct'] + stats['wrong'] > 0:
            print(f"  Prediction accuracy: {stats['accuracy_pct']:.0f}%")
        print(f"\n  Modes: anomaly | fill | sellout | booking | heatmap | alert | predict")


if __name__ == '__main__':
    main()
