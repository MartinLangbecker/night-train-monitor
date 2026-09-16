"""
Leo Express Multi-Currency Price Comparison
Queries a specific connection in EUR, CZK, PLN to compare actual ticket prices.
Shows real cost in EUR after applying market exchange rates vs Leo's fixed rates.
Gives a buying recommendation based on current ECB rates.

Usage: python leo-currency.py [from] [to] [date]

Positional args:
  from   Origin station EVA code or meta-code (default: 8002041 = Frankfurt (Main) Süd)
  to     Destination station EVA code or meta-code (default: 5100234 = Przemyśl Główny)
  date   Travel date in DD.MM.YYYY format (default: today)

Options:
  -h, --help  Show this help

Station codes:
  German EVA:  8002041 (Frankfurt Süd), 8010366 (Weimar), 8010101 (Erfurt)
  Czech:       5457076 (Praha hl.n.), 5434364 (Ostrava hl.n.)
  Polish:      5100234 (Przemyśl Główny)
  Meta:        PRZEMYSL, PRAHA, OSTRAVA, KRAKOW, DRESDEN, BRATISLAVA

Examples:
  python leo-currency.py                                  # Frankfurt Süd → Przemyśl
  python leo-currency.py 5457076 5434364 25.07.2026       # Praha → Ostrava
  python leo-currency.py 8010366 PRZEMYSL 01.08.2026      # Weimar → Przemyśl
"""

import json
import sys
import platform
import subprocess
import re
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURL = 'curl.exe' if platform.system() == 'Windows' else 'curl'

if '-h' in sys.argv or '--help' in sys.argv:
    print(__doc__)
    sys.exit(0)

FROM = sys.argv[1] if len(sys.argv) > 1 else "8002041"
TO = sys.argv[2] if len(sys.argv) > 2 else "5100234"
DATE = sys.argv[3] if len(sys.argv) > 3 else datetime.now().strftime("%d.%m.%Y")

ENDPOINT = "https://graph.leoexpress.com/le"

# Leo Express internal fixed rates (from creditExchangeRates API)
LEO_RATES = {"EUR": 24, "CZK": 1, "PLN": 5}  # all relative to CZK

# Fallback rates if ECB is unreachable
FALLBACK_CZK = {"EUR": 24.25, "CZK": 1, "PLN": 5.64}


def fetch_ecb_rates():
    """Fetch live EUR/CZK and EUR/PLN from ECB daily reference rates."""
    try:
        result = subprocess.run(
            [CURL, '-s', '--max-time', '5',
             'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'],
            capture_output=True, text=True, encoding='utf-8'
        )
        xml = result.stdout
        czk_match = re.search(r"currency='CZK'\s+rate='([0-9.]+)'", xml)
        pln_match = re.search(r"currency='PLN'\s+rate='([0-9.]+)'", xml)
        if czk_match and pln_match:
            czk_rate = float(czk_match.group(1))
            pln_rate = float(pln_match.group(1))
            pln_in_czk = czk_rate / pln_rate
            return {"EUR": czk_rate, "CZK": 1, "PLN": pln_in_czk}, True
    except Exception:
        pass
    return FALLBACK_CZK, False


MARKET_CZK, ecb_live = fetch_ecb_rates()

QUERY = """query searchConnections($from: String, $to: String, $date: String, $persons: [RateArgument], $services: [ServiceArgument], $currency: String, $locale: String, $platform: String) {
  searchResults(from: $from, to: $to, date: $date, persons: $persons, services: $services, currency: $currency, locale: $locale, platform: $platform) {
    connections {
      lines { line_id }
      classes { id short name }
      class_info { record_id capacity total rates { price count } }
      currency
    }
    error { code message }
  }
}"""


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


def query_currency(currency):
    variables = {
        "from": FROM, "to": TO, "date": DATE,
        "persons": [{"name": "adult", "cards": []}],
        "services": [], "locale": "de", "currency": currency, "platform": "website",
    }
    data = graphql({"operationName": "searchConnections", "query": QUERY, "variables": variables})
    results = data.get("data", {}).get("searchResults", {})
    if results.get("error"):
        return None, results["error"]["message"]
    conns = results.get("connections", [])
    if not conns:
        return None, "no connections"
    conn = conns[0]
    classes = {c["id"]: c for c in conn.get("classes", [])}
    prices = {}
    for ci in conn.get("class_info", []):
        cls = classes.get(ci["record_id"], {})
        short = cls.get("short", ci["record_id"])
        rates = ci.get("rates", [])
        prices[short] = rates[0]["price"] if rates else ci.get("total", 0)
    return prices, conn.get("lines", [{}])[0].get("line_id", "?")


