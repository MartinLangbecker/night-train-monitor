#!/usr/bin/env python3
"""
Leo Express Segment Pricing — Single Date, All Sub-Routes

Four perspectives on the same train:
  1. Eastbound, fixed origin:  Frankfurt Süd → [each stop]
  2. Eastbound, fixed dest:    [each stop] → Przemyśl Główny
  3. Westbound, fixed origin:  Przemyśl Główny → [each stop]
  4. Westbound, fixed dest:    [each stop] → Frankfurt (Main) Süd

Usage:
  python3 leo-segment-pricing.py 2026-08-28                    # All 4 perspectives
  python3 leo-segment-pricing.py 2026-08-28 -c CZK
  python3 leo-segment-pricing.py 2026-08-28 -o data/segments/20260828_segments.json

Options:
  -c, --currency C  CZK, EUR, PLN (default: EUR)
  -o, --output F    Save results to JSON file
  -q, --quiet       Suppress console output
"""

import json
import sys
import os
import subprocess
import time
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURL = 'curl'
ENDPOINT = "https://graph.leoexpress.com/le"

# Complete LE235 route stops in eastbound order — ALL intermediate halts
# from actual timetable (Period 4, Variant A)
ROUTE_STOPS = [
    # Germany
    ("8070003", "Frankfurt Flughafen"),
    ("8002041", "Frankfurt (Main) Süd"),
    ("8000349", "Offenbach (Main) Hbf"),
    ("8000150", "Hanau Hbf"),
    ("8000115", "Fulda"),
    ("8010097", "Eisenach Hbf"),
    ("8010136", "Gotha"),
    ("8010101", "Erfurt Hbf"),
    ("8010366", "Weimar"),
    ("8011051", "Apolda"),
    ("8010240", "Naumburg (Saale) Hbf"),
    ("8010368", "Weißenfels"),
    # ("xxxxxx", "Halle (Saale) Hbf"),  # durchfahrt (|)
    ("8098205", "Leipzig Hbf (tief)"),
    ("8010089", "Dresden-Neustadt"),
    ("8010085", "Dresden Hbf"),
    ("8010022", "Bad Schandau"),
    # Czechia
    ("556597", "Děčín hl.n."),
    ("531798", "Ústí nad Labem"),
    ("543967", "Kralupy n.Vltavou"),
    ("5457256", "Prag-Holešovice"),
    ("5457076", "Prag Hbf"),
    ("54572768", "Prag-Vršovice"),
    ("5453613", "Pardubice Hbf"),
    ("5453863", "Ústí nad Orlicí"),
    ("5436145", "Zábřeh na Moravě"),
    ("5434362", "Olmütz Hbf"),
    ("5433722", "Hranice na Moravě"),
    ("5434804", "Suchdol nad Odrou"),
    ("5434694", "Studénka"),
    ("5434434", "Ostrava-Svinov"),
    ("5434364", "Ostrava Hbf"),
    ("5434124", "Bohumín"),
    # Poland
    ("5100048", "Oświęcim"),
    ("5100028", "Krakau Główny"),
    ("5100170", "Krakau Płaszów"),
    ("5100227", "Bochnia"),
    ("5100671", "Brzesko Okocim"),
    ("5100230", "Tarnów"),
    ("5100228", "Dębica"),
    ("5103157", "Ropczyce"),
    ("5103349", "Sędziszów Małopolski"),
    ("5100229", "Rzeszów Główny"),
    ("5101932", "Łańcut"),
    ("5100195", "Przeworsk"),
    ("5100233", "Jarosław"),
    ("5103068", "Radymno"),
    ("5102825", "Przemyśl Zasanie"),
    ("5100234", "Przemyśl Główny"),
]

