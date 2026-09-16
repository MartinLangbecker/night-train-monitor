#!/usr/bin/env python3
"""
Unified Snapshot Comparison Tool (all providers)

Provider-agnostic diff / trend / anomaly analysis built on lib/loaders.py, which
normalizes every provider to {travel_date: {class: {capacity, price}}}. Replaces
the former per-provider compare tools and covers rdc + sj + snalltaget
which previously had no (or only partial) compare tooling.

Modes:
  diff       Compare the latest two snapshots (price/capacity changes per travel date)
  trend      Track one travel date across all snapshots
  anomaly    Price drops/spikes, sellouts, new availability (via lib.analysis)
  routes     List discovered routes per provider

Usage:
  python3 compare.py routes
  python3 compare.py diff  --provider sj  --route stockholm-malmoe
  python3 compare.py trend --provider rdc --route hamburg-stockholm --date 2026-09-23
  python3 compare.py anomaly --provider all --since 3
  python3 compare.py diff --provider leo --route weimar-przemysl-eur

Provider defaults to 'all' for routes/anomaly; diff/trend require an explicit route.
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from lib import loaders, analysis  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROVIDERS = ['es', 'leo', 'snalltaget', 'rdc', 'sj']


def fmt_price(p):
    return '—' if p is None else (f"{p:g}")


def resolve_targets(provider, route):
    """Return list of (provider, route) tuples to operate on."""
    if provider == 'all':
        targets = loaders.get_all_routes()
        if route:
            targets = [(p, r) for (p, r) in targets if r == route]
        return targets
    # single provider
    if route:
        return [(provider, route)]
    routes = [r for (p, r) in loaders.get_all_routes() if p == provider]
    return [(provider, r) for r in routes]


def cmd_routes(args):
    all_routes = loaders.get_all_routes()
    by_provider = {}
    for p, r in all_routes:
        by_provider.setdefault(p, []).append(r)
    for p in PROVIDERS:
        rs = sorted(by_provider.get(p, []))
        print(f"\n[{p.upper()}] {len(rs)} routes")
        for r in rs:
            snaps = loaders.load_all_snapshots(p, r)
            n = len(snaps)
            span = ''
            if snaps:
                span = f"  ({snaps[0]['snap_date']}–{snaps[-1]['snap_date']})"
            print(f"  {r:28s} {n:3d} snapshots{span}")


def cmd_diff(args):
    if not args.route:
        print("diff requires --route (and --provider unless a route is unique)")
        return
    for provider, route in resolve_targets(args.provider, args.route):
        snaps = loaders.load_all_snapshots(provider, route)
        if len(snaps) < 2:
            print(f"\n[{provider}] {route}: need ≥2 snapshots (have {len(snaps)})")
            continue
        prev, curr = snaps[-2], snaps[-1]
        print(f"\n{'=' * 70}")
        print(f"  [{provider.upper()}] diff: {route}")
        print(f"  {prev['snap_date']} → {curr['snap_date']}")
        print(f"{'=' * 70}")
        dates = sorted(set(list(prev['data'].keys()) + list(curr['data'].keys())))
        changes = 0
        for dt in dates:
            pc = prev['data'].get(dt, {})
            cc = curr['data'].get(dt, {})
            lines = []
            for cls in sorted(set(list(pc.keys()) + list(cc.keys()))):
                op = pc.get(cls, {}).get('price')
                np_ = cc.get(cls, {}).get('price')
                ocap = pc.get(cls, {}).get('capacity')
                ncap = cc.get(cls, {}).get('capacity')
                if op != np_ or ocap != ncap:
                    pchg = ''
                    if op is not None and np_ is not None and op != np_:
                        pct = (np_ - op) / op * 100 if op else 0
                        pchg = f"  {fmt_price(op)}→{fmt_price(np_)} ({pct:+.0f}%)"
                    elif op != np_:
                        pchg = f"  {fmt_price(op)}→{fmt_price(np_)}"
                    cchg = ''
                    if ocap != ncap:
                        cchg = f"  cap {ocap}→{ncap}"
                    lines.append(f"    {cls:22s}{pchg}{cchg}")
            if lines:
                changes += 1
                print(f"  {dt}")
                print('\n'.join(lines))
        if not changes:
            print("  No changes.")


def cmd_trend(args):
    if not args.route or not args.date:
        print("trend requires --route and --date")
        return
    for provider, route in resolve_targets(args.provider, args.route):
        snaps = loaders.load_all_snapshots(provider, route)
        if not snaps:
            print(f"\n[{provider}] {route}: no snapshots")
            continue
        print(f"\n{'=' * 70}")
        print(f"  [{provider.upper()}] trend: {route} — {args.date}")
        print(f"{'=' * 70}")
        # collect all classes seen for that date (ignore API-error markers)
        all_classes = []
        for s in snaps:
            entry = s['data'].get(args.date, {})
            if loaders.is_error_entry(entry):
                continue
            for cls in entry:
                if cls not in all_classes:
                    all_classes.append(cls)
        if not all_classes:
            print(f"  No data for travel date {args.date}")
            continue
        header = "  Snap        " + ' '.join(f"{c[:14]:>15s}" for c in all_classes)
        print(header)
        print("  " + "-" * (len(header) - 2))
        for s in snaps:
            entry = s['data'].get(args.date, {})
            if loaders.is_error_entry(entry):
                err = entry[loaders.ERROR_KEY]
                print(f"  {s['snap_date']}  (error: {err})")
                continue
            cells = []
            for c in all_classes:
                cell = entry.get(c, {})
                p = cell.get('price') if isinstance(cell, dict) else None
                cells.append(f"{fmt_price(p):>15s}")
            print(f"  {s['snap_date']}  " + ' '.join(cells))


def cmd_anomaly(args):
    targets = resolve_targets(args.provider, args.route)
    for provider, route in targets:
        snaps = loaders.load_all_snapshots(provider, route)
        if len(snaps) < 2:
            continue
        res = analysis.anomaly_scan(snaps, future_only=True, since_days=args.since,
                                    provider=provider)
        drops = res['price_drops']
        spikes = res['price_spikes']
        sellouts = res['sellouts']
        apps = res['appearances']
        sysmoves = res.get('system_moves', [])
        if not (drops or spikes or sellouts or apps or sysmoves):
            continue
        print(f"\n{'=' * 70}")
        print(f"  [{provider.upper()}] {route} — ANOMALIES")
        print(f"{'=' * 70}")
        if sysmoves:
            print(f"  System-wide tier moves ({len(sysmoves)}):")
            for snap, cls, direction, moved, active, _from, to_tier in sysmoves[:10]:
                arrow = "↓" if direction == 'down' else "↑"
                dest = f" → tier {to_tier}" if to_tier is not None else ""
                print(f"    [{snap}] {cls:22s} {arrow} {moved}/{active} dates{dest}")
        if drops:
            print(f"  Price drops ({len(drops)}):")
            for snap, dt, cls, old, new, pct, lead in drops[:10]:
                print(f"    [{snap}] {dt}  {cls:22s} {fmt_price(old)}→{fmt_price(new)} ({pct:+.0f}%) lead={lead}d")
        if spikes:
            print(f"  Price spikes ({len(spikes)}):")
            for snap, dt, cls, old, new, pct, lead in spikes[:10]:
                print(f"    [{snap}] {dt}  {cls:22s} {fmt_price(old)}→{fmt_price(new)} ({pct:+.0f}%) lead={lead}d")
        if sellouts:
            print(f"  Sellouts ({len(sellouts)}):")
            for snap, dt, classes, lead in sellouts[:10]:
                print(f"    [{snap}] {dt}  lost: {', '.join(classes)}  lead={lead}d")
        if apps:
            print(f"  New availability ({len(apps)}):")
            for snap, dt, classes, lead in apps[:10]:
                print(f"    [{snap}] {dt}  gained: {', '.join(classes)}  lead={lead}d")


class _NS:
    """Lightweight argparse.Namespace stand-in for interactive dispatch."""
    def __init__(self, provider=None, route=None, date=None, since=None):
        self.provider = provider
        self.route = route
        self.date = date
        self.since = since


def pick(prompt, options):
    """Numbered picker. Returns the selected value or None on abort."""
    print(f"\n  {prompt}\n")
    for i, (label, value) in enumerate(options, 1):
        print(f"    [{i}] {label}")
    print("    [q] Cancel\n")
    while True:
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if choice == 'q':
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][1]
        except ValueError:
            pass
        print(f"    Enter 1-{len(options)} or q")


def interactive():
    """Interactive menu when no arguments are given (all providers)."""
    all_routes = loaders.get_all_routes()
    if not all_routes:
        print("No snapshot data found.")
        return

    # Step 1: mode
    mode = pick("What do you want to do?", [
        ("Compare latest two snapshots (diff)", "diff"),
        ("Track a travel date over time (trend)", "trend"),
        ("Find anomalies / big changes (anomaly)", "anomaly"),
    ])
    if not mode:
        return

    if mode == 'anomaly':
        # anomaly can run across everything; offer all or a single provider
        prov_opts = [("All providers", "all")]
        prov_opts += [(p.upper(), p) for p in PROVIDERS
                      if any(pp == p for pp, _ in all_routes)]
        provider = pick("Which provider?", prov_opts)
        if not provider:
            return
        since = None
        try:
            s = input("  Only last N days? [blank = all]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if s:
            try:
                since = int(s)
            except ValueError:
                pass
        cmd_anomaly(_NS(provider=provider, since=since))
        return

    # diff / trend need a concrete (provider, route)
    route_opts = []
    for prov, route in all_routes:
        n = len(loaders.load_all_snapshots(prov, route))
        route_opts.append((f"[{prov}] {route} ({n} snaps)", (prov, route)))
    sel = pick("Which route?", sorted(route_opts, key=lambda o: o[0]))
    if not sel:
        return
    provider, route = sel

    if mode == 'diff':
        cmd_diff(_NS(provider=provider, route=route))
        return

    # trend: ask for a travel date, hint the available ones
    snaps = loaders.load_all_snapshots(provider, route)
    if snaps:
        dates = sorted(snaps[-1]['data'].keys())
        if dates:
            print(f"\n  Available travel dates: {dates[0]} to {dates[-1]} ({len(dates)} dates)")
    try:
        d = input("\n  Enter travel date (YYYY-MM-DD): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not d:
        return
    cmd_trend(_NS(provider=provider, route=route, date=d))


def main():
    # No arguments → interactive menu (handy for manual exploration).
    if len(sys.argv) == 1:
        interactive()
        return

    ap = argparse.ArgumentParser(description="Unified snapshot comparison (all providers)")
    ap.add_argument('mode', choices=['diff', 'trend', 'anomaly', 'routes'])
    ap.add_argument('--provider', default='all',
                    choices=PROVIDERS + ['all'],
                    help="Provider (default: all)")
    ap.add_argument('--route', help="Route name")
    ap.add_argument('--date', help="Travel date (YYYY-MM-DD) for trend mode")
    ap.add_argument('--since', type=int, help="Only snapshots from the last N days (anomaly)")
    args = ap.parse_args()

    if args.mode == 'routes':
        cmd_routes(args)
    elif args.mode == 'diff':
        cmd_diff(args)
    elif args.mode == 'trend':
        cmd_trend(args)
    elif args.mode == 'anomaly':
        cmd_anomaly(args)


if __name__ == '__main__':
    main()
