"""
Analysis functions for nighttrain availability data.

All functions work on the unified snapshot format:
  snapshots = [{'snap_date': 'YYYYMMDD', 'data': {date: {class: {capacity, price}}}}]
"""

from datetime import datetime, timedelta, date
from collections import defaultdict
import math
import sys
from lib.loaders import is_error_entry
from lib import tiers


TODAY = date.today()

# A sellout is only credible if the previous snapshot's remaining capacity was
# at/below this. Larger drops to zero in one step signal a data gap.
SELLOUT_MAX_PREV_CAP = 10

# Step-aware anomaly thresholds (LEO and other step-priced operators).
# A single-tier move is normal (a booking climbs one tier, a cancellation drops
# one) and is NOT reported. Only jumps of this many tiers or more are flagged
# as an individual anomaly.
MIN_TIER_JUMP = 2

# A system-wide anomaly is when a large share of a route's active travel dates
# move in the SAME tier direction within one snapshot interval (e.g. a backend
# reset dropping every date back to T1). Requires both a minimum share and a
# minimum absolute count to avoid firing on tiny date sets.
SYSTEM_MOVE_SHARE = 0.50
SYSTEM_MOVE_MIN_DATES = 3


def fill_curves(snapshots, future_only=True, target_date=None):
    """
    Track capacity over snapshot time for each travel date/class.

    Returns:
      {travel_date: {class: [(snap_date, capacity, price, lead_days)]}}
    """
    curves = defaultdict(lambda: defaultdict(list))

    for snap in snapshots:
        snap_dt = datetime.strptime(snap['snap_date'], '%Y%m%d').date()
        for travel_date_str, classes in snap['data'].items():
            if is_error_entry(classes):
                continue
            try:
                travel_dt = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            if future_only and travel_dt < TODAY:
                continue
            if target_date and travel_date_str != target_date:
                continue
            lead_days = (travel_dt - snap_dt).days
            if lead_days < 0:
                continue
            for cls_name, cls_data in classes.items():
                capacity = cls_data['capacity']
                if capacity is None:
                    continue  # skip points without capacity (breaks regression math)
                curves[travel_date_str][cls_name].append((
                    snap['snap_date'],
                    capacity,
                    cls_data['price'],
                    lead_days,
                ))
    return dict(curves)


def sellout_prediction(curve_points):
    """
    Estimate days until sellout using linear regression on capacity decline.

    Args:
        curve_points: [(snap_date, capacity, price, lead_days)] for one class/date

    Returns:
        dict with days_to_sellout, confidence, decline_rate, current_capacity, data_points
        or None if insufficient data or no decline.
    """
    if len(curve_points) < 7:
        return None

    first_date = datetime.strptime(curve_points[0][0], '%Y%m%d').date()
    points = []
    for snap_date_str, cap, price, lead in curve_points:
        snap_dt = datetime.strptime(snap_date_str, '%Y%m%d').date()
        day_offset = (snap_dt - first_date).days
        points.append((day_offset, cap))

    # Weighted linear regression (exponential decay, halflife=7 days)
    n = len(points)
    max_day = points[-1][0]

    if n >= 5:
        halflife = getattr(sys.modules[__name__], '_BACKTEST_HALFLIFE', 14.0)
        lam = math.log(2) / halflife
        weights = [math.exp(-lam * (max_day - p[0])) for p in points]
    else:
        weights = [1.0] * n

    sum_w = sum(weights)
    sum_wx = sum(w * p[0] for w, p in zip(weights, points))
    sum_wy = sum(w * p[1] for w, p in zip(weights, points))
    sum_wxy = sum(w * p[0] * p[1] for w, p in zip(weights, points))
    sum_wx2 = sum(w * p[0] ** 2 for w, p in zip(weights, points))

    denom = sum_w * sum_wx2 - sum_wx ** 2
    if denom == 0:
        return None

    slope = (sum_w * sum_wxy - sum_wx * sum_wy) / denom
    intercept = (sum_wy - slope * sum_wx) / sum_w

    if slope >= 0:
        return None  # not declining

    # Weighted R²
    y_mean = sum_wy / sum_w
    ss_tot = sum(w * (p[1] - y_mean) ** 2 for w, p in zip(weights, points))
    ss_res = sum(w * (p[1] - (slope * p[0] + intercept)) ** 2 for w, p in zip(weights, points))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Days from last point to zero
    last_day = points[-1][0]
    current_cap = slope * last_day + intercept
    if slope == 0:
        return None
    days_to_zero = -current_cap / slope

    if days_to_zero < 0 or days_to_zero > 365:
        return None

    last_snap_date = datetime.strptime(curve_points[-1][0], '%Y%m%d').date()
    days_from_today = days_to_zero - (TODAY - last_snap_date).days
    if days_from_today < 0:
        days_from_today = 0

    return {
        'days_to_sellout': round(days_from_today, 1),
        'confidence': round(r_squared, 3),
        'decline_rate': round(-slope, 2),
        'current_capacity': round(current_cap),
        'data_points': n,
    }


