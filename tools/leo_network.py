"""
Leo Express Network & Currency Map
Discovers all station pairs via minPricesQuery in EUR, CZK, PLN and highlights
arbitrage opportunities where paying in a different currency is cheaper.

Uses Leo's internal fixed rates (1 EUR = 24 CZK, 1 CZK = 5 PLN) and compares
against real market rates to find savings.

Usage: python leo-network.py [--json] [--stations]

Options:
  --json      Export full network to leo-network.json
  --stations  Resolve station names via stations API (189 of 229 resolvable)
  -h, --help  Show this help

Notes:
  - Fetches minPrices in all 3 currencies (3 API calls)
  - 22,147 routes across 229 station IDs
  - 77 internal IDs (mostly dead Lux Express/Baltic bus stops) can't be resolved
  - Market rates (MARKET_CZK) should be updated periodically in the script

Examples:
  python leo-network.py                  # Basic network stats + arbitrage
  python leo-network.py --stations       # With station name resolution
  python leo-network.py --stations --json  # Full export
"""

import json
import sys
import platform
import subprocess
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURL = 'curl.exe' if platform.system() == 'Windows' else 'curl'

if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    sys.exit(0)

ENDPOINT = "https://graph.leoexpress.com/le"

# Leo Express internal fixed rates (from creditExchangeRates API)
LEO_RATES = {"EUR": 24, "CZK": 1, "PLN": 5}  # all relative to CZK

# Approximate real market rates (CZK per unit)
MARKET_CZK = {"EUR": 25.3, "CZK": 1, "PLN": 5.9}  # update as needed

MIN_PRICES_QUERY = """query minPricesQuery($currency: String, $locale: String) {
  minPrices(currency: $currency, locale: $locale) {
    minPrices { from to { to price } }
    error { code message }
  }
}"""

STATIONS_QUERY = """query { stations(locale: "de") { id name country } }"""


def graphql(body):
    body_json = json.dumps(body)
    result = subprocess.run(
        [CURL, '-s', '-X', 'POST', ENDPOINT,
         '-H', 'Content-Type: application/json',
         '-H', 'Origin: https://www.leoexpress.com',
         '-d', body_json],
        capture_output=True, text=True, encoding='utf-8'
    )
    return json.loads(result.stdout)


def fetch_min_prices(currency):
    data = graphql({"query": MIN_PRICES_QUERY, "variables": {"currency": currency, "locale": "de"}})
    mp = data.get("data", {}).get("minPrices", {})
    if mp.get("error"):
        print(f"  ERROR ({currency}): {mp['error']['message']}")
        return {}
    prices = {}
    for origin in mp.get("minPrices", []):
        from_id = origin["from"]
        for dest in origin["to"]:
            prices[(from_id, dest["to"])] = dest["price"]
    return prices


def fetch_stations():
    data = graphql({"query": STATIONS_QUERY})
    stations = data.get("data", {}).get("stations", [])
    return {s["id"]: s["name"] for s in stations}


