"""
European Sleeper Availability Monitor
Queries search/trains + search/availability for a date range and shows
free seats, prices per accommodation type, and fare levels.

Usage:
  python es-availability.py [from] [to] [--days N] [--json] [-o FILE] [-q] [--currency C]

Positional args:
  from      Origin station (default: bruxelles = Bruxelles-Midi)
  to        Destination station (default: praha = Praha hl.n.)

Options:
  --days N        Query N days starting from today (default: rest of month)
  --json          Save results to auto-named file
  -o, --output F  Save results to specified file (implies --json)
  -q, --quiet     Suppress console output (errors still go to stderr)
  --currency C    Currency: eur, czk, gbp, jpy, usd (default: eur)
  --diff          Compare with previous snapshot and highlight changes
  -h, --help      Show this help

Station matching:
  - Short aliases (hamburg, paris, bruxelles, praha, etc.) resolved automatically
  - EVA numbers (e.g. 8800104) matched exactly
  - Names matched case-insensitively: exact first, then substring

The route is auto-detected from the station pair. Both stations must appear
on the same route.

Short names (resolved automatically):
  hamburg, berlin, berlin-ost, paris, bruxelles/brussels, amsterdam,
  praha/prague, milano/milan, rotterdam, den-haag, antwerpen, dresden,
  liege, mons, roosendaal, koeln, zurich

Examples:
  python es-availability.py                                # Brussels → Prague, rest of month
  python es-availability.py --days 60                      # Brussels → Prague, 60 days
  python es-availability.py hamburg paris --days 60        # Hamburg → Paris, 60 days
  python es-availability.py paris hamburg --days 60        # Paris → Hamburg, 60 days
  python es-availability.py bruxelles milano --days 60     # Brussels → Milan
  python es-availability.py --days 60 -q -o snap.json     # Silent, custom output
  python es-availability.py --days 60 --currency gbp      # GBP prices
  python es-availability.py --diff                         # Compare with previous snapshot
"""

import json
import sys
import os
import glob
import http.client
import ssl
import calendar
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    sys.exit(0)

BASE = "https://europeansleeperprod-api.azurewebsites.net/api"

CURRENCY_SYMBOLS = {"eur": "€", "czk": "Kč", "gbp": "£", "jpy": "¥", "usd": "$"}

# Short aliases for common stations (resolved before API lookup)
# EVA numbers are ES-specific (may differ from DB standard EVA)
STATION_ALIASES = {
    "hamburg": "8020401",
    "berlin": "8010100",
    "berlin-hbf": "8010100",
    "berlin-ost": "8010110",
    "paris": "8700015",
    "bruxelles": "8800104",
    "brussels": "8800104",
    "amsterdam": "8400058",
    "praha": "5457076",
    "prague": "5457076",
    "milano": "8300112",
    "milan": "8300112",
    "rotterdam": "8400530",
    "den-haag": "8400280",
    "antwerpen": "8800210",
    "dresden": "8001305",
    "liege": "8800410",
    "mons": "8800810",
    "roosendaal": "8400526",
    "koeln": "8050500",
    "zurich": "8500200",
}

# Short slugs for filenames (EVA -> short name)
STATION_SLUGS = {
    "8020401": "hamburg",
    "8010100": "berlin-hbf",
    "8010110": "berlin-ost",
    "8700015": "paris",
    "8800104": "bruxelles",
    "8400058": "amsterdam",
    "5457076": "praha",
    "8300112": "milano",
    "8400530": "rotterdam",
    "8400280": "den-haag",
    "8800210": "antwerpen",
    "8001305": "dresden",
    "8800410": "liege",
    "8800810": "mons",
    "8050500": "koeln",
    "8500200": "zurich",
}

# Defaults
DEFAULT_FROM = "bruxelles"
DEFAULT_TO = "praha"


_es_conn = None


