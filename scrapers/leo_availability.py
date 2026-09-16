"""
Leo Express Availability Monitor
Queries searchConnections for a date range and shows capacity, occupancy,
price per class, and promo flags. Optionally saves JSON for change detection.

Usage:
  python leo-availability.py [from] [to] [YYYY-MM] [--json] [--days N] [--diff]
                                                    [-o FILE] [-q]

Positional args:
  from     Origin station EVA code or meta-code (default: 8002041 = Frankfurt (Main) Süd)
  to       Destination station EVA code or meta-code (default: 5100234 = Przemyśl Główny)
  YYYY-MM  Month to query (default: current month)

Options:
  --json            Save results to leo-availability-{from}-{to}-{YYYYMM}.json
  -o, --output F    Save results to specified file (implies --json)
  --days N          Only query N days starting from today (or 1st of month if future)
  -c, --currency C  Currency: CZK, EUR, PLN (default: CZK)
  --diff            Compare with previous JSON and highlight changes
  -q, --quiet       Suppress console output (errors still go to stderr)
  -h, --help        Show this help

Station codes:
  German EVA:  8002041 (Frankfurt Süd), 8010366 (Weimar), 8010101 (Erfurt)
  Czech:       5457076 (Praha hl.n.), 5434364 (Ostrava hl.n.)
  Polish:      5100234 (Przemyśl Główny), 5100069 (Wrocław)
  Meta:        PRZEMYSL, PRAHA, OSTRAVA, KRAKOW, DRESDEN, BRATISLAVA

Date format: DD.MM.YYYY (used internally by API)
Currency: CZK (canonical base currency, avoids rounding artifacts)

Examples:
  python leo-availability.py                                      # Frankfurt Süd → Przemyśl, this month
  python leo-availability.py 8010366 PRZEMYSL 2026-08             # Weimar → Przemyśl, Aug 2026
  python leo-availability.py 8002041 5100234 2026-08 --days 14    # First 14 days
  python leo-availability.py --days 3 --json --diff               # Quick diff of last 3 days
  python leo-availability.py --days 60 --json -q                  # Silent, auto-named
  python leo-availability.py --days 60 -o snapshot.json -q        # Silent, custom file
"""

import json
import sys
import os
import time
import http.client
import ssl
import calendar
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    sys.exit(0)

# Parse args
args = sys.argv[1:]
MAX_DAYS = None
SAVE_JSON = False
DIFF_MODE = False
QUIET = False
OUTPUT_FILE = None
CURRENCY = "CZK"

# Extract flags and their values first
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
    elif args[i] in ('-c', '--currency') and i + 1 < len(args):
        CURRENCY = args[i + 1].upper()
        i += 2
    elif args[i].startswith('--'):
        i += 1  # skip unknown flags
    else:
        clean_args.append(args[i])
        i += 1

CURRENCY_SYMBOLS = {"CZK": "Kč", "EUR": "€", "PLN": "zł"}
CURRENCY_SYM = CURRENCY_SYMBOLS.get(CURRENCY, CURRENCY)

FROM = clean_args[0] if len(clean_args) > 0 else "8002041"       # Frankfurt (Main) Süd
TO = clean_args[1] if len(clean_args) > 1 else "5100234"         # Przemyśl Główny

# Parse date: support both YYYY-MM and legacy MM YYYY
DATE_ARG = clean_args[2] if len(clean_args) > 2 else None
if DATE_ARG and '-' in DATE_ARG:
    # YYYY-MM format
    try:
        parsed = datetime.strptime(DATE_ARG, "%Y-%m")
        YEAR = parsed.year
        MONTH = parsed.month
    except ValueError:
        print(f"Invalid date '{DATE_ARG}'. Expected format: YYYY-MM (e.g. 2026-08)", file=sys.stderr)
        sys.exit(1)
elif DATE_ARG:
    # Legacy: MM [YYYY]
    MONTH = int(DATE_ARG)
    YEAR = int(clean_args[3]) if len(clean_args) > 3 else datetime.now().year
else:
    MONTH = datetime.now().month
    YEAR = datetime.now().year

ENDPOINT = "https://graph.leoexpress.com/le"

QUERY = """query searchConnections($from: String, $to: String, $date: String, $persons: [RateArgument], $services: [ServiceArgument], $currency: String, $locale: String, $platform: String) {
  searchResults(from: $from, to: $to, date: $date, persons: $persons, services: $services, currency: $currency, locale: $locale, platform: $platform) {
    return_code
    connections {
      origin { id name }
      destination { id name }
      departure_time { date timezone }
      arrival_time { date timezone }
      lines { line_id ride_id carrier_id }
      classes { id short name }
      class_info {
        record_id
        capacity
        max_capacity
        occupied
        standing
        total
        basictotal
        guaranted
        cashback
        is_promo
        rates { price basicprice count }
        passengers
      }
      hash
    }
    error { code message }
  }
}"""