FRANKFURT = ("8002041", "Frankfurt (Main) Süd")
PRZEMYSL = ("5100234", "Przemyśl Główny")

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
        total
        basictotal
        is_promo
        cashback
        rates { price basicprice count }
      }
    }
    error { code message }
  }
}"""

CLASS_ORDER = ['ECO', 'BUS', 'ECOSLEEPER', 'ECOSLEEPERLADY']


def query_segment(from_id, to_id, date_str, currency):
    """Query a single origin-destination pair."""
    variables = {
        "from": from_id,
        "to": to_id,
        "date": date_str,
        "persons": [{"name": "adult", "cards": []}],
        "services": [],
        "currency": currency,
        "locale": "de",
        "platform": "website",
    }
    body = json.dumps({"operationName": "searchConnections", "query": QUERY, "variables": variables})

    result = subprocess.run(
        [CURL, '-s', '-X', 'POST', ENDPOINT,
         '-H', 'Content-Type: application/json',
         '-H', 'Origin: https://www.leoexpress.com',
         '-d', body],
        capture_output=True, text=True, encoding='utf-8', timeout=20
    )

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"error": "JSON parse failed"}

    if "errors" in data:
        return {"error": data["errors"][0].get("message", "graphql error")}

    sr = data.get("data", {}).get("searchResults", {})
    if sr.get("error"):
        return {"error": sr["error"].get("message", "unknown")}

    connections = sr.get("connections", [])
    if not connections:
        return {"info": "no service"}

    conn = connections[0]
    class_info_map = {str(ci["record_id"]): ci for ci in conn.get("class_info", [])}

    classes = []
    for cls in conn.get("classes", []):
        ci = class_info_map.get(str(cls["id"]))
        if ci:
            price = ci["rates"][0]["price"] if ci.get("rates") else None
            classes.append({
                "class": cls["short"],
                "name": cls["name"],
                "capacity": ci.get("capacity"),
                "price": price,
                "is_promo": ci.get("is_promo", False),
            })

    return {
        "classes": classes,
        "origin": conn["origin"]["name"],
        "destination": conn["destination"]["name"],
        "departure": conn.get("departure_time", {}).get("date", ""),
        "arrival": conn.get("arrival_time", {}).get("date", ""),
    }


def print_header(label, date_str, currency):
    print(f"\n{'─'*78}")
    print(f"  {label}")
    print(f"  Datum: {date_str}  Währung: {currency}")
    print(f"{'─'*78}")
    print(f"  {'Station':<26} {'Eco':>8} {'Bus':>8} {'Slp':>8} {'Lady':>8}   cap")
    print(f"  {'─'*72}")


def print_result(station_name, result):
    if "classes" in result:
        price_map = {c['class']: c for c in result['classes']}
        cols = []
        caps = []
        for cls in CLASS_ORDER:
            if cls in price_map:
                p = price_map[cls]['price']
                c = price_map[cls]['capacity']
                cols.append(f"{p:>7.1f}")
                caps.append(f"{c:>3}")
            else:
                cols.append(f"{'—':>7}")
                caps.append(f"{'—':>3}")
        cap_str = "/".join(caps)
        print(f"  {station_name:<26} {''.join(cols)}   [{cap_str}]")
    elif "info" in result:
        print(f"  {station_name:<26} {'(kein Verkehr)':>35}")
    elif "error" in result:
        err = result['error'][:45]
        print(f"  {station_name:<26} {err}")


def run_queries(pairs, date_str, currency, label, quiet):
    """Run a list of (from_id, to_id, display_name) queries."""
    results = {}
    if not quiet:
        print_header(label, date_str, currency)

    for from_id, to_id, display_name in pairs:
        result = query_segment(from_id, to_id, date_str, currency)
        results[f"{from_id}_{to_id}"] = {"name": display_name, "from": from_id, "to": to_id, "data": result}
        if not quiet:
            print_result(display_name, result)
        time.sleep(0.3)

    return results


def main():
    args = sys.argv[1:]

    currency = "EUR"
    output_file = None
    quiet = False

    i = 0
    positional = []
    while i < len(args):
        if args[i] in ('-c', '--currency') and i + 1 < len(args):
            currency = args[i + 1].upper()
            i += 2
        elif args[i] in ('-o', '--output') and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ('-q', '--quiet'):
            quiet = True
            i += 1
        elif args[i] in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        else:
            positional.append(args[i])
            i += 1

    if positional:
        try:
            d = datetime.strptime(positional[0], "%Y-%m-%d")
            date_str = d.strftime("%d.%m.%Y")
        except ValueError:
            date_str = positional[0]
    else:
        d = date.today() + timedelta(days=1)
        date_str = d.strftime("%d.%m.%Y")

    if not quiet:
        print(f"Leo Express Segment-Preise (alle Perspektiven)")
        print(f"Datum: {date_str}  Währung: {currency}")

    ffm_idx = next(i for i, s in enumerate(ROUTE_STOPS) if s[0] == FRANKFURT[0])
    prz_idx = next(i for i, s in enumerate(ROUTE_STOPS) if s[0] == PRZEMYSL[0])

    # === 1. Eastbound, fixed origin: Frankfurt → [each stop] ===
    pairs_1 = [(FRANKFURT[0], s[0], s[1]) for s in ROUTE_STOPS[ffm_idx+1:]]
    r1 = run_queries(pairs_1, date_str, currency,
                     "OSTWÄRTS ab Frankfurt (Main) Süd → [Ziel variiert]", quiet)

    # === 2. Eastbound, fixed dest: [each stop] → Przemyśl ===
    pairs_2 = [(s[0], PRZEMYSL[0], s[1]) for s in ROUTE_STOPS[ffm_idx:prz_idx]]
    r2 = run_queries(pairs_2, date_str, currency,
                     "OSTWÄRTS nach Przemyśl Główny ← [Start variiert]", quiet)

    # === 3. Westbound, fixed origin: Przemyśl → [each stop] ===
    pairs_3 = [(PRZEMYSL[0], s[0], s[1]) for s in reversed(ROUTE_STOPS[:prz_idx])]
    r3 = run_queries(pairs_3, date_str, currency,
                     "WESTWÄRTS ab Przemyśl Główny → [Ziel variiert]", quiet)

    # === 4. Westbound, fixed dest: [each stop] → Frankfurt ===
    pairs_4 = [(s[0], FRANKFURT[0], s[1]) for s in reversed(ROUTE_STOPS[ffm_idx+1:prz_idx+1])]
    r4 = run_queries(pairs_4, date_str, currency,
                     "WESTWÄRTS nach Frankfurt (Main) Süd ← [Start variiert]", quiet)

    # Summary
    if not quiet:
        print(f"\n{'─'*78}")
        for label, r in [("Ost ab FFM", r1), ("Ost nach PRZ", r2),
                         ("West ab PRZ", r3), ("West nach FFM", r4)]:
            ok = sum(1 for v in r.values() if "classes" in v.get("data", {}))
            print(f"  {label:<16} {ok}/{len(r)} Segmente mit Preisen")

    if output_file:
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        output = {
            "timestamp": datetime.now().isoformat(),
            "date": date_str,
            "currency": currency,
            "eastbound_from_frankfurt": r1,
            "eastbound_to_przemysl": r2,
            "westbound_from_przemysl": r3,
            "westbound_to_frankfurt": r4,
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        if not quiet:
            print(f"\n  Gespeichert: {output_file}")


if __name__ == '__main__':
    main()
