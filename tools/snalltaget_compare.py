"""
Snälltåget Snapshot Comparison Tool

Aggregates availability and pricing data across daily snapshots.
Auto-discovers files in data/snalltaget/ by route name.

Modes:
  diff       Compare latest two snapshots (price/capacity changes)
  trend      Track a travel date across all snapshots
  tiers      Analyze quota→price tier boundaries
  overshoot  Cross-route price comparison (same train, different destinations)
  inversion  Detect berth<seat pricing anomalies on transfer routes
  routes     List discovered routes

Usage:
  python snalltaget_compare.py diff [ROUTE]
  python snalltaget_compare.py trend ROUTE --date 2026-09-11
  python snalltaget_compare.py tiers [ROUTE]
  python snalltaget_compare.py overshoot [--date 2026-09-11]
  python snalltaget_compare.py inversion [ROUTE]
  python snalltaget_compare.py routes

Route names: berlin-stockholm, stockholm-berlin, hamburg-stockholm,
  stockholm-hamburg, berlin-malmoe, malmoe-berlin, dresden-stockholm,
  stockholm-dresden, etc.

Examples:
  python snalltaget_compare.py diff berlin-stockholm
  python snalltaget_compare.py trend stockholm-dresden --date 2026-09-11
  python snalltaget_compare.py tiers berlin-stockholm
  python snalltaget_compare.py overshoot
  python snalltaget_compare.py inversion berlin-stockholm
"""

import json
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from lib import loaders  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROVIDER = 'snalltaget'

# Product family display names and sort order
PRODUCT_ORDER = ['SPSF', 'SPFF', 'NTBSF', 'NTBFF', 'NTPCSF', 'NTPCFF', 'SPPCSF', 'SPPCFF']

PRODUCT_NAMES = {
    'SPSF': 'Seat',
    'SPFF': 'Seat-Flex',
    'NTBSF': 'Berth',
    'NTBFF': 'Berth-Flex',
    'NTPCSF': 'Compartment',
    'NTPCFF': 'Comp-Flex',
    'SPPCSF': 'SeatComp',
    'SPPCFF': 'SeatComp-Flex',
}

# Routes that share the same physical train (D 10300/10301)
# Station order = physical stop sequence of the train.
# Overshoot = booking a LONGER segment than needed and exiting early.
#
# Southbound D 10301: Stockholm → Hamburg → Berlin → Dresden
#   Valid overshoot: want Hamburg? Book to Berlin or Dresden (longer, exit at Hamburg)
#   The LONGER route must be CHEAPER for overshoot to work.
#
# Northbound D 10300: Dresden → Berlin → Hamburg → Stockholm
#   Valid overshoot: want Hamburg? Book to Stockholm (longer, exit at Hamburg)
#   Want Berlin? Book from Dresden (earlier origin, ride past).
#   BUT: boarding before your ticket origin is NOT valid (can't board at Hamburg
#   with a Berlin→Stockholm ticket). Only extending the DESTINATION works.

OVERSHOOT_GROUPS = {
    'southbound': {
        # D 10301: Stockholm → Hamburg → Berlin → Dresden
        # Routes go FROM Stockholm TO each station
        # Overshoot = book to a station FURTHER DOWN the line
        'routes': ['stockholm-hamburg', 'stockholm-berlin', 'stockholm-dresden'],
        'stop_order': ['stockholm', 'hamburg', 'berlin', 'dresden'],
        'direction': 'destination',  # overshoot by extending destination
    },
    'northbound': {
        # D 10300: Dresden → Berlin → Hamburg → Stockholm
        # Routes go FROM each station TO Stockholm
        # Overshoot = book FROM a station EARLIER on the line
        'routes': ['dresden-stockholm', 'berlin-stockholm', 'hamburg-stockholm'],
        'stop_order': ['dresden', 'berlin', 'hamburg', 'stockholm'],
        'direction': 'origin',  # overshoot by extending origin (earlier boarding station)
    },
}


def product_name(pfid):
    return PRODUCT_NAMES.get(pfid, pfid)


def sorted_products(products):
    known = [p for p in PRODUCT_ORDER if p in products]
    unknown = sorted(p for p in products if p not in PRODUCT_ORDER)
    return known + unknown


# === File Discovery ===

def discover_routes():
    """All Snälltåget routes via the shared loader."""
    return [r for (prov, r) in loaders.get_all_routes() if prov == PROVIDER]


def find_files(route):
    """Snapshot files for a route (delegates to lib.loaders)."""
    return loaders.find_files(PROVIDER, route)


def snap_date(path):
    return loaders.extract_date_from_filename(path)


def load_snapshot(path):
    # Raw load: overshoot/inversion/tiers need the Snälltåget bundle structure
    # (productFamilyId/quota) that the lib loader normalizes away.
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def bundles_dict(bundles):
    """Convert bundle list to {productFamilyId: price}."""
    return {b['productFamilyId']: b['price'] for b in bundles if b.get('price') is not None}


# ─── DIFF ────────────────────────────────────────────────────────────────────

def cmd_diff(args):
    route = args.get('route')
    if not route:
        routes = discover_routes()
        if not routes:
            print("No data found.")
            return
        route = routes[0]
        print(f"Using route: {route}")

    files = find_files(route)
    if len(files) < 2:
        print(f"Need at least 2 snapshots for diff, found {len(files)}.")
        return

    prev_path, curr_path = files[-2], files[-1]
    prev_date, curr_date = snap_date(prev_path), snap_date(curr_path)
    prev = load_snapshot(prev_path)
    curr = load_snapshot(curr_path)

    print(f"\nSnälltåget diff: {route}")
    print(f"  {prev_date} → {curr_date}")
    print("=" * 85)

    all_dates = sorted(set(list(prev.keys()) + list(curr.keys())))
    today = datetime.now().date().isoformat()

    changes = []
    new_dates = []
    gone_dates = []

    for dt in all_dates:
        if dt < today:
            continue
        p = prev.get(dt, {})
        c = curr.get(dt, {})
        p_has = 'direct' in p or 'transfer' in p
        c_has = 'direct' in c or 'transfer' in c

        if not p_has and c_has:
            new_dates.append(dt)
            continue
        if p_has and not c_has:
            gone_dates.append(dt)
            continue
        if not p_has and not c_has:
            continue

        # Compare direct bundles
        for section in ('direct', 'transfer'):
            p_bundles = bundles_dict(p.get(section, {}).get('bundles', []))
            c_bundles = bundles_dict(c.get(section, {}).get('bundles', []))
            prefix = 'T:' if section == 'transfer' else ''

            all_products = sorted(set(list(p_bundles.keys()) + list(c_bundles.keys())),
                                  key=lambda x: PRODUCT_ORDER.index(x) if x in PRODUCT_ORDER else 99)

            for prod in all_products:
                pp = p_bundles.get(prod)
                cp = c_bundles.get(prod)
                if pp and cp and pp != cp:
                    pct = ((cp - pp) / pp) * 100
                    changes.append((dt, f"{prefix}{product_name(prod)}", pp, cp, pct))
                elif pp and not cp:
                    changes.append((dt, f"{prefix}{product_name(prod)}", pp, None, -100))
                elif not pp and cp:
                    changes.append((dt, f"{prefix}{product_name(prod)}", None, cp, 100))

        # Calendar changes
        p_cal = p.get('calendar', {})
        c_cal = c.get('calendar', {})
        p_cap = p_cal.get('capacity')
        c_cap = c_cal.get('capacity')
        if p_cap is not None and c_cap is not None and p_cap != c_cap:
            changes.append((dt, 'CAPACITY', p_cap, c_cap, ((c_cap - p_cap) / max(p_cap, 1)) * 100))

    # Print results
    if changes:
        # Sort by absolute percentage change
        drops = [(dt, name, pp, cp, pct) for dt, name, pp, cp, pct in changes
                 if pct < -5 and name != 'CAPACITY']
        spikes = [(dt, name, pp, cp, pct) for dt, name, pp, cp, pct in changes
                  if pct > 5 and name != 'CAPACITY']
        cap_changes = [(dt, name, pp, cp, pct) for dt, name, pp, cp, pct in changes
                       if name == 'CAPACITY']

        if drops:
            print(f"\n  Price drops ({len(drops)}):")
            for dt, name, pp, cp, pct in sorted(drops, key=lambda x: x[4]):
                cp_s = f"{cp:.0f}" if cp else "SOLD"
                print(f"    {dt}  {name:<18} {pp:>7.0f} → {cp_s:>7}  ({pct:+.0f}%)")

        if spikes:
            print(f"\n  Price spikes ({len(spikes)}):")
            for dt, name, pp, cp, pct in sorted(spikes, key=lambda x: -x[4]):
                pp_s = f"{pp:.0f}" if pp else "NEW"
                print(f"    {dt}  {name:<18} {pp_s:>7} → {cp:>7.0f}  ({pct:+.0f}%)")

        if cap_changes:
            print(f"\n  Capacity changes ({len(cap_changes)}):")
            for dt, _, pp, cp, pct in sorted(cap_changes, key=lambda x: x[0]):
                print(f"    {dt}  {pp:>3.0f} → {cp:>3.0f}  ({pct:+.0f}%)")

    if new_dates:
        print(f"\n  New dates with service ({len(new_dates)}):")
        for dt in new_dates:
            print(f"    {dt}")

    if gone_dates:
        print(f"\n  Dates lost ({len(gone_dates)}):")
        for dt in gone_dates:
            print(f"    {dt}")

    if not changes and not new_dates and not gone_dates:
        print("\n  No changes.")

    print()


# ─── TREND ───────────────────────────────────────────────────────────────────

def cmd_trend(args):
    route = args.get('route')
    target_date = args.get('date')

    if not route or not target_date:
        print("Usage: snalltaget_compare.py trend ROUTE --date YYYY-MM-DD")
        return

    files = find_files(route)
    if not files:
        print(f"No files for route '{route}'.")
        return

    print(f"\nSnälltåget trend: {route} — {target_date}")
    print("=" * 100)

    # Collect data across snapshots
    rows = []  # (snap_date, calendar, direct_bundles, transfer_bundles)
    for f in files:
        sd = snap_date(f)
        data = load_snapshot(f)
        entry = data.get(target_date, {})
        if 'info' in entry or 'error' in entry:
            rows.append((sd, None, {}, {}))
            continue
        cal = entry.get('calendar', {})
        d_bundles = bundles_dict(entry.get('direct', {}).get('bundles', []))
        t_bundles = bundles_dict(entry.get('transfer', {}).get('bundles', []))
        rows.append((sd, cal, d_bundles, t_bundles))

    if not rows:
        print("  No data.")
        return

    # Discover all products across snapshots
    all_d_products = set()
    all_t_products = set()
    for _, _, db, tb in rows:
        all_d_products.update(db.keys())
        all_t_products.update(tb.keys())

    d_prods = sorted_products(all_d_products)
    t_prods = sorted_products(all_t_products)

    # Header
    print(f"\n  {'Snap':<10} {'Cap':>4} {'Quo':>4} {'Amount':>7}", end='')
    for p in d_prods:
        print(f" {product_name(p):>10}", end='')
    for p in t_prods:
        print(f" {'T:'+product_name(p):>12}", end='')
    print()
    print("  " + "-" * (28 + 11 * len(d_prods) + 13 * len(t_prods)))

    prev_d = {}
    prev_t = {}
    for sd, cal, db, tb in rows:
        cap = cal.get('capacity', '-') if cal else '-'
        quo = cal.get('quota', '-') if cal else '-'
        amt = cal.get('amount', '-') if cal else '-'
        cap_s = f"{cap:>4}" if isinstance(cap, (int, float)) else f"{cap:>4}"
        quo_s = f"{quo:>4}" if isinstance(quo, (int, float)) else f"{quo:>4}"
        amt_s = f"{amt:>7.0f}" if isinstance(amt, (int, float)) else f"{amt:>7}"

        print(f"  {sd:<10} {cap_s} {quo_s} {amt_s}", end='')

        for p in d_prods:
            v = db.get(p)
            pv = prev_d.get(p)
            if v is not None:
                marker = ''
                if pv is not None and v != pv:
                    marker = '▲' if v > pv else '▼'
                print(f" {v:>9.0f}{marker}", end='')
            else:
                print(f" {'—':>10}", end='')

        for p in t_prods:
            v = tb.get(p)
            pv = prev_t.get(p)
            if v is not None:
                marker = ''
                if pv is not None and v != pv:
                    marker = '▲' if v > pv else '▼'
                print(f" {v:>11.0f}{marker}", end='')
            else:
                print(f" {'—':>12}", end='')

        print()
        prev_d = db
        prev_t = tb

    print()


# ─── TIERS ───────────────────────────────────────────────────────────────────

def cmd_tiers(args):
    """Analyze quota→price tier relationships and cross-origin pricing.

    Three analyses:
    1. Tier jumps: when does the calendar price change? What was quota before?
    2. Cross-origin: same train, different cap/quota/price per boarding station
    3. Dead inventory: origins where low tier persists despite available capacity
    """
    route = args.get('route')

    print(f"\nSnälltåget Tier Analysis")
    print("=" * 95)

    # ── Part 1: Tier Jumps (per-route) ──

    target_routes = [route] if route else discover_routes()

    all_tier_prices = set()  # collect all observed tier price levels

    for rt in target_routes:
        files = find_files(rt)
        if len(files) < 2:
            continue

        observations = []
        for f in files:
            sd = snap_date(f)
            data = load_snapshot(f)
            for dt, entry in data.items():
                if 'info' in entry or 'error' in entry:
                    continue
                cal = entry.get('calendar', {})
                quota = cal.get('quota')
                amount = cal.get('amount')
                cap = cal.get('capacity')
                observations.append((dt, sd, quota, amount, cap))
                if amount:
                    all_tier_prices.add(amount)

        if not observations:
            continue

        by_date = defaultdict(list)
        for dt, sd, quota, amount, cap in observations:
            by_date[dt].append((sd, quota, amount, cap))

        tier_jumps = []
        for dt, snapshots in sorted(by_date.items()):
            snapshots.sort()
            for i in range(1, len(snapshots)):
                prev_sd, prev_q, prev_a, prev_c = snapshots[i - 1]
                curr_sd, curr_q, curr_a, curr_c = snapshots[i]
                if prev_a and curr_a and prev_a != curr_a:
                    tier_jumps.append({
                        'date': dt,
                        'prev_snap': prev_sd, 'curr_snap': curr_sd,
                        'prev_amount': prev_a, 'curr_amount': curr_a,
                        'prev_quota': prev_q, 'curr_quota': curr_q,
                        'prev_cap': prev_c, 'curr_cap': curr_c,
                        'direction': 'up' if curr_a > prev_a else 'down',
                    })

        if tier_jumps:
            print(f"\n  ─── TIER JUMPS: {rt} ({len(tier_jumps)}) ───")
            print(f"  {'Date':<12} {'Snap':>17} {'Amount':>17} {'Quota':>12} {'Cap':>10} {'Dir':>4}")
            print(f"  {'-'*75}")

            for tj in sorted(tier_jumps, key=lambda x: (x['date'], x['prev_snap'])):
                dir_marker = '▲' if tj['direction'] == 'up' else '▼'
                print(f"  {tj['date']:<12} {tj['prev_snap'][:8]}→{tj['curr_snap'][:8]} "
                      f"{tj['prev_amount']:>7.0f}→{tj['curr_amount']:>7.0f} "
                      f"{tj['prev_quota']:>5}→{tj['curr_quota']:>5} "
                      f"{tj['prev_cap']:>4}→{tj['curr_cap']:>4} "
                      f"  {dir_marker}")

            up_jumps = [tj for tj in tier_jumps if tj['direction'] == 'up']
            down_jumps = [tj for tj in tier_jumps if tj['direction'] == 'down']
            if up_jumps:
                avg_q = sum(tj['prev_quota'] for tj in up_jumps) / len(up_jumps)
                print(f"\n  ▲ Price increases ({len(up_jumps)}): avg quota before jump = {avg_q:.1f}")
            if down_jumps:
                avg_q = sum(tj['prev_quota'] for tj in down_jumps) / len(down_jumps)
                print(f"  ▼ Price decreases ({len(down_jumps)}): avg quota before drop = {avg_q:.1f}")

    # ── Part 1b: Per-Product Price Jumps ──

    for rt in target_routes:
        files = find_files(rt)
        if len(files) < 2:
            continue

        # Collect per-product prices across snapshots
        # {travel_date: [(snap_date, {product: price}, {product: price}, cap, quota)]}
        prod_obs = defaultdict(list)
        for f in files:
            sd = snap_date(f)
            data = load_snapshot(f)
            for dt, entry in data.items():
                if 'info' in entry or 'error' in entry:
                    continue
                cal = entry.get('calendar', {})
                d_prices = bundles_dict(entry.get('direct', {}).get('bundles', []))
                t_prices = bundles_dict(entry.get('transfer', {}).get('bundles', []))
                prod_obs[dt].append((sd, d_prices, t_prices,
                                     cal.get('capacity'), cal.get('quota')))

        product_jumps = []  # (date, section, product, prev_price, curr_price, prev_snap, curr_snap, pct)
        for dt, snapshots in sorted(prod_obs.items()):
            snapshots.sort()
            for i in range(1, len(snapshots)):
                prev_sd, prev_d, prev_t, _, _ = snapshots[i - 1]
                curr_sd, curr_d, curr_t, curr_cap, curr_q = snapshots[i]

                for section, prev_p, curr_p in [('direct', prev_d, curr_d),
                                                  ('transfer', prev_t, curr_t)]:
                    all_prods = set(list(prev_p.keys()) + list(curr_p.keys()))
                    for prod in all_prods:
                        pp = prev_p.get(prod)
                        cp = curr_p.get(prod)
                        if pp and cp and pp != cp:
                            pct = ((cp - pp) / pp) * 100
                            prefix = 'T:' if section == 'transfer' else ''
                            product_jumps.append({
                                'date': dt, 'product': f"{prefix}{product_name(prod)}",
                                'prev': pp, 'curr': cp, 'pct': pct,
                                'prev_snap': prev_sd, 'curr_snap': curr_sd,
                            })

        if product_jumps:
            # Group by product
            by_product = defaultdict(list)
            for pj in product_jumps:
                by_product[pj['product']].append(pj)

            print(f"\n  ─── PER-PRODUCT PRICE JUMPS: {rt} ───")

            for prod in sorted(by_product.keys()):
                jumps = by_product[prod]
                ups = [j for j in jumps if j['pct'] > 5]
                downs = [j for j in jumps if j['pct'] < -5]

                if not ups and not downs:
                    continue

                # Collect distinct price levels for this product
                prices = set()
                for j in jumps:
                    prices.add(j['prev'])
                    prices.add(j['curr'])
                sorted_prices = sorted(prices)

                print(f"\n  {prod}: {len(ups)}▲ {len(downs)}▼  "
                      f"Observed prices: {', '.join(f'{p:.0f}' for p in sorted_prices)} SEK")

                # Show significant jumps (>15%)
                big = [j for j in jumps if abs(j['pct']) > 15]
                if big:
                    for j in sorted(big, key=lambda x: (x['date'], x['prev_snap'])):
                        marker = '▲' if j['pct'] > 0 else '▼'
                        print(f"    {j['date']}  {j['prev_snap'][:8]}→{j['curr_snap'][:8]}  "
                              f"{j['prev']:>7.0f}→{j['curr']:>7.0f}  ({j['pct']:+.0f}%)  {marker}")

    # ── Part 2: Observed Tier Levels ──

    if all_tier_prices:
        print(f"\n\n  ─── OBSERVED PRICE TIERS (calendar 'amount' values) ───")
        sorted_tiers = sorted(all_tier_prices)
        print(f"  {len(sorted_tiers)} distinct levels: {', '.join(f'{t:.0f}' for t in sorted_tiers)} SEK")

    # ── Part 3: Cross-Origin Comparison (same physical train) ──

    train_groups = {
        'D 10300 northbound': {
            'routes': ['dresden-stockholm', 'berlin-stockholm', 'hamburg-stockholm'],
            'labels': ['Dresden', 'Berlin', 'Hamburg'],
        },
        'D 10301 southbound': {
            'routes': ['stockholm-dresden', 'stockholm-berlin', 'stockholm-hamburg'],
            'labels': ['Dresden', 'Berlin', 'Hamburg'],
        },
    }

    for train, group in train_groups.items():
        # Load latest snapshot per route
        latest = {}
        for rt, label in zip(group['routes'], group['labels']):
            files = find_files(rt)
            if files:
                latest[label] = load_snapshot(files[-1])

        if len(latest) < 2:
            continue

        # Collect dates with service on any origin
        all_dates = set()
        for data in latest.values():
            for dt, entry in data.items():
                if 'calendar' in entry:
                    all_dates.add(dt)

        today = datetime.now().date().isoformat()
        future_dates = sorted(d for d in all_dates if d >= today)

        if not future_dates:
            continue

        labels = [l for l in group['labels'] if l in latest]

        print(f"\n\n  ─── CROSS-ORIGIN: {train} ───")
        print(f"  Same physical train, different booking origin → different cap/quota/price.\n")
        hdr = f"  {'Date':<12}"
        for l in labels:
            hdr += f" {'cap':>4} {'quo':>4} {'amount':>7}  "
        print(hdr)
        sub = f"  {'':12}"
        for l in labels:
            sub += f" {l:>17}  "
        print(sub)
        print(f"  {'-' * (12 + 19 * len(labels))}")

        dead_inventory = []  # (date, label_cheap, label_expensive, cap_cheap, price_cheap, price_exp, saving)

        for dt in future_dates:
            cols = []
            prices = {}
            caps = {}
            for l in labels:
                entry = latest.get(l, {}).get(dt, {})
                cal = entry.get('calendar', {})
                if cal:
                    cap = cal.get('capacity', '-')
                    quo = cal.get('quota', '-')
                    amt = cal.get('amount', '-')
                    amt_s = f"{amt:.0f}" if isinstance(amt, (int, float)) else "-"
                    cap_s = f"{cap}" if isinstance(cap, (int, float)) else "-"
                    quo_s = f"{quo}" if isinstance(quo, (int, float)) else "-"
                    cols.append(f" {cap_s:>4} {quo_s:>4} {amt_s:>7}  ")
                    if isinstance(amt, (int, float)):
                        prices[l] = amt
                    if isinstance(cap, (int, float)):
                        caps[l] = cap
                else:
                    cols.append(f" {'—':>17}  ")

            # Flag rows with price differences
            marker = ""
            if len(prices) >= 2:
                p_vals = list(prices.values())
                if max(p_vals) > min(p_vals):
                    cheapest_l = min(prices, key=prices.get)
                    most_exp_l = max(prices, key=prices.get)
                    saving = prices[most_exp_l] - prices[cheapest_l]
                    marker = f" ← {cheapest_l} {saving:.0f} SEK cheaper"

                    # Track dead inventory: cheap origin with high capacity
                    cheap_cap = caps.get(cheapest_l, 0)
                    if cheap_cap >= 10 and saving >= 200:
                        dead_inventory.append((dt, cheapest_l, most_exp_l,
                                               cheap_cap, prices[cheapest_l],
                                               prices[most_exp_l], saving))

            print(f"  {dt:<12}{''.join(cols)}{marker}")

        # ── Part 4: Dead Inventory Summary ──
        if dead_inventory:
            print(f"\n  DEAD INVENTORY: {len(dead_inventory)} dates where a cheaper origin has ≥10 capacity")
            print(f"  These seats are likely unsold because travelers don't know to book this origin.\n")
            print(f"  {'Date':<12} {'Cheap':>8} {'Cap':>4} {'Price':>7} {'Expensive':>10} {'Price':>7} {'Gap':>8}")
            print(f"  {'-'*60}")
            for dt, cl, el, cap, cp, ep, sav in sorted(dead_inventory, key=lambda x: -x[6]):
                print(f"  {dt:<12} {cl:>8} {cap:>4} {cp:>7.0f} {el:>10} {ep:>7.0f} {sav:>+8.0f} SEK")

    print()

    print()


# ─── OVERSHOOT ───────────────────────────────────────────────────────────────

def cmd_overshoot(args):
    """Compare prices across destinations for the same physical train.

    Overshoot = booking a LONGER segment than needed, exit at your actual stop.

    Southbound (Stockholm → Hamburg → Berlin → Dresden):
      Want Hamburg? Book Stockholm→Berlin or →Dresden if cheaper. Exit at Hamburg.
      The ticket covers a LONGER route (further destination).

    Northbound (Dresden → Berlin → Hamburg → Stockholm):
      Want Stockholm from Hamburg? Book Dresden→Stockholm if cheaper.
      The ticket covers a LONGER route (earlier origin).
      NOTE: You must physically board at the ticket's origin station.
      So this only works if you're actually at the earlier station.
      More realistically: want Hamburg? Book to Stockholm if cheaper. Exit at Hamburg.
    """
    target_date = args.get('date')

    print(f"\nSnälltåget Overshoot Analysis — same train, different ticket")
    print("  Book a longer segment, exit at your actual destination, save money.")
    print("=" * 95)

    for group_name, group in OVERSHOOT_GROUPS.items():
        routes = group['routes']
        stop_order = group['stop_order']
        overshoot_type = group['direction']

        # Load latest snapshot for each route
        latest = {}
        for route in routes:
            files = find_files(route)
            if files:
                latest[route] = load_snapshot(files[-1])

        if len(latest) < 2:
            continue

        # Find all dates with data
        all_dates = set()
        for data in latest.values():
            for d, entry in data.items():
                if 'direct' in entry or 'transfer' in entry:
                    all_dates.add(d)

        if target_date:
            all_dates = {target_date} if target_date in all_dates else set()

        if not all_dates:
            continue

        # Build station index for ordering
        station_idx = {s: i for i, s in enumerate(stop_order)}

        def route_station(route):
            """Extract the variable station from a route name."""
            parts = route.split('-')
            if overshoot_type == 'destination':
                # stockholm-hamburg → hamburg
                return parts[-1]
            else:
                # hamburg-stockholm → hamburg
                return parts[0]

        def route_length(route):
            """Segment length index (higher = longer segment)."""
            station = route_station(route)
            return station_idx.get(station, 0)

        if overshoot_type == 'destination':
            origin = stop_order[0].title()
            header = f"{group_name.upper()}: {origin} → [{' / '.join(s.title() for s in stop_order[1:])}]"
            # Longer = further destination = higher index
            is_longer = lambda r1, r2: route_length(r1) > route_length(r2)
        else:
            dest = stop_order[-1].title()
            header = f"{group_name.upper()}: [{' / '.join(s.title() for s in stop_order[:-1])}] → {dest}"
            # Longer = earlier origin = LOWER index (e.g., Dresden < Berlin < Hamburg)
            is_longer = lambda r1, r2: route_length(r1) < route_length(r2)

        print(f"\n  ─── {header} ───")

        savings_found = []

        for dt in sorted(all_dates):
            if dt < datetime.now().date().isoformat():
                continue

            # Get direct prices for each route
            route_prices = {}
            for route in routes:
                entry = latest.get(route, {}).get(dt, {})
                if 'direct' in entry:
                    route_prices[route] = bundles_dict(entry['direct'].get('bundles', []))

            if len(route_prices) < 2:
                continue

            all_products = set()
            for prices in route_prices.values():
                all_products.update(prices.keys())

            for prod in sorted_products(all_products):
                prices_by_route = {r: p.get(prod) for r, p in route_prices.items()
                                   if p.get(prod) is not None}
                if len(prices_by_route) < 2:
                    continue

                # For each pair: if the LONGER segment is CHEAPER, that's overshoot
                for short_route, short_price in prices_by_route.items():
                    for long_route, long_price in prices_by_route.items():
                        if short_route == long_route:
                            continue
                        if not is_longer(long_route, short_route):
                            continue
                        if long_price < short_price:
                            saving = short_price - long_price
                            short_station = route_station(short_route).title()
                            long_station = route_station(long_route).title()

                            if overshoot_type == 'destination':
                                # "Want Hamburg? Book to Dresden instead"
                                actual_dest = short_station
                                book_to = long_station
                            else:
                                # "From Hamburg? Book from Dresden instead"
                                actual_dest = short_station
                                book_to = long_station

                            savings_found.append({
                                'date': dt,
                                'product': prod,
                                'actual': actual_dest,
                                'actual_price': short_price,
                                'book': book_to,
                                'book_price': long_price,
                                'saving': saving,
                            })

        if savings_found:
            savings_found.sort(key=lambda x: -x['saving'])

            if overshoot_type == 'destination':
                print(f"  Tip: Book to a FURTHER station. Exit at your actual stop.\n")
                print(f"  {'Date':<12} {'Product':<12} {'Want':>10} {'Price':>7} {'Book to':>10} {'Price':>7} {'Save':>8}")
            else:
                print(f"  Tip: Book from an EARLIER station. Board later (compartment stays reserved).\n")
                print(f"  {'Date':<12} {'Product':<12} {'From':>10} {'Price':>7} {'Book from':>10} {'Price':>7} {'Save':>8}")

            print(f"  {'-'*72}")
            shown = set()
            for s in savings_found[:40]:
                key = (s['date'], s['product'], s['actual'], s['book'])
                if key in shown:
                    continue
                shown.add(key)
                print(f"  {s['date']:<12} {product_name(s['product']):<12} "
                      f"{s['actual']:>10} {s['actual_price']:>7.0f} "
                      f"{s['book']:>10} {s['book_price']:>7.0f} "
                      f"{s['saving']:>+8.0f} SEK")
        else:
            print("\n  No overshoot savings found.")

    print()


# ─── INVERSION ───────────────────────────────────────────────────────────────

def cmd_inversion(args):
    """Detect berth<seat pricing inversions on transfer routes.

    On transfer routes (D 300+3940 / 3943+301), shared berths (NTBSF) can
    sometimes be cheaper than seats (SPSF) — counterintuitive since berths
    are normally the upgrade. This detects and tracks those inversions.
    """
    route = args.get('route')
    routes = [route] if route else discover_routes()

    print(f"\nSnälltåget Berth-Seat Inversion Detector")
    print("  Transfer routes only (D 300+3940 / 3943+301)")
    print("  Normal: Seat < Berth. Inversion: Berth < Seat")
    print("=" * 90)

    inversions = []

    for route in routes:
        files = find_files(route)
        for f in files:
            sd = snap_date(f)
            data = load_snapshot(f)
            for dt, entry in data.items():
                if 'info' in entry or 'error' in entry:
                    continue
                if dt < datetime.now().date().isoformat():
                    continue

                transfer = entry.get('transfer', {})
                t_bundles = bundles_dict(transfer.get('bundles', []))

                seat = t_bundles.get('SPSF')
                berth = t_bundles.get('NTBSF')

                if seat and berth and berth < seat:
                    diff = seat - berth
                    # Also check direct route prices for context
                    d_bundles = bundles_dict(entry.get('direct', {}).get('bundles', []))
                    d_seat = d_bundles.get('SPSF')

                    inversions.append({
                        'date': dt,
                        'route': route,
                        'snap': sd,
                        'seat': seat,
                        'berth': berth,
                        'saving': diff,
                        'direct_seat': d_seat,
                    })

    if inversions:
        # Deduplicate: show latest snap per (route, date)
        latest = {}
        for inv in inversions:
            key = (inv['route'], inv['date'])
            if key not in latest or inv['snap'] > latest[key]['snap']:
                latest[key] = inv

        by_route = defaultdict(list)
        for inv in latest.values():
            by_route[inv['route']].append(inv)

        for route in sorted(by_route.keys()):
            invs = sorted(by_route[route], key=lambda x: x['date'])
            print(f"\n  ─── {route} ({len(invs)} inversions) ───")
            print(f"  {'Date':<12} {'T:Seat':>8} {'T:Berth':>8} {'Save':>6} {'D:Seat':>8} {'Note'}")
            print(f"  {'-'*60}")
            for inv in invs:
                d_seat_s = f"{inv['direct_seat']:.0f}" if inv['direct_seat'] else "-"
                note = ""
                if inv['direct_seat'] and inv['berth'] < inv['direct_seat']:
                    note = f"T:Berth also < D:Seat ({inv['direct_seat']:.0f})"
                print(f"  {inv['date']:<12} {inv['seat']:>8.0f} {inv['berth']:>8.0f} "
                      f"{inv['saving']:>+6.0f} {d_seat_s:>8}  {note}")
    else:
        print("\n  No berth < seat inversions found in current data.")

    # Also show near-inversions (berth within 10% of seat)
    near = []
    for route in routes:
        files = find_files(route)
        if not files:
            continue
        data = load_snapshot(files[-1])
        for dt, entry in data.items():
            if 'info' in entry or 'error' in entry or dt < datetime.now().date().isoformat():
                continue
            t_bundles = bundles_dict(entry.get('transfer', {}).get('bundles', []))
            seat = t_bundles.get('SPSF')
            berth = t_bundles.get('NTBSF')
            if seat and berth and berth >= seat and (berth - seat) / seat < 0.10:
                near.append((route, dt, seat, berth, berth - seat))

    if near:
        print(f"\n  Near-inversions (berth within 10% of seat, latest snapshot):")
        for route, dt, seat, berth, diff in sorted(near, key=lambda x: x[3] - x[2]):
            print(f"    {route:<25} {dt}  Seat={seat:.0f}  Berth={berth:.0f}  gap={diff:.0f} SEK")

    print()


# ─── ROUTES ──────────────────────────────────────────────────────────────────

def cmd_routes(args):
    routes = discover_routes()
    print(f"\nDiscovered {len(routes)} routes:\n")
    for route in routes:
        files = find_files(route)
        if files:
            first = snap_date(files[0])
            last = snap_date(files[-1])
            # Count dates with actual service
            data = load_snapshot(files[-1])
            service = sum(1 for e in data.values()
                          if 'direct' in e or 'transfer' in e)
            print(f"  {route:<25} {len(files):>3} snapshots  ({first}–{last})  "
                  f"{service} service dates")
    print()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    argv = sys.argv[1:]

    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    cmd = argv[0]
    if cmd not in ('diff', 'trend', 'tiers', 'overshoot', 'inversion', 'routes'):
        cmd = 'diff'
        argv = ['diff'] + argv

    args = {
        'command': cmd,
        'route': None,
        'date': None,
        'since': None,
    }

    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--date' and i + 1 < len(argv):
            args['date'] = argv[i + 1]
            i += 2
        elif a == '--since' and i + 1 < len(argv):
            args['since'] = int(argv[i + 1])
            i += 2
        elif a in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        elif not a.startswith('-') and args['route'] is None:
            args['route'] = a
            i += 1
        else:
            i += 1

    return args


def main():
    args = parse_args()
    cmd = args['command']

    if cmd == 'diff':
        cmd_diff(args)
    elif cmd == 'trend':
        cmd_trend(args)
    elif cmd == 'tiers':
        cmd_tiers(args)
    elif cmd == 'overshoot':
        cmd_overshoot(args)
    elif cmd == 'inversion':
        cmd_inversion(args)
    elif cmd == 'routes':
        cmd_routes(args)


if __name__ == '__main__':
    main()