def _get_es_conn():
    """Get or create persistent HTTPS connection to European Sleeper API."""
    global _es_conn
    if _es_conn is None:
        ctx = ssl.create_default_context()
        _es_conn = http.client.HTTPSConnection(
            "europeansleeperprod-api.azurewebsites.net", timeout=30, context=ctx)
    return _es_conn


def api_get(path):
    global _es_conn
    headers = {"Accept": "application/json", "Connection": "keep-alive", "User-Agent": "Mozilla/5.0"}
    full_path = "/api" + path
    for attempt in range(2):
        try:
            conn = _get_es_conn()
            conn.request("GET", full_path, headers=headers)
            resp = conn.getresponse()
            return json.loads(resp.read().decode("utf-8"))
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            _es_conn = None
            if attempt == 0:
                continue
    return None


def api_post(path, body):
    global _es_conn
    headers = {"Content-Type": "application/json", "Accept": "application/json", "Connection": "keep-alive", "User-Agent": "Mozilla/5.0"}
    data = json.dumps(body).encode("utf-8")
    full_path = "/api" + path
    for attempt in range(2):
        try:
            conn = _get_es_conn()
            conn.request("POST", full_path, body=data, headers=headers)
            resp = conn.getresponse()
            return json.loads(resp.read().decode("utf-8"))
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            _es_conn = None
            if attempt == 0:
                continue
    return None


def load_constants():
    """Fetch station list and routes from the API."""
    data = api_get('/constants')
    if not data:
        print("Error: could not fetch /constants", file=sys.stderr)
        sys.exit(1)

    stations = {}
    for country_group in data['stations']:
        for s in country_group['stations']:
            stations[s['id']] = s['name']

    routes = data['routes']
    return stations, routes


def resolve_station(query, stations):
    """Resolve a station query (alias, name, or EVA) to an EVA number."""
    # Check aliases first
    if query.lower() in STATION_ALIASES:
        eva = STATION_ALIASES[query.lower()]
        return eva, stations.get(eva, query)

    # Direct EVA match
    if query in stations:
        return query, stations[query]

    # Exact name match (case-insensitive)
    query_lower = query.lower()
    for eva, name in stations.items():
        if name.lower() == query_lower:
            return eva, name

    # Substring match
    matches = [(eva, name) for eva, name in stations.items()
               if query_lower in name.lower()]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        print(f"Ambiguous station '{query}'. Did you mean:")
        for eva, name in sorted(matches, key=lambda x: x[1]):
            print(f"  {eva}  {name}")
        sys.exit(1)

    print(f"Unknown station '{query}'. Available stations:")
    for eva, name in sorted(stations.items(), key=lambda x: x[1]):
        print(f"  {eva}  {name}")
    sys.exit(1)


def find_route(from_eva, to_eva, routes):
    """Find the route containing both stations."""
    for route in routes:
        station_ids = [s['id'] for s in route['stations']]
        if from_eva in station_ids and to_eva in station_ids:
            return route['id']
    return None


def station_slug(eva, name):
    """Short filename-safe slug for a station."""
    if eva in STATION_SLUGS:
        return STATION_SLUGS[eva]
    return name.lower().replace(' ', '-').replace('.', '').replace("'", "").replace('/', '-')[:20]


def find_previous_snapshot(output_path):
    """Find the most recent snapshot file matching the same route pattern."""
    dirname = os.path.dirname(output_path) or '.'
    basename = os.path.basename(output_path)
    parts = basename.split('_', 1)
    if len(parts) == 2:
        pattern = os.path.join(dirname, f'*_{parts[1]}')
    else:
        return None

    files = sorted(glob.glob(pattern))
    if output_path in files:
        idx = files.index(output_path)
        return files[idx - 1] if idx > 0 else None
    elif len(files) >= 1:
        return files[-1]
    return None


# Parse args
args = sys.argv[1:]
MAX_DAYS = None
SAVE_JSON = False
QUIET = False
OUTPUT_FILE = None
CURRENCY = "eur"
DIFF_MODE = False

