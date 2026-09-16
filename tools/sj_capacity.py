#!/usr/bin/env python3
"""
SJ Tier-Capacity Analysis

Tracks tier-capacity (places left before the next price tier) over snapshot time
for SJ night trains and turns it into booking/cancellation signals and, once
enough history exists, sellout forecasts.

WHAT "CAPACITY" MEANS HERE
--------------------------
SJ prices rise in tiers. The scraper finds the exact passenger count at which the
per-person price jumps (`tier_jump_at`) via binary search over n = 1..MAX_N.
`lib.loaders.load_sj_snapshot` exposes:

    capacity = tier_jump_at - 1   # seats/beds left in the CURRENT price tier

This is a LOWER BOUND on the true remaining capacity: after the tier boundary
there are usually more places in the next (more expensive) tier. So:

  * A capacity DROP between two snapshots = that many places were booked
    (or the tier boundary moved) since the previous snapshot.
  * capacity == None historically meant "> MAX_N places left, boundary not
    reached". On 2026-09-08 MAX_N was raised 9 -> 40, so from that date almost
    every available cell has a numeric capacity (boundary <= 40). Snapshots
    before 2026-09-08 have capacity == None for any tier with > 9 free places
    and MUST NOT be mixed into a decline regression (they look like missing data).

DATA MATURITY
-------------
  * 1 snapshot  -> current tier position only (use sj_tiers.py for that).
  * 2 snapshots -> day-over-day DELTA (bookings/cancellations). Available now.
  * >= 7 numeric points (post-2026-09-08) -> sellout regression via
    lib.analysis.sellout_prediction. Not enough history yet; the tool reports
    how many more days are needed per class.

USAGE
-----
  python3 tools/sj_capacity.py                      # delta, all SJ routes, latest 2 snaps
  python3 tools/sj_capacity.py stockholm-malmoe     # one route
  python3 tools/sj_capacity.py --min-drop 3         # only show drops >= 3
  python3 tools/sj_capacity.py --maturity           # data-readiness report per class
  python3 tools/sj_capacity.py --forecast           # sellout forecast where data allows
  python3 tools/sj_capacity.py --since 20260908     # only use snapshots >= this date

Only travel dates in the future are considered. Prices/capacities are SEK.
"""

import sys
import os
import argparse
from collections import defaultdict
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import loaders, analysis  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# The snapshot from which capacities >9 became measurable (MAX_N 9 -> 40).
EXTENDED_SINCE = '20260908'
# sellout_prediction needs at least this many numeric capacity points.
MIN_POINTS_FORECAST = 7

TODAY = date.today()


def sj_routes():
    return [r for p, r in loaders.get_all_routes() if p == 'sj']


def numeric_timelines(route, since=None):
    """
    Build per (travel_date, class) capacity timeline using only NUMERIC capacities.

    Returns: {(travel_date, class): [(snap_date, capacity, price, lead_days)]}
    Points with capacity == None are skipped (see module docstring).
    """
    snaps = loaders.load_all_snapshots('sj', route)
    timelines = defaultdict(list)
    for s in snaps:
        snap_str = s['snap_date']
        if since and snap_str < since:
            continue
        snap_dt = datetime.strptime(snap_str, '%Y%m%d').date()
        for tdate, classes in s['data'].items():
            if loaders.is_error_entry(classes):
                continue
            try:
                tdt = datetime.strptime(tdate, '%Y-%m-%d').date()
            except ValueError:
                continue
            if tdt < TODAY:
                continue
            lead = (tdt - snap_dt).days
            if lead < 0:
                continue
            for cls, cd in classes.items():
                cap = cd.get('capacity')
                if cap is None:
                    continue
                timelines[(tdate, cls)].append((snap_str, cap, cd.get('price'), lead))
    return timelines