def booking_window(snapshots, future_only=True):
    """
    Group prices by lead-time bucket and class.

    Returns:
      {class: [{'bucket': str, 'avg_price': float, 'min_price': float,
                'max_price': float, 'samples': int}]}
    """
    bucket_bounds = [3, 7, 14, 21, 30, 45, 60, 90, 999]
    bucket_labels = ['0-3d', '4-7d', '8-14d', '15-21d', '22-30d',
                     '31-45d', '46-60d', '61-90d', '91+d']

    data = defaultdict(lambda: defaultdict(list))

    for snap in snapshots:
        snap_dt = datetime.strptime(snap['snap_date'], '%Y%m%d').date()
        for travel_date_str, classes in snap['data'].items():
            if is_error_entry(classes):
                continue
            try:
                travel_dt = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            if future_only and travel_dt < TODAY:
                continue
            lead_days = (travel_dt - snap_dt).days
            if lead_days < 0:
                continue

            bucket_idx = next(
                (bi for bi, bound in enumerate(bucket_bounds) if lead_days <= bound), 0
            )
            for cls_name, cls_data in classes.items():
                data[cls_name][bucket_idx].append(cls_data['price'])

    result = {}
    for cls_name, buckets in sorted(data.items()):
        cls_result = []
        for bi in range(len(bucket_bounds)):
            prices = buckets.get(bi, [])
            if prices:
                cls_result.append({
                    'bucket': bucket_labels[bi],
                    'avg_price': round(sum(prices) / len(prices), 2),
                    'min_price': round(min(prices), 2),
                    'max_price': round(max(prices), 2),
                    'samples': len(prices),
                })
        result[cls_name] = cls_result
    return result


def weekday_heatmap(snapshots, future_only=True):
    """
    Aggregate price and capacity by travel-date weekday.

    Returns:
      {class: {weekday_name: {'avg_price': float, 'avg_capacity': float|None, 'count': int}}}
    """
    weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    data = defaultdict(lambda: defaultdict(lambda: {'prices': [], 'capacities': []}))

    for snap in snapshots:
        for travel_date_str, classes in snap['data'].items():
            if is_error_entry(classes):
                continue
            try:
                travel_dt = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            if future_only and travel_dt < TODAY:
                continue
            wd = travel_dt.weekday()
            for cls_name, cls_data in classes.items():
                data[cls_name][wd]['prices'].append(cls_data['price'])
                if cls_data['capacity'] is not None:
                    data[cls_name][wd]['capacities'].append(cls_data['capacity'])

    result = {}
    for cls_name in sorted(data.keys()):
        cls_result = {}
        for wd in range(7):
            d = data[cls_name][wd]
            if d['prices']:
                cls_result[weekday_names[wd]] = {
                    'avg_price': round(sum(d['prices']) / len(d['prices']), 2),
                    'avg_capacity': (round(sum(d['capacities']) / len(d['capacities']), 1)
                                     if d['capacities'] else None),
                    'count': len(d['prices']),
                }
        result[cls_name] = cls_result
    return result


