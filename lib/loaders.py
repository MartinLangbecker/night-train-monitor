"""
Snapshot loading and file discovery for all operators.

Supported providers: es, leo, snalltaget, rdc, sj, nox

All loaders return a unified format:
  {travel_date: {class_name: {'capacity': int|None, 'price': float}}}
"""

import json
import glob
import os
from datetime import datetime


# === Path Configuration ===

def get_base_dir():
    """Get the nighttrain-monitor base directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir(provider):
    """Get data directory for a provider."""
    return os.path.join(get_base_dir(), 'data', provider)


# === File Discovery ===

def find_files(provider, route):
    """Find all snapshot files for a provider/route, sorted chronologically."""
    data_dir = get_data_dir(provider)
    pattern = os.path.join(data_dir, f'*_{route}.json')
    return sorted(glob.glob(pattern))


def extract_date_from_filename(filepath):
    """Extract YYYYMMDD from snapshot filename."""
    return os.path.basename(filepath)[:8]


def get_all_routes():
    """
    Discover all available routes.
    Returns list of (provider, route_name) tuples.
    """
    routes = set()

    # ES routes
    es_dir = get_data_dir('es')
    for f in glob.glob(os.path.join(es_dir, '*.json')):
        name = os.path.basename(f)[9:].replace('.json', '')
        if name != 'last-minute-deals':
            routes.add(('es', name))

    # LEO routes (EUR only by default — CZK is redundant for analysis)
    leo_dir = get_data_dir('leo')
    for f in glob.glob(os.path.join(leo_dir, '*-eur.json')):
        name = os.path.basename(f)[9:].replace('.json', '')
        routes.add(('leo', name))

    # Snälltåget routes
    sna_dir = get_data_dir('snalltaget')
    if os.path.isdir(sna_dir):
        for f in glob.glob(os.path.join(sna_dir, '*.json')):
            name = os.path.basename(f)[9:].replace('.json', '')
            if name not in ('cron',):
                routes.add(('snalltaget', name))

    # RDC routes
    rdc_dir = get_data_dir('rdc')
    if os.path.isdir(rdc_dir):
        for f in glob.glob(os.path.join(rdc_dir, '*.json')):
            name = os.path.basename(f)[9:].replace('.json', '')
            if name not in ('cron',):
                routes.add(('rdc', name))

    # SJ routes
    sj_dir = get_data_dir('sj')
    if os.path.isdir(sj_dir):
        for f in glob.glob(os.path.join(sj_dir, '*.json')):
            name = os.path.basename(f)[9:].replace('.json', '')
            if name not in ('cron',):
                routes.add(('sj', name))

    # NOX routes
    nox_dir = get_data_dir('nox')
    if os.path.isdir(nox_dir):
        for f in glob.glob(os.path.join(nox_dir, '*.json')):
            name = os.path.basename(f)[9:].replace('.json', '')
            if name not in ('cron',):
                routes.add(('nox', name))

    return sorted(routes)


def get_all_routes_all_currencies():
    """Like get_all_routes but includes CZK variants for LEO."""
    routes = set()
    for provider in ('es', 'leo', 'snalltaget', 'rdc', 'sj', 'nox'):
        data_dir = get_data_dir(provider)
        if not os.path.isdir(data_dir):
            continue
        for f in glob.glob(os.path.join(data_dir, '*.json')):
            name = os.path.basename(f)[9:].replace('.json', '')
            if name not in ('last-minute-deals', 'cron'):
                routes.add((provider, name))
    return sorted(routes)


# Marker key for travel dates whose API query returned an error (not a sellout).
ERROR_KEY = '__error__'


def is_error_entry(classes):
    """True if a travel-date entry is an API-error marker, not real class data."""
    return isinstance(classes, dict) and ERROR_KEY in classes


# === Snapshot Loading ===

def load_es_snapshot(filepath):
    """
    Load ES snapshot file.
    Returns: {travel_date: {class_type: {'capacity': int|None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.items():
        if isinstance(entry, dict) and 'error' in entry and 'classes' not in entry:
            result[dt] = {ERROR_KEY: entry['error']}
            continue
        if 'classes' not in entry:
            continue  # "no service" entries
        classes = {}
        for cls in entry['classes']:
            if cls['price'] is not None:
                classes[cls['type']] = {
                    'capacity': cls['free'],
                    'price': cls['price'],
                }
        if classes:
            result[dt] = classes
    return result


def load_leo_snapshot(filepath):
    """
    Load LEO snapshot file.
    Returns: {travel_date: {class_code: {'capacity': int|None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.get('results', {}).items():
        # API returned an error for this query (e.g. empty response) -> keep a
        # marker so anomaly detection can tell "data missing" from "sold out".
        if isinstance(entry, dict) and 'error' in entry and 'classes' not in entry:
            result[dt] = {ERROR_KEY: entry['error']}
            continue
        classes = {}
        for cls in entry.get('classes', []):
            if cls['price'] is not None:
                classes[cls['class']] = {
                    'capacity': cls['capacity'],
                    'price': cls['price'],
                }
        if classes:
            result[dt] = classes
    return result


# Snälltåget product family display names
SNALLTAGET_PRODUCT_NAMES = {
    'SPSF': 'Seat',
    'SPFF': 'Seat-Flex',
    'NTBSF': 'Berth',
    'NTBFF': 'Berth-Flex',
    'NTPCSF': 'Compartment',
    'NTPCFF': 'Compartment-Flex',
    'SPPCSF': 'SeatComp',
    'SPPCFF': 'SeatComp-Flex',
}


def load_snalltaget_snapshot(filepath):
    """
    Load Snälltåget snapshot file.

    Normalizes direct and transfer bundles into unified classes.
    Direct bundles are preferred; transfer bundles are included with a 'T:' prefix
    to distinguish them (transfer routes have additional products like shared berths).

    Returns: {travel_date: {class_name: {'capacity': int|None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.items():
        if 'info' in entry or 'error' in entry:
            continue

        classes = {}
        cal = entry.get('calendar', {})
        capacity = cal.get('capacity')  # global capacity (not per-class)

        # Direct bundles (D 10300/10301)
        direct = entry.get('direct', {})
        for b in direct.get('bundles', []):
            pfid = b['productFamilyId']
            price = b.get('price')
            if price is not None:
                name = SNALLTAGET_PRODUCT_NAMES.get(pfid, pfid)
                classes[name] = {'capacity': capacity, 'price': price}

        # Transfer bundles (D 300+3940 / 3943+301)
        # Prefixed with T: to distinguish from direct (same product can exist on both)
        transfer = entry.get('transfer', {})
        for b in transfer.get('bundles', []):
            pfid = b['productFamilyId']
            price = b.get('price')
            if price is not None:
                name = 'T:' + SNALLTAGET_PRODUCT_NAMES.get(pfid, pfid)
                # Only add transfer product if not already present as direct
                # (direct is preferred — same physical train, simpler journey)
                direct_name = SNALLTAGET_PRODUCT_NAMES.get(pfid, pfid)
                if direct_name not in classes:
                    classes[name] = {'capacity': capacity, 'price': price}
                else:
                    # Direct exists — still add transfer if price differs meaningfully
                    classes[name] = {'capacity': capacity, 'price': price}

        if classes:
            result[dt] = classes
    return result



def _rdc_capacity_from_tiers(tiers):
    """Extract capacity from RDC tier data.

    tier_jump_at - 1 = remaining places in current price tier.
    Backwards-compatible: checks both 'tier_jump_at' (new) and 'at_n' (old).
    Returns None if no tier data (meaning no jump detected = plenty of availability).
    """
    if not tiers:
        return None
    tier = tiers[0]
    jump = tier.get('tier_jump_at') or tier.get('at_n')
    if jump:
        return jump - 1
    return None

def load_rdc_snapshot(filepath):
    """
    Load RDC EuroNight snapshot file.

    Extracts Sparpreis (cheapest fare) per entity type.
    Entity types: Sitz, Liege, Bett, Bett 1. Klasse
    For entities with both single and cabin pricing, both are included.

    Returns: {travel_date: {class_name: {'capacity': int|None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.items():
        if 'info' in entry:
            continue

        classes = {}
        for entity in entry.get('entities', []):
            title = entity.get('title', '')

            # Extract cheapest single fare (Sparpreis preferred, then lowest)
            single_fares = entity.get('single', [])
            if single_fares:
                spar = next((f for f in single_fares if f.get('Title') == 'Sparpreis'), None)
                fare = spar or min(single_fares, key=lambda f: f['Price']['Amount'])
                price = fare['Price']['Amount']
                cap = _rdc_capacity_from_tiers(entity.get('single_tiers', []))
                classes[title] = {'capacity': cap, 'price': price}

            # Cabin pricing (whole compartment) — separate class
            cabin_fares = entity.get('cabin', [])
            if cabin_fares:
                spar = next((f for f in cabin_fares if f.get('Title') == 'Sparpreis'), None)
                fare = spar or min(cabin_fares, key=lambda f: f['Price']['Amount'])
                price = fare['Price']['Amount']
                cabin_name = f"{title} (Abteil)"
                cabin_cap = _rdc_capacity_from_tiers(entity.get('cabin_tiers', []))
                classes[cabin_name] = {'capacity': cabin_cap, 'price': price}

        if classes:
            result[dt] = classes
    return result



def load_sj_snapshot(filepath):
    """
    Load SJ night train snapshot file.

    Extracts NOFLEX price per seat class and bed comfort type.
    Uses tier_jump_at as capacity signal (tier_jump_at - 1 = remaining in tier).

    Returns: {travel_date: {class_name: {'capacity': int_or_None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.items():
        if 'info' in entry:
            continue

        classes = {}
        for dep in entry.get('departures', []):
            if dep.get('status', [None])[0] != 'AVAILABLE':
                continue

            # Seats: SECOND, SECOND_CALM, FIRST
            for cls, flexes in dep.get('seats', {}).items():
                nf = flexes.get('NOFLEX', {})
                price = nf.get('price')
                if price is not None:
                    jump = nf.get('tier_jump_at')
                    cap = (jump - 1) if jump else None
                    classes[f"Seat {cls}"] = {'capacity': cap, 'price': price}

            # Beds: COUCHETTE_SHARED, SLEEPER_SECOND_SHARED, etc.
            for ct, flexes in dep.get('beds', {}).items():
                nf = flexes.get('NOFLEX', {})
                price = nf.get('price')
                if price is not None:
                    jump = nf.get('tier_jump_at')
                    cap = (jump - 1) if jump else None
                    # Friendly names
                    name = ct.replace('_', ' ').title()
                    classes[name] = {'capacity': cap, 'price': price}

        if classes:
            result[dt] = classes

    return result


def load_nox_snapshot(filepath):
    """
    Load NOX Mobility snapshot file.

    NOX exposes real remaining capacity directly (availability.available), so
    capacity is exact — no tier reconstruction needed.

    Returns: {travel_date: {class_name: {'capacity': int|None, 'price': float}}}
    """
    with open(filepath) as f:
        raw = json.load(f)

    result = {}
    for dt, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        if '__error__' in entry:
            result[dt] = {ERROR_KEY: entry['__error__']}
            continue
        if 'info' in entry:
            continue  # "no service"
        available = entry.get('available')
        classes = {}
        for cls in entry.get('classes', []):
            price = cls.get('price')
            if price is not None:
                classes[cls['type']] = {'capacity': available, 'price': price}
        if classes:
            result[dt] = classes
    return result


def load_snapshot(provider, filepath):
    """Load a snapshot file using the appropriate provider loader."""
    if provider == 'es':
        return load_es_snapshot(filepath)
    elif provider == 'snalltaget':
        return load_snalltaget_snapshot(filepath)
    elif provider == 'rdc':
        return load_rdc_snapshot(filepath)
    elif provider == 'sj':
        return load_sj_snapshot(filepath)
    elif provider == 'nox':
        return load_nox_snapshot(filepath)
    else:
        return load_leo_snapshot(filepath)


def load_all_snapshots(provider, route):
    """
    Load all snapshots for a provider/route.
    Returns list of {'snap_date': 'YYYYMMDD', 'data': {travel_date: {class: {capacity, price}}}}
    """
    files = find_files(provider, route)
    snapshots = []
    for f in files:
        snap_date = extract_date_from_filename(f)
        data = load_snapshot(provider, f)
        if data:
            snapshots.append({'snap_date': snap_date, 'data': data})
    return snapshots