def main():
    flags = set(sys.argv[1:])
    export_json = "--json" in flags
    resolve_names = "--stations" in flags

    print("Leo Express Network — Multi-Currency Min Prices")
    print("=" * 70)

    # Fetch prices in all currencies
    all_prices = {}
    for currency in ["EUR", "CZK", "PLN"]:
        print(f"  Fetching {currency}...", end="", flush=True)
        all_prices[currency] = fetch_min_prices(currency)
        print(f" {len(all_prices[currency])} routes")

    eur_prices = all_prices["EUR"]
    czk_prices = all_prices["CZK"]
    pln_prices = all_prices["PLN"]

    # All route pairs
    all_pairs = set(eur_prices.keys()) | set(czk_prices.keys()) | set(pln_prices.keys())
    stations = set()
    for f, t in all_pairs:
        stations.add(f)
        stations.add(t)

    print(f"\nNetwork: {len(stations)} stations, {len(all_pairs)} route pairs")

    # Station name resolution
    names = {}
    if resolve_names:
        print("  Resolving station names...")
        names = fetch_stations()

    def name(sid):
        return names.get(sid, sid)

    # Find arbitrage opportunities
    # Convert all prices to "real EUR cost" using market rates
    print(f"\n{'─'*70}")
    print("ARBITRAGE: Routes where paying in CZK/PLN is cheaper than EUR")
    print(f"  (using market rates: 1€ = {MARKET_CZK['EUR']} CZK, 1€ = {MARKET_CZK['EUR']/MARKET_CZK['PLN']:.1f} PLN)")
    print(f"{'─'*70}")
    print(f"  {'From':<22} {'To':<22} {'EUR':>6} {'CZK':>7} {'PLN':>7} {'Save':>6} {'Best'}")
    print(f"  {'─'*80}")

    arbitrage = []
    for pair in sorted(all_pairs):
        eur = eur_prices.get(pair)
        czk = czk_prices.get(pair)
        pln = pln_prices.get(pair)
        if not eur or eur == 0:
            continue

        # Real cost in EUR at market exchange rates
        eur_cost = eur
        czk_cost = (czk / MARKET_CZK["EUR"]) if czk else eur
        pln_cost = (pln * MARKET_CZK["PLN"] / MARKET_CZK["EUR"]) if pln else eur

        best_cost = min(eur_cost, czk_cost, pln_cost)
        saving_pct = (eur_cost - best_cost) / eur_cost * 100

        if saving_pct > 3:
            best_cur = "EUR"
            if czk_cost == best_cost:
                best_cur = "CZK"
            elif pln_cost == best_cost:
                best_cur = "PLN"
            arbitrage.append((pair, eur, czk, pln, saving_pct, best_cur))

    arbitrage.sort(key=lambda x: -x[4])
    for pair, eur, czk, pln, pct, best in arbitrage[:30]:
        f_name = name(pair[0])[:21]
        t_name = name(pair[1])[:21]
        print(f"  {f_name:<22} {t_name:<22} {eur:>5.1f}€ {czk:>5.0f} Kč {pln:>5.0f} zł {pct:>5.1f}% {best}")

    if not arbitrage:
        print("  (none found — prices are consistent across currencies)")

    # Top hubs
    print(f"\n{'─'*70}")
    print("TOP 15 HUBS (most destinations)")
    print(f"{'─'*70}")
    degree = defaultdict(int)
    for f, t in all_pairs:
        degree[f] += 1
    sorted_hubs = sorted(degree.items(), key=lambda x: -x[1])[:15]
    print(f"  {'Station':<30} {'Routes':>7} {'Min €':>7} {'Max €':>7}")
    print(f"  {'─'*55}")
    for station, deg in sorted_hubs:
        prices_from = [eur_prices[p] for p in eur_prices if p[0] == station]
        if prices_from:
            print(f"  {name(station):<30} {deg:>7} {min(prices_from):>6.1f} {max(prices_from):>6.1f}")

    # Price distribution
    print(f"\n{'─'*70}")
    print("PRICE DISTRIBUTION (EUR)")
    print(f"{'─'*70}")
    tiers = [(0, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 50), (50, 100), (100, 999)]
    for lo, hi in tiers:
        count = len([p for p in eur_prices.values() if lo <= p < hi])
        if count:
            bar = "█" * (count // 3)
            label = f"{lo}–{hi}" if hi < 999 else f"{lo}+"
            print(f"  {label:>7} €: {count:>4} routes  {bar}")

    # Cheapest & most expensive
    print(f"\n{'─'*70}")
    print("CHEAPEST 15 ROUTES (EUR)")
    print(f"{'─'*70}")
    sorted_eur = sorted(eur_prices.items(), key=lambda x: x[1])
    for (f, t), p in sorted_eur[:15]:
        print(f"  {name(f):<25} → {name(t):<25} {p:>5.1f} €")

    print(f"\nMOST EXPENSIVE 10 ROUTES (EUR)")
    for (f, t), p in sorted_eur[-10:]:
        print(f"  {name(f):<25} → {name(t):<25} {p:>5.1f} €")

    # Export
    if export_json:
        output = {
            "stations": sorted(stations),
            "station_count": len(stations),
            "route_count": len(all_pairs),
            "exchange_rates": {"CZK_per_EUR": 25.0, "PLN_per_EUR": 4.3},
            "routes": [],
            "arbitrage_count": len(arbitrage),
        }
        for pair in sorted(all_pairs):
            output["routes"].append({
                "from": pair[0], "to": pair[1],
                "eur": eur_prices.get(pair),
                "czk": czk_prices.get(pair),
                "pln": pln_prices.get(pair),
            })
        with open("leo-network.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\nExported to leo-network.json ({len(all_pairs)} routes)")

    print(f"\nLeo internal rates: 1 EUR = {LEO_RATES['EUR']} CZK, 1 PLN = {LEO_RATES['PLN']} CZK")
    print(f"Market rates used:  1 EUR ≈ {MARKET_CZK['EUR']} CZK, 1 PLN ≈ {MARKET_CZK['PLN']} CZK")


if __name__ == "__main__":
    main()
