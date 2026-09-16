#!/usr/bin/env python3
"""
European Sleeper Last-Minute Deals

Compares last-minute deal prices (from europeansleeper.eu landing pages, scraped
by scrapers/es_last_minute.py into *_last-minute-deals.json) against the regular
availability prices, sorted by savings. ES-specific: only European Sleeper offers
these last-minute landing pages, and they can be substantially cheaper than the
regular fare — a genuine feature of the ES tariff system.

Data sources:
  - Regular prices: data/es/YYYYMMDD_<route>.json (raw ES snapshot)
  - Deals:          data/es/YYYYMMDD_last-minute-deals.json (separate scraper)

Usage:
  python3 es_deals.py hamburg-paris
  python3 es_deals.py routes            # list routes that have a deal landing page
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from lib import loaders  # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROVIDER = 'es'
DATA_DIR = loaders.get_data_dir(PROVIDER)

# ES route -> last-minute landing page slug on europeansleeper.eu.
# Pages are named by a different origin/destination than the tracked route.
ROUTE_TO_DEAL_SLUG = {
    'hamburg-paris': 'brussels-paris',       # train 474
    'paris-hamburg': 'hamburg-berlin',       # train 475
    'bruxelles-praha': 'berlin-prague',      # train 453 (page named by destination)
    'praha-bruxelles': 'amsterdam-brussels', # train 454 (page named by destination)
    # bruxelles-milano / milano-bruxelles: no last-minute landing page exists
}


def load_raw_snapshot(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_entry(results, date):
    entry = results.get(date, {})
    if 'info' in entry or 'error' in entry or not entry.get('classes'):
        return None
    return entry


def classes_to_dict(entry):
    if not entry:
        return {}
    return {c['type']: c for c in entry.get('classes', [])}


def find_latest_deals_file():
    """Find the most recent last-minute-deals JSON file."""
    files = sorted(f for f in os.listdir(DATA_DIR)
                   if f.endswith('_last-minute-deals.json'))
    return os.path.join(DATA_DIR, files[-1]) if files else None


def load_deals_for_route(route):
    """Load last-minute deals relevant to a route.
    Returns ({date: {shared: price, private: price}}, deals_file)."""
    deals_file = find_latest_deals_file()
    if not deals_file:
        return {}, None

    slug = ROUTE_TO_DEAL_SLUG.get(route)
    if not slug:
        return {}, deals_file

    with open(deals_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = {}
    for page in data.get('pages', []):
        if page['slug'] == slug:
            for d in page.get('shared', []):
                result.setdefault(d['date'], {})['shared'] = d['price']
            for d in page.get('private', []):
                result.setdefault(d['date'], {})['private'] = d['price']
            break
    return result, deals_file


def cmd_deals(route):
    files = loaders.find_files(PROVIDER, route)
    if not files:
        print(f"No availability files found for route '{route}'")
        return

    latest_data = load_raw_snapshot(files[-1])
    snap_date = loaders.extract_date_from_filename(files[-1])

    deals, deals_file = load_deals_for_route(route)
    if not deals:
        print(f"No last-minute deals found for route '{route}'")
        slug = ROUTE_TO_DEAL_SLUG.get(route, '?')
        print(f"  (looking for deal slug '{slug}' in latest *_last-minute-deals.json)")
        return

    deals_date = loaders.extract_date_from_filename(deals_file) if deals_file else '?'

    print("Last-Minute Deals vs Regular Prices")
    print(f"Route: {route}")
    print(f"Availability snapshot: {snap_date} | Deals snapshot: {deals_date}")
    print()

    rows = []
    for date in sorted(deals.keys()):
        entry = get_entry(latest_data, date)
        regular_couchette = None
        regular_private = None
        if entry:
            cd = classes_to_dict(entry)
            couch = cd.get('couchette-5')
            if couch and couch.get('price'):
                regular_couchette = couch['price']
            priv = cd.get('couchette-5-private')
            if priv and priv.get('price'):
                regular_private = priv['price']

        deal_shared = deals[date].get('shared')
        deal_private = deals[date].get('private')

        if deal_shared:
            saving = regular_couchette - deal_shared if regular_couchette else None
            saving_pct = (saving / regular_couchette * 100) if saving and regular_couchette else None
            rows.append((date, 'Couchette', regular_couchette, deal_shared, saving, saving_pct))
        if deal_private:
            saving = regular_private - deal_private if regular_private else None
            saving_pct = (saving / regular_private * 100) if saving and regular_private else None
            rows.append((date, 'Couchette Priv', regular_private, deal_private, saving, saving_pct))

    rows.sort(key=lambda r: r[5] if r[5] is not None else 0, reverse=True)

    print(f"  {'Date':<12} {'Class':<16} {'Regular':>8} {'Deal':>8} {'Saving':>8} {'%':>5}")
    print(f"  {'─'*12} {'─'*16} {'─'*8} {'─'*8} {'─'*8} {'─'*5}")
    for date, cls, regular, deal, saving, pct in rows:
        reg_str = f"{regular:.0f}\u20ac" if regular else "\u2014"
        deal_str = f"{deal:.0f}\u20ac"
        if saving and saving > 0:
            sav_str = f"-{saving:.0f}\u20ac"
            pct_str = f"-{pct:.0f}%"
        else:
            sav_str = "\u2014"
            pct_str = "\u2014"
        print(f"  {date:<12} {cls:<16} {reg_str:>8} {deal_str:>8} {sav_str:>8} {pct_str:>5}")


def cmd_routes():
    print("ES routes with a last-minute deal landing page:\n")
    for route, slug in ROUTE_TO_DEAL_SLUG.items():
        print(f"  {route:20s} → deal page '{slug}'")


def main():
    args = sys.argv[1:]
    if not args or args[0] == 'routes':
        cmd_routes()
        return
    cmd_deals(args[0])


if __name__ == '__main__':
    main()