def tier_alerts(snapshots, future_only=True, threshold=0.20):
    """
    Find travel dates where current price deviates significantly from
    the median price at the same lead-time bucket.

    Returns list of alert dicts sorted by deviation (cheapest first).
    """
    bucket_bounds = [7, 14, 21, 30, 45, 60, 90, 999]
    price_by_bucket = defaultdict(lambda: defaultdict(list))

    for snap in snapshots:
        snap_dt = datetime.strptime(snap['snap_date'], '%Y%m%d').date()
        for travel_date_str, classes in snap['data'].items():
            if is_error_entry(classes):
                continue
            try:
                travel_dt = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            lead_days = (travel_dt - snap_dt).days
            if lead_days < 0:
                continue
            bucket_idx = next(
                (bi for bi, bound in enumerate(bucket_bounds) if lead_days <= bound), 0
            )
            for cls_name, cls_data in classes.items():
                price_by_bucket[cls_name][bucket_idx].append(cls_data['price'])

    def median(lst):
        s = sorted(lst)
        n = len(s)
        if n == 0:
            return 0
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    medians = {
        cls: {bi: median(prices) for bi, prices in buckets.items()}
        for cls, buckets in price_by_bucket.items()
    }

    if not snapshots:
        return []

    latest = snapshots[-1]
    latest_dt = datetime.strptime(latest['snap_date'], '%Y%m%d').date()
    alerts = []

    for travel_date_str, classes in latest['data'].items():
        if is_error_entry(classes):
            continue
        try:
            travel_dt = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if future_only and travel_dt < TODAY:
            continue
        lead_days = (travel_dt - latest_dt).days
        if lead_days < 0:
            continue

        bucket_idx = next(
            (bi for bi, bound in enumerate(bucket_bounds) if lead_days <= bound), 0
        )

        for cls_name, cls_data in classes.items():
            expected = medians.get(cls_name, {}).get(bucket_idx)
            if not expected or expected == 0:
                continue
            deviation = (cls_data['price'] - expected) / expected
            if abs(deviation) >= threshold:
                alerts.append({
                    'travel_date': travel_date_str,
                    'class': cls_name,
                    'price': cls_data['price'],
                    'expected': round(expected, 2),
                    'deviation_pct': round(deviation * 100, 1),
                    'lead_days': lead_days,
                    'capacity': cls_data.get('capacity'),
                    'type': 'CHEAP' if deviation < 0 else 'EXPENSIVE',
                })

    alerts.sort(key=lambda a: a['deviation_pct'])
    return alerts