clean_args = []
i = 0
while i < len(args):
    if args[i] == '--days' and i + 1 < len(args):
        MAX_DAYS = int(args[i + 1])
        i += 2
    elif args[i] == '--json':
        SAVE_JSON = True
        i += 1
    elif args[i] == '--diff':
        DIFF_MODE = True
        i += 1
    elif args[i] in ('-q', '--quiet'):
        QUIET = True
        i += 1
    elif args[i] in ('-o', '--output') and i + 1 < len(args):
        OUTPUT_FILE = args[i + 1]
        SAVE_JSON = True
        i += 2
    elif args[i] == '--currency' and i + 1 < len(args):
        CURRENCY = args[i + 1].lower()
        i += 2
    elif args[i].startswith('-') and not args[i][1:].isdigit():
        i += 1
    else:
        clean_args.append(args[i])
        i += 1

FROM_QUERY = clean_args[0] if len(clean_args) > 0 else DEFAULT_FROM
TO_QUERY = clean_args[1] if len(clean_args) > 1 else DEFAULT_TO


def qprint(*a, **kw):
    if not QUIET:
        print(*a, **kw)


# Load constants and resolve stations
qprint("Loading station data...")
stations, routes = load_constants()

from_eva, from_name = resolve_station(FROM_QUERY, stations)
to_eva, to_name = resolve_station(TO_QUERY, stations)

# Find route
route_id = find_route(from_eva, to_eva, routes)
if not route_id:
    print(f"No route found containing both {from_name} ({from_eva}) and {to_name} ({to_eva}).")
    sys.exit(1)

SYM = CURRENCY_SYMBOLS.get(CURRENCY, CURRENCY.upper())

# Generate filename slug
from_slug = station_slug(from_eva, from_name)
to_slug = station_slug(to_eva, to_name)


def search_trains(d):
    return api_post('/search/trains', {
        "fromLocationId": from_eva,
        "toLocationId": to_eva,
        "departureDate": f"{d.isoformat()}T00:00:00.000Z",
        "passengerTypes": [72],
        "bicycleCount": 0,
        "petsCount": 0,
        "returnDate": None
    })


def get_availability(train_number, travel_date):
    return api_post('/search/availability', {
        "trainRouteId": route_id,
        "fromLocationId": from_eva,
        "toLocationId": to_eva,
        "passengerTypes": [72],
        "trainNumber": train_number,
        "travelDate": travel_date,
        "bicycleCount": 0
    })


# Determine date range
today = date.today()
start = today

if MAX_DAYS:
    end = start + timedelta(days=MAX_DAYS - 1)
else:
    # Default: rest of current month
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    end = date(today.year, today.month, days_in_month)

qprint(f"\nEuropean Sleeper: {from_name} → {to_name}")
qprint(f"Period: {start} to {end} | Currency: {CURRENCY.upper()}")
qprint("=" * 80)

results = {}