_leo_conn = None


def _get_leo_conn():
    """Get or create persistent HTTPS connection to Leo Express GraphQL."""
    global _leo_conn
    if _leo_conn is None:
        ctx = ssl.create_default_context()
        _leo_conn = http.client.HTTPSConnection("graph.leoexpress.com", timeout=20, context=ctx)
    return _leo_conn


def _leo_post(body):
    """POST to Leo Express GraphQL with keep-alive."""
    global _leo_conn
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.leoexpress.com",
        "Connection": "keep-alive",
    }
    data = body.encode("utf-8") if isinstance(body, str) else body
    for attempt in range(2):
        try:
            conn = _get_leo_conn()
            conn.request("POST", "/le", body=data, headers=headers)
            resp = conn.getresponse()
            return json.loads(resp.read().decode("utf-8"))
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError, OSError):
            _leo_conn = None
            if attempt == 0:
                continue
            raise


def query_date(d):
    """Query availability for a single date."""
    variables = {
        "from": FROM,
        "to": TO,
        "date": d.strftime("%d.%m.%Y"),
        "persons": [{"name": "adult", "cards": []}],
        "services": [],
        "locale": "de",
        "currency": CURRENCY,
        "platform": "website",
    }

    body = json.dumps({"operationName": "searchConnections", "query": QUERY, "variables": variables})

    try:
        data = _leo_post(body)
    except Exception as e:
        return {"error": str(e)}

    if "errors" in data:
        return {"error": data["errors"][0]["message"]}

    results = data.get("data", {}).get("searchResults", {})
    if results.get("error"):
        return {"error": results["error"]["message"]}

    connections = results.get("connections", [])
    if not connections:
        return {"error": "no connections"}

    # Take first connection (LE235 night train - usually only one per day)
    conn = connections[0]
    classes = {str(c["id"]): c for c in conn.get("classes", [])}

    dest_name = conn.get("destination", {}).get("name", TO)
    origin_name = conn.get("origin", {}).get("name", FROM)
    dep_time = conn.get("departure_time", {}).get("date", "")
    arr_time = conn.get("arrival_time", {}).get("date", "")
    line_id = conn["lines"][0]["line_id"] if conn.get("lines") else "?"

    # Check if the returned train actually departs on the queried date
    if dep_time and not dep_time.startswith(d.isoformat()):
        return {"info": "no service"}

    output = []
    for ci in conn.get("class_info", []):
        cls = classes.get(str(ci["record_id"]), {})
        rates = ci.get("rates", [])
        adult_price = rates[0]["price"] if rates else ci.get("total")
        basic_price = rates[0].get("basicprice") if rates else ci.get("basictotal")

        output.append({
            "class": cls.get("short", ci["record_id"]),
            "name": cls.get("name", "?"),
            "capacity": ci.get("capacity"),
            "max_capacity": ci.get("max_capacity"),
            "occupied": ci.get("occupied"),
            "price": adult_price,
            "basic_price": basic_price,
            "is_promo": ci.get("is_promo"),
            "cashback": ci.get("cashback"),
        })

    return {
        "classes": output,
        "origin": origin_name,
        "destination": dest_name,
        "line": line_id,
        "departure": dep_time,
        "arrival": arr_time,
        "num_connections": len(connections),
    }


def slugify(name):
    """Turn a station name into a filename-safe slug."""
    import re
    s = name.lower()
    # Common replacements
    for old, new in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                     ("ś", "s"), ("ł", "l"), ("ó", "o"), ("ą", "a"), ("ę", "e"),
                     ("ż", "z"), ("ź", "z"), ("ń", "n"),
                     ("ž", "z"), ("č", "c"), ("ř", "r"), ("ň", "n"), ("ý", "y"),
                     ("á", "a"), ("í", "i"), ("é", "e")]:
        s = s.replace(old, new)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def format_cell(c):
    """Format a class info dict into a compact cell."""
    if not c:
        return f"{'—':>11}"
    cap = c["capacity"] if c["capacity"] is not None else "?"
    occ = c.get("occupied")
    price = f"{c['price']:.0f} {CURRENCY_SYM}" if c["price"] else "?"
    promo = "★" if c.get("is_promo") else ""

    if occ is not None and c.get("max_capacity"):
        fill = f"{occ}/{c['max_capacity']}"
        return f"{fill:>6} {price}{promo:>5}"
    else:
        return f"{cap:>3} {price}{promo:>5}"