def recommendation(arbitrage_pct, best_currency, max_saving):
    """Generate a buying recommendation based on current rates."""
    lines = []
    lines.append("")
    lines.append("  ┌─────────────────────────────────────────────────────────────┐")

    if best_currency == "EUR" or max_saving < 0.5:
        lines.append("  │  💶 EMPFEHLUNG: In EUR buchen                              │")
        lines.append("  │                                                             │")
        lines.append("  │  Kein relevanter Preisvorteil durch Fremdwährung.           │")
        lines.append("  │  EUR vermeidet Wechselkursgebühren und Aufwand.             │")
    elif best_currency == "CZK" and arbitrage_pct >= 3:
        lines.append("  │  🇨🇿 EMPFEHLUNG: In CZK buchen (Wise/Revolut)               │")
        lines.append(f"  │                                                             │")
        lines.append(f"  │  Ersparnis: ~{arbitrage_pct:.0f}% (bis {max_saving:.1f}€ pro Ticket)              │")
        lines.append("  │  Leo rechnet 24 CZK/EUR, Markt gibt mehr — lohnt sich.     │")
        lines.append("  │  Weg: Währung auf CZK → Suche → Google Pay → Karte.        │")
    elif best_currency == "CZK" and arbitrage_pct >= 1:
        lines.append("  │  🇨🇿 CZK marginal günstiger — Aufwand abwägen               │")
        lines.append(f"  │                                                             │")
        lines.append(f"  │  Ersparnis: ~{arbitrage_pct:.1f}% (bis {max_saving:.1f}€ pro Ticket)              │")
        lines.append("  │  Nur lohnenswert bei teurem Ticket + kostenloser Karte.     │")
        lines.append("  │  Bei Gebühren (Kartenwechselkurs) → EUR nehmen.             │")
    elif best_currency == "PLN":
        lines.append("  │  🇵🇱 EMPFEHLUNG: In PLN buchen                              │")
        lines.append(f"  │                                                             │")
        lines.append(f"  │  Ersparnis: bis {max_saving:.1f}€ pro Ticket                       │")
        lines.append("  │  Ungewöhnlich — PLN ist selten die günstigste Option.       │")

    lines.append("  └─────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)


def main():
    print(f"Leo Express Currency Comparison: {FROM} → {TO}, {DATE}")
    print("=" * 75)

    results = {}
    line_id = "?"
    for currency in ["EUR", "CZK", "PLN"]:
        prices, info = query_currency(currency)
        if prices is None:
            print(f"  {currency}: ERROR — {info}")
            return
        results[currency] = prices
        line_id = info

    print(f"  Line: {line_id}\n")
    print(f"  {'Class':<18} {'EUR':>8} {'CZK':>9} {'PLN':>8} │ {'CZK cost':>8} {'PLN cost':>8} {'Save':>6} {'Best'}")
    print(f"  {'─'*85}")

    class_order = ["ECO", "ECOPLUS", "BUS", "PRE", "ECOSLEEPER", "ECOSLEEPERLADY"]
    class_names = {
        "ECO": "Economy", "ECOPLUS": "Eco Plus", "BUS": "Business",
        "PRE": "Premium", "ECOSLEEPER": "Sleeper", "ECOSLEEPERLADY": "Sleeper Lady"
    }

    max_saving = 0
    overall_best = "EUR"
    best_counts = {"EUR": 0, "CZK": 0, "PLN": 0}

    for cls in class_order:
        if cls not in results["EUR"]:
            continue

        eur = results["EUR"].get(cls, 0)
        czk = results["CZK"].get(cls, 0)
        pln = results["PLN"].get(cls, 0)

        # Real cost in EUR at market exchange rates
        czk_real_eur = czk / MARKET_CZK["EUR"]
        pln_real_eur = pln * MARKET_CZK["PLN"] / MARKET_CZK["EUR"]

        options = {"EUR": eur, "CZK": czk_real_eur, "PLN": pln_real_eur}
        best = min(options, key=options.get)
        saving = eur - options[best]
        save_str = f"{saving:.1f}€" if saving > 0.3 else "—"
        best_str = best if saving > 0.3 else "="

        if saving > max_saving:
            max_saving = saving
        if saving > 0.3:
            best_counts[best] += 1

        print(f"  {class_names.get(cls, cls):<18} {eur:>6.1f} € {czk:>7.0f} Kč {pln:>6.1f} zł │ {czk_real_eur:>7.2f}€ {pln_real_eur:>7.2f}€ {save_str:>6} {best_str}")

    # Determine overall best currency
    if best_counts["CZK"] > best_counts["PLN"] and best_counts["CZK"] > 0:
        overall_best = "CZK"
    elif best_counts["PLN"] > best_counts["CZK"] and best_counts["PLN"] > 0:
        overall_best = "PLN"
    else:
        overall_best = "EUR"

    rate_source = "ECB live" if ecb_live else "fallback (ECB unreachable)"
    arbitrage = (MARKET_CZK["EUR"] - LEO_RATES["EUR"]) / MARKET_CZK["EUR"] * 100

    print(f"\n  Leo internal: 1 EUR = {LEO_RATES['EUR']} CZK, 1 PLN = {LEO_RATES['PLN']} CZK")
    print(f"  Market rates: 1 EUR = {MARKET_CZK['EUR']:.3f} CZK, 1 PLN = {MARKET_CZK['PLN']:.3f} CZK ({rate_source})")
    print(f"  CZK arbitrage: {arbitrage:.1f}% (market {MARKET_CZK['EUR']:.3f} vs Leo {LEO_RATES['EUR']})")

    print(recommendation(arbitrage, overall_best, max_saving))


if __name__ == "__main__":
    main()