def cmd_delta(routes, min_drop, since):
    """Day-over-day capacity change between the two latest snapshots."""
    any_output = False
    for route in routes:
        snaps = loaders.load_all_snapshots('sj', route)
        by = {s['snap_date']: s['data'] for s in snaps}
        snap_dates = sorted(d for d in by if not since or d >= since)
        if len(snap_dates) < 2:
            continue
        prev_s, curr_s = snap_dates[-2], snap_dates[-1]
        prev, curr = by[prev_s], by[curr_s]

        rows = []
        for tdate, classes in curr.items():
            if loaders.is_error_entry(classes):
                continue
            pclasses = prev.get(tdate, {})
            if loaders.is_error_entry(pclasses):
                pclasses = {}
            for cls, cd in classes.items():
                c1 = cd.get('capacity')
                c0 = (pclasses.get(cls) or {}).get('capacity')
                if c0 is None or c1 is None:
                    continue
                delta = c1 - c0
                if delta <= -min_drop:
                    rows.append((tdate, cls, c0, c1, delta, cd.get('price')))

        if not rows:
            continue
        any_output = True
        print(f"\n{'=' * 74}")
        print(f"  [SJ] {route}  capacity delta {prev_s} -> {curr_s}  (drops >= {min_drop})")
        print(f"{'=' * 74}")
        print(f"  {'Travel date':<12} {'Class':<28} {'was':>4} {'now':>4} {'chg':>4} {'price':>7}")
        print("  " + "-" * 66)
        for tdate, cls, c0, c1, delta, price in sorted(rows, key=lambda r: r[4]):
            ps = f"{price:>5.0f}" if price is not None else "    ?"
            print(f"  {tdate:<12} {cls:<28} {c0:>4} {c1:>4} {delta:>+4} {ps:>7}")
    if not any_output:
        print("No capacity drops at or above the threshold in the latest two snapshots.")


def cmd_maturity(routes, since):
    """Report how ready the data is for regression-based forecasting."""
    total_series = 0
    ready = 0
    hist = defaultdict(int)  # n_points -> count
    for route in routes:
        tls = numeric_timelines(route, since=since or EXTENDED_SINCE)
        for key, pts in tls.items():
            total_series += 1
            n = len(pts)
            hist[n] += 1
            if n >= MIN_POINTS_FORECAST:
                ready += 1

    print(f"\n{'=' * 60}")
    print(f"  [SJ] Capacity data maturity (numeric points, since {since or EXTENDED_SINCE})")
    print(f"{'=' * 60}")
    print(f"  (travel_date, class) series total : {total_series}")
    print(f"  ready for regression (>= {MIN_POINTS_FORECAST} pts) : {ready}")
    if total_series:
        max_n = max(hist) if hist else 0
        print(f"  longest series so far             : {max_n} points")
        days_needed = max(0, MIN_POINTS_FORECAST - max_n)
        if ready == 0:
            print(f"  -> ~{days_needed} more daily snapshots needed for the first forecast")
    print("\n  points-per-series histogram:")
    for n in sorted(hist):
        bar = '#' * min(hist[n], 50)
        print(f"    {n:>2} pts: {hist[n]:>5}  {bar}")


def cmd_forecast(routes, since):
    """Run sellout_prediction where enough numeric points exist."""
    found = 0
    for route in routes:
        tls = numeric_timelines(route, since=since or EXTENDED_SINCE)
        preds = []
        for (tdate, cls), pts in tls.items():
            pts_sorted = sorted(pts, key=lambda p: p[0])
            pred = analysis.sellout_prediction(pts_sorted)
            if pred:
                preds.append((tdate, cls, pred))
        if not preds:
            continue
        found += 1
        print(f"\n{'=' * 74}")
        print(f"  [SJ] {route}  sellout forecast")
        print(f"{'=' * 74}")
        for tdate, cls, p in sorted(preds, key=lambda x: x[2]['days_to_sellout']):
            print(f"  {tdate:<12} {cls:<28} ~{p['days_to_sellout']:>5} d "
                  f"(cap {p['current_capacity']}, -{p['decline_rate']}/d, R²={p['confidence']}, n={p['data_points']})")
    if not found:
        print(f"No class has >= {MIN_POINTS_FORECAST} numeric capacity points yet "
              f"(extended capacities exist only since {EXTENDED_SINCE}).")
        print("Run with --maturity to see how much history is still missing.")


def main():
    ap = argparse.ArgumentParser(description="SJ tier-capacity analysis")
    ap.add_argument('route', nargs='?', help="SJ route (default: all SJ routes)")
    ap.add_argument('--min-drop', type=int, default=1, help="Min capacity drop to show in delta mode")
    ap.add_argument('--since', help="Only use snapshots on/after this YYYYMMDD")
    ap.add_argument('--maturity', action='store_true', help="Data-readiness report")
    ap.add_argument('--forecast', action='store_true', help="Sellout forecast where data allows")
    args = ap.parse_args()

    routes = [args.route] if args.route else sj_routes()
    if not routes:
        print("No SJ routes found.")
        return

    if args.maturity:
        cmd_maturity(routes, args.since)
    elif args.forecast:
        cmd_forecast(routes, args.since)
    else:
        cmd_delta(routes, args.min_drop, args.since)


if __name__ == '__main__':
    main()