def main():
    today = date.today()

    # Determine date range
    if MAX_DAYS and not DATE_ARG:
        # --days without explicit month: span from today for N days (cross-month)
        start = today
        end = today + timedelta(days=MAX_DAYS - 1)
    else:
        # Explicit month or no --days: stay within the specified month
        days_in_month = calendar.monthrange(YEAR, MONTH)[1]
        start_day = 1
        if YEAR == today.year and MONTH == today.month:
            start_day = today.day
        end_day = days_in_month
        if MAX_DAYS:
            end_day = min(start_day + MAX_DAYS - 1, days_in_month)
        start = date(YEAR, MONTH, start_day)
        end = date(YEAR, MONTH, end_day)

    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += timedelta(days=1)

    def qprint(*a, **kw):
        if not QUIET:
            print(*a, **kw)

    qprint(f"Leo Express: {FROM} → {TO}, {dates[0]} to {dates[-1]} ({len(dates)} days)")
    qprint(f"{'Date':<12} {'Business':>11} {'Economy':>11} {'Sleeper':>11} {'SleeperLady':>11}")
    qprint("-" * 60)

    all_results = {}

    for i, d in enumerate(dates):
        result = query_date(d)
        all_results[d.isoformat()] = result

        if "error" in result:
            qprint(f"{d.strftime('%a %d.%m'):<12} {result['error']}")
        elif "info" in result:
            qprint(f"{d.strftime('%a %d.%m'):<12} ({result['info']})")
        else:
            by_class = {c["class"]: c for c in result["classes"]}

            cols = []
            for short in ["BUS", "ECO", "ECOSLEEPER", "ECOSLEEPERLADY"]:
                cols.append(format_cell(by_class.get(short)))

            qprint(f"{d.strftime('%a %d.%m'):<12} {cols[0]} {cols[1]} {cols[2]} {cols[3]}")

        # Small delay to avoid rate limiting (every 5 requests)
        if (i + 1) % 5 == 0 and i < len(dates) - 1:
            time.sleep(0.5)

    # Save JSON if requested
    if SAVE_JSON or DIFF_MODE:
        # Derive filename from API-resolved station names (first successful result)
        resolved_origin = FROM
        resolved_dest = TO
        for r in all_results.values():
            if "error" not in r:
                resolved_origin = r.get("origin", FROM)
                resolved_dest = r.get("destination", TO)
                break
        date_tag = f"{dates[0].strftime('%Y%m%d')}-{dates[-1].strftime('%Y%m%d')}"
        file_slug = f"{slugify(resolved_origin)}-{slugify(resolved_dest)}-{date_tag}"
        filename = OUTPUT_FILE if OUTPUT_FILE else f"leo-availability-{file_slug}.json"
        old_data = {}

        if DIFF_MODE and os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                old_data = json.load(f)

        if SAVE_JSON:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "from": FROM,
                    "to": TO,
                    "results": all_results,
                }, f, indent=2, ensure_ascii=False)
            qprint(f"\nSaved to {filename}")

        # Show diffs
        if DIFF_MODE and old_data:
            old_results = old_data.get("results", {})
            qprint(f"\n--- Changes since {old_data.get('timestamp', '?')} ---")
            changes = 0
            for d_str, new in all_results.items():
                old = old_results.get(d_str)
                if not old or "error" in new or "error" in old:
                    continue
                for nc in new.get("classes", []):
                    oc = next((c for c in old.get("classes", []) if c["class"] == nc["class"]), None)
                    if not oc:
                        continue
                    if nc["price"] != oc["price"]:
                        diff = nc["price"] - oc["price"]
                        arrow = "↑" if diff > 0 else "↓"
                        qprint(f"  {d_str} {nc['class']}: {oc['price']:.0f} {CURRENCY_SYM} → {nc['price']:.0f} {CURRENCY_SYM} ({arrow}{abs(diff):.0f} {CURRENCY_SYM})")
                        changes += 1
                    if nc["capacity"] != oc["capacity"]:
                        diff = nc["capacity"] - oc["capacity"]
                        arrow = "↑" if diff > 0 else "↓"
                        qprint(f"  {d_str} {nc['class']}: capacity {oc['capacity']} → {nc['capacity']} ({arrow}{abs(diff)})")
                        changes += 1
            if changes == 0:
                qprint("  No changes detected.")


if __name__ == "__main__":
    main()