def anomaly_scan(snapshots, future_only=True, since_days=None, provider=None):
    """
    Detect pricing anomalies across consecutive snapshots.

    For step-priced operators (currently LEO) this is tier-aware: prices are
    mapped onto an empirically reconstructed tier ladder (surcharges absorbed),
    so single-tier moves (a booking or a cancellation) are treated as normal
    and suppressed. Only multi-tier jumps (>= MIN_TIER_JUMP), off-ladder prices,
    or system-wide correlated moves are reported. For operators without a usable
    ladder the classic percentage heuristic (drop < -5%, spike > 20%) applies.

    Returns dict with:
      'price_drops': [(snap_date, travel_date, class, old, new, pct, lead)]
      'price_spikes': [...]
      'sellouts': [(snap_date, travel_date, classes_lost, lead)]
      'appearances': [(snap_date, travel_date, classes_gained, lead)]
      'system_moves': [(snap_date, class, direction, moved, active, from_tier, to_tier)]
    """
    if since_days:
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime('%Y%m%d')
        snapshots = [s for s in snapshots if s['snap_date'] >= cutoff]

    if len(snapshots) < 2:
        return {'price_drops': [], 'price_spikes': [], 'sellouts': [],
                'appearances': [], 'system_moves': []}

    # Reconstruct tier ladders from the full history when the operator is
    # step-priced. Empty ladders (unknown/flat classes) make tier_delta return
    # None, which transparently falls back to the percentage heuristic.
    tier_aware = provider == 'leo'
    ladders = tiers.build_ladders(snapshots) if tier_aware else {}

    price_drops = []
    price_spikes = []
    sellouts = []
    appearances = []
    system_moves = []

    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]
        snap_date = curr['snap_date']
        snap_dt = datetime.strptime(snap_date, '%Y%m%d').date()

        # Per-interval tier-move tally (for system-wide anomaly detection).
        # class -> {'up': n, 'down': n, 'active': n, 'to': {tier_idx: count}}
        interval_moves = defaultdict(
            lambda: {'up': 0, 'down': 0, 'active': 0, 'to': defaultdict(int)})

        all_dates = sorted(set(list(prev['data'].keys()) + list(curr['data'].keys())))

        for dt in all_dates:
            travel_dt = None
            try:
                travel_dt = datetime.strptime(dt, '%Y-%m-%d').date()
                lead_days = (travel_dt - snap_dt).days
            except ValueError:
                lead_days = None

            if future_only and travel_dt is not None and travel_dt < TODAY:
                continue
            if lead_days is not None and lead_days < 0:
                continue

            prev_classes = prev['data'].get(dt, {})
            curr_classes = curr['data'].get(dt, {})

            # Skip dates whose API query errored in either snapshot: "data missing"
            # must not be mistaken for a sellout or a fresh appearance.
            if is_error_entry(prev_classes) or is_error_entry(curr_classes):
                continue

            # Sellout: was available, now gone. Only treat this as a real sellout
            # if the remaining capacity in the previous snapshot was low. A jump
            # from many free places to "completely gone" in one step is physically
            # impossible (capacity only moves via bookings/cancellations) and
            # indicates a scraper/API data gap, not a sellout.
            if prev_classes and not curr_classes:
                prev_caps = [c.get('capacity') for c in prev_classes.values()
                             if isinstance(c, dict) and c.get('capacity') is not None]
                max_prev_cap = max(prev_caps) if prev_caps else None
                if max_prev_cap is not None and max_prev_cap <= SELLOUT_MAX_PREV_CAP:
                    sellouts.append((snap_date, dt, list(prev_classes.keys()), lead_days))
                continue

            # Appearance: wasn't available, now is
            if not prev_classes and curr_classes:
                appearances.append((snap_date, dt, list(curr_classes.keys()), lead_days))
                continue

            # Price changes
            for cls_name in set(list(prev_classes.keys()) + list(curr_classes.keys())):
                old = prev_classes.get(cls_name, {}).get('price')
                new = curr_classes.get(cls_name, {}).get('price')
                if not (old and new and old != new):
                    continue
                pct = (new - old) / old * 100
                entry = (snap_date, dt, cls_name, old, new, round(pct, 1), lead_days)

                ladder = ladders.get(cls_name) if tier_aware else None
                delta = tiers.tier_delta(old, new, ladder) if ladder else None

                if delta is not None:
                    # On-ladder move: tally for system-wide detection, then
                    # only report individual jumps of MIN_TIER_JUMP tiers or more.
                    m = interval_moves[cls_name]
                    m['active'] += 1
                    if delta > 0:
                        m['up'] += 1
                    elif delta < 0:
                        m['down'] += 1
                    to_idx = tiers.tier_index(new, ladder)
                    if to_idx is not None:
                        m['to'][to_idx] += 1
                    if abs(delta) < MIN_TIER_JUMP:
                        continue  # single-tier move (booking/cancellation) — noise
                    if delta <= -MIN_TIER_JUMP:
                        price_drops.append(entry)
                    else:
                        price_spikes.append(entry)
                else:
                    # No usable ladder (other operators, or off-ladder price):
                    # fall back to the percentage heuristic.
                    if pct < -5:
                        price_drops.append(entry)
                    elif pct > 20:
                        price_spikes.append(entry)

        # After scanning all dates in this interval, flag system-wide moves:
        # a large share of a class's active dates moving in the same tier
        # direction (e.g. a backend reset dropping every date to T1).
        for cls_name, m in interval_moves.items():
            active = m['active']
            if active < SYSTEM_MOVE_MIN_DATES:
                continue
            for direction, moved in (('down', m['down']), ('up', m['up'])):
                if moved >= SYSTEM_MOVE_MIN_DATES and moved / active >= SYSTEM_MOVE_SHARE:
                    # Dominant destination tier among the moved dates (if any).
                    to_tier = max(m['to'], key=m['to'].get) if m['to'] else None
                    system_moves.append(
                        (snap_date, cls_name, direction, moved, active, None, to_tier))

    # Sort by magnitude
    price_drops.sort(key=lambda x: x[5])  # most negative first
    price_spikes.sort(key=lambda x: -x[5])  # most positive first

    return {
        'price_drops': price_drops,
        'price_spikes': price_spikes,
        'sellouts': sellouts,
        'appearances': appearances,
        'system_moves': system_moves,
    }