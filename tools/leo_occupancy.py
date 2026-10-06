#!/usr/bin/env python3
"""
leo_occupancy.py — Same-day (0 days lead) sold-seats estimate per LEO connection.

For every snapshot taken on day D, look at the travel date == D (the departure
leaving ~15-18h after the 00:01 cron). The API never exposes occupied/max_capacity
(both null), so "sold" is inferred as a LOWER BOUND:

    sold(class, route, date) = max_capacity_ref(class, route) - capacity_same_day

max_capacity_ref is the maximum capacity ever observed for that class+route over
the whole history (segment-correct — LEO sells per-segment contingents that exceed
the 69/54/20 physical seats on short legs, see docs/leo-express.md).

Physical totals (per train, docs): ECO 69, BUS 54, ECOSLEEPER 20, ECOSLEEPERLADY 20.
For the two sleeper classes the physical berth count is used as the reference
(5 compartments x 4 = 20): observed ECOSLEEPER capacity >20 from ~25 Sep is a
Lady->mixed compartment reshuffle inside the same car, not a longer train
(ECOSLEEPERLADY never exceeds 20). ECO/BUS use the observed max (segment
contingents legitimately exceed the physical seat count on short legs).

Caveats:
  - Lower bound: bookings before the first snapshot of a date are invisible.
  - 0-day snapshot = ~15-18h pre-departure; same-day last-minute sales are missed.
  - Aug inventory resets (14-15 Aug ECO, 26-27 Aug Sleeper) inflate the ECO/BUS
    observed max slightly; the sleeper clamp above sidesteps it for berths.
  - From 25 Sep the Lady class was abolished on all routes and ECOSLEEPER sells the
    full 40-berth pool (observed capacity up to 28). The fixed 20-berth sleeper
    reference therefore slightly understates sold seats for the ~10 same-day
    departures on/after 25 Sep (clamped at 0 when cap>20). Marginal on the overall
    average (dominated by pre-25-Sep departures); not corrected here. A time-aware
    reference (20+20 before 25 Sep, 40 after) would be needed for exact Oct figures.

Usage:
  python3 tools/leo_occupancy.py                      # all routes, summary
  python3 tools/leo_occupancy.py --route weimar-przemysl-eur --detail
  python3 tools/leo_occupancy.py --currency eur
"""
import json, glob, os, sys, argparse
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'leo')
DATA = os.path.abspath(DATA)
NOSRV = 'Auf dieser Strecke fahren wir nicht'
PHYSICAL = {'ECO': 69, 'BUS': 54, 'ECOSLEEPER': 20, 'ECOSLEEPERLADY': 20}
CLASS_ORDER = ['ECO', 'BUS', 'ECOSLEEPER', 'ECOSLEEPERLADY']


def entry_classes(val):
    """Return list of class dicts for a priced result, else None."""
    if isinstance(val, dict) and 'classes' in val:
        return val['classes']
    if isinstance(val, list) and val and isinstance(val[0], dict) and 'classes' in val[0]:
        return val[0]['classes']
    return None


def snapshots(route):
    out = []
    for f in sorted(glob.glob(os.path.join(DATA, f'*_{route}.json'))):
        snap = os.path.basename(f)[:8]  # YYYYMMDD
        try:
            obj = json.load(open(f))
        except Exception:
            continue
        out.append((snap, obj.get('results', {})))
    return out


def iso(snap):
    return f'{snap[:4]}-{snap[4:6]}-{snap[6:8]}'


def analyze(route):
    data = snapshots(route)
    if not data:
        return None
    # 1) reference max capacity per class over whole history
    max_ref = defaultdict(int)
    for _, res in data:
        for val in res.values():
            cls = entry_classes(val)
            if not cls:
                continue
            for c in cls:
                cap = c.get('capacity')
                if isinstance(cap, (int, float)):
                    max_ref[c['class']] = max(max_ref[c['class']], cap)
    # Sleeper classes have a fixed physical berth count (5 compartments x 4 = 20).
    # Observed capacity >20 for ECOSLEEPER (from ~25 Sep) is a Lady->mixed compartment
    # reshuffle inside the SAME car, not a longer train (Lady never exceeds 20).
    # Clamp the sleeper reference to physical berths so the reshuffle doesn't deflate
    # occupancy. ECO/BUS keep the observed max (per-segment contingents legitimately
    # exceed the physical seat count on short legs).
    for scls in ('ECOSLEEPER', 'ECOSLEEPERLADY'):
        if scls in max_ref:
            max_ref[scls] = PHYSICAL[scls]
    # 2) same-day departures: travel date == snapshot date
    rows = []  # (date, {class: (sold, cap_now, ref)})
    for snap, res in data:
        td = iso(snap)
        val = res.get(td)
        cls = entry_classes(val)
        if not cls:
            continue
        perclass = {}
        for c in cls:
            cap = c.get('capacity')
            if not isinstance(cap, (int, float)):
                continue
            ref = max_ref.get(c['class'], cap)
            sold = max(0, ref - cap)
            perclass[c['class']] = (sold, cap, ref)
        if perclass:
            rows.append((td, perclass))
    return {'route': route, 'max_ref': dict(max_ref), 'rows': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--route', help='single route, e.g. weimar-przemysl-eur')
    ap.add_argument('--currency', choices=['eur', 'czk'], default='eur')
    ap.add_argument('--detail', action='store_true', help='per-date table')
    args = ap.parse_args()

    if args.route:
        routes = [args.route]
    else:
        seen = set()
        for f in glob.glob(os.path.join(DATA, f'*-{args.currency}.json')):
            seen.add(os.path.basename(f)[9:-5])  # strip YYYYMMDD_ and .json
        routes = sorted(seen)

    print(f'Same-day (0-day lead) sold-seats estimate — LEO, {args.currency.upper()}')
    print('sold = max_observed_capacity(class,route) - capacity_on_departure_day')
    print('=' * 72)

    grand = defaultdict(lambda: [0, 0, 0])  # class -> [sum_sold, sum_ref, n_departures]
    for route in routes:
        a = analyze(route)
        if not a or not a['rows']:
            continue
        print(f'\n--- {route} ---  ({len(a["rows"])} same-day departures observed)')
        refstr = ' '.join(f'{k}:ref={a["max_ref"].get(k,0)}(phys {PHYSICAL.get(k,"?")})' for k in CLASS_ORDER if k in a['max_ref'])
        print(f'  Referenz-Kapazitaet (max beobachtet): {refstr}')
        per = defaultdict(lambda: [0, 0, 0])  # class -> [sum_sold, sum_ref, n]
        for td, pc in a['rows']:
            for cls, (sold, cap, ref) in pc.items():
                per[cls][0] += sold
                per[cls][1] += ref
                per[cls][2] += 1
                grand[cls][0] += sold
                grand[cls][1] += ref
                grand[cls][2] += 1
        for cls in CLASS_ORDER:
            if cls not in per:
                continue
            s, r, n = per[cls]
            avg_sold = s / n if n else 0
            avg_ref = r / n if n else 0
            pct = (avg_sold / avg_ref * 100) if avg_ref else 0
            print(f'    {cls:16s} n={n:2d}  Ø verkauft={avg_sold:5.1f}  Ø Kap={avg_ref:5.1f}  Auslastung={pct:4.0f}%')
        if args.detail:
            print('    --- pro Reisetag (Same-Day) ---')
            for td, pc in a['rows']:
                cells = ' '.join(f'{c}:{pc[c][0]:.0f}/{pc[c][2]:.0f}' for c in CLASS_ORDER if c in pc)
                print(f'      {td}: {cells}')

    print('\n' + '=' * 72)
    print('GESAMT (alle Routen, Same-Day):')
    for cls in CLASS_ORDER:
        if cls not in grand:
            continue
        s, r, n = grand[cls]
        pct = (s / r * 100) if r else 0
        print(f'  {cls:16s} n={n:3d} Abfahrten  Ø verkauft={s/n:5.1f}  Auslastung={pct:4.0f}%')


if __name__ == '__main__':
    main()