d = start
while d <= end:
    search = search_trains(d)
    if not search:
        print(f"\n{d} — API error", file=sys.stderr)
        d += timedelta(days=1)
        continue

    found_trip = None
    for route_result in search.get('routeSearchResults', []):
        for sr in route_result.get('searchResultOutward', []):
            trip = sr.get('trip')
            if trip and trip.get('bookable') and trip.get('travelDate') == d.isoformat():
                found_trip = trip
                break

    if not found_trip:
        qprint(f"\n{d} {'—':>3} no service")
        results[str(d)] = {"info": "no service"}
        d += timedelta(days=1)
        continue

    # Get availability
    avail_data = get_availability(found_trip['trainNumber'], found_trip['travelDate'])
    avail = (avail_data or {}).get('availabilityResult', {}).get('availability', {})

    if not avail:
        qprint(f"\n{d} {'—':>3} train {found_trip['trainNumber']} — no availability data")
        results[str(d)] = {"info": "no availability"}
        d += timedelta(days=1)
        continue

    dep = avail.get('departureTime', '')[11:16]
    arr = avail.get('arrivalTime', '')[11:16]
    dep_name = avail.get('departureStationName', '')
    arr_name = avail.get('arrivalStationName', '')

    detour_note = ""
    det = found_trip.get('detourInfo', {})
    if det.get('hasDetour'):
        if det.get('alternativeFromId'):
            detour_note += f" [dep:{dep_name}]"
        if det.get('alternativeToId'):
            detour_note += f" [arr:{arr_name}]"

    qprint(f"\n{d} | {found_trip['trainNumber']} | {dep}→{arr}{detour_note}")

    day_data = {"date": str(d), "train": found_trip['trainNumber'], "classes": []}

    for pc in avail.get('priceClasses', []):
        ptype = pc['placeTypeKey']
        free = pc.get('freeSeatsCount')
        prices = pc.get('prices') or {}
        price = prices.get(CURRENCY)

        fares = pc.get('fareTypes', [])
        fare_info = []
        fare_dict = {}
        for f in fares:
            if f.get('bookable'):
                fp = (f.get('prices') or {}).get(CURRENCY)
                fare_info.append(f"{f['id']}:{fp}{SYM}" if fp else f"{f['id']}:?")
                if fp:
                    fare_dict[f['id']] = fp

        free_str = f"{free:>3}" if free is not None else "  ?"
        price_str = f"{price:>7.0f}{SYM}" if price else "      ?"

        qprint(f"  {ptype:<28} {free_str} free  from {price_str}  [{', '.join(fare_info)}]")

        day_data["classes"].append({
            "type": ptype,
            "free": free,
            "price": price,
            "fares": fare_dict
        })

    results[str(d)] = day_data
    d += timedelta(days=1)

# Save JSON
if SAVE_JSON or OUTPUT_FILE:
    if not OUTPUT_FILE:
        OUTPUT_FILE = f"es-{from_slug}-{to_slug}.json"
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    qprint(f"\nSaved to {OUTPUT_FILE}")

# Diff mode
if DIFF_MODE:
    out_path = OUTPUT_FILE or f"es-{from_slug}-{to_slug}.json"
    prev_path = find_previous_snapshot(out_path)
    if prev_path:
        qprint(f"\n{'=' * 80}")
        qprint(f"DIFF vs {os.path.basename(prev_path)}")
        qprint(f"{'=' * 80}")
        prev_data = json.load(open(prev_path, 'r', encoding='utf-8'))

        for dt in sorted(results.keys()):
            if dt not in prev_data:
                continue
            curr = results[dt]
            prev = prev_data[dt]

            # Skip info-only entries
            if 'info' in curr or 'info' in prev:
                continue

            curr_classes = {c['type']: c for c in curr.get('classes', [])}
            prev_classes = {c['type']: c for c in prev.get('classes', [])}

            changes = []
            for typ in set(list(curr_classes.keys()) + list(prev_classes.keys())):
                cp = curr_classes.get(typ, {}).get('price')
                pp = prev_classes.get(typ, {}).get('price')
                cf = curr_classes.get(typ, {}).get('free')
                pf = prev_classes.get(typ, {}).get('free')

                if cp != pp:
                    if pp and cp:
                        pct = ((cp - pp) / pp) * 100
                        changes.append(f"  {typ:<28} price: {pp:.0f}→{cp:.0f} ({pct:+.0f}%)")
                    elif pp and not cp:
                        changes.append(f"  {typ:<28} SOLD OUT (was {pp:.0f}{SYM}, {pf} free)")
                    elif not pp and cp:
                        changes.append(f"  {typ:<28} NOW AVAILABLE {cp:.0f}{SYM}, {cf} free")

                if cf != pf and cf is not None and pf is not None:
                    diff = cf - pf
                    changes.append(f"  {typ:<28} free: {pf}→{cf} ({diff:+d})")

            if changes:
                qprint(f"\n{dt}:")
                for c in changes:
                    qprint(c)
    else:
        qprint("\nNo previous snapshot found for diff.")

qprint()
