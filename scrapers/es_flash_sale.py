"""
European Sleeper Flash Sale Scraper

Fetches the European Sleeper "Flash Sale" campaign landing pages and extracts
the discounted deal dates. The Flash Sale is a separate, time-limited campaign
(distinct from the ongoing last-minute landing pages): it has its own URLs
(/flash-sale and /flash-<a>-<b>) and a fixed campaign end date. Unlike the
last-minute pages, the Flash Sale currently also covers the Brussels-Milan route.

The per-page DOM is identical to the last-minute pages (div-tab-0 / div-tab-1
with <button name="price"> entries), so the same parser is reused.

Usage:
  python es_flash_sale.py [-o FILE] [-q]

Options:
  -o, --output F  Save results to file (default: stdout)
  -q, --quiet     No console output

Output format:
  JSON with all active flash-sale deals grouped by page/direction, plus the
  detected campaign end date. When all pages are empty or unreachable (e.g.
  after the campaign ends and the pages are taken down), the scraper reports
  campaignActive=false and exits early rather than writing noise.

Cron:
  25 6 * * * cd ~/Projects/night-train-monitor/data && python3 ~/Projects/night-train-monitor/scrapers/es_flash_sale.py -q -o "$(date +%Y%m%d)_flash-sale.json"
"""

import json
import sys
import re
import subprocess
import platform
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CURL = 'curl.exe' if platform.system() == 'Windows' else 'curl'

PAGES = [
    {
        "slug": "flash-brussels-milan",
        "url": "https://europeansleeper.eu/flash-brussels-milan",
        "direction": "Brussels/Cologne → Switzerland/Milan",
    },
    {
        "slug": "flash-milan-brussels",
        "url": "https://europeansleeper.eu/flash-milan-brussels",
        "direction": "Milan/Switzerland → Cologne/Brussels",
    },
    {
        "slug": "flash-paris-berlin",
        "url": "https://europeansleeper.eu/flash-paris-berlin",
        "direction": "Paris/Brussels → Hamburg/Berlin",
    },
    {
        "slug": "flash-berlin-paris",
        "url": "https://europeansleeper.eu/flash-berlin-paris",
        "direction": "Berlin/Hamburg → Brussels/Paris",
    },
    {
        "slug": "flash-prague-brussels",
        "url": "https://europeansleeper.eu/flash-prague-brussels",
        "direction": "Prague/Berlin → Amsterdam/Brussels",
    },
    {
        "slug": "flash-brussels-prague",
        "url": "https://europeansleeper.eu/flash-brussels-prague",
        "direction": "Brussels/Amsterdam → Berlin/Prague",
    },
]

# Also used to detect the campaign end date ("Offer ends 6 October").
OVERVIEW_URL = "https://europeansleeper.eu/flash-sale"


def fetch_page(url):
    """Fetch HTML of a page. Returns (html, ok) where ok is False on a
    transport error or an obvious error page (non-200)."""
    try:
        result = subprocess.run(
            [CURL, '-sS', '-L', '-w', '\n%{http_code}', url],
            capture_output=True, text=True, encoding='utf-8', timeout=30
        )
    except (subprocess.TimeoutExpired, OSError):
        return '', False

    body = result.stdout or ''
    # Last line carries the HTTP status code (from -w).
    status = None
    nl = body.rfind('\n')
    if nl >= 0:
        tail = body[nl + 1:].strip()
        if tail.isdigit():
            status = int(tail)
            body = body[:nl]
    ok = status is not None and 200 <= status < 400
    return body, ok


def parse_deals(html):
    """Extract deal dates and price IDs from the page HTML.

    The page has two tab divs:
      <div id="div-tab-0"> = CLASSIC (shared couchette)
      <div id="div-tab-1"> = CLASSIC PRIVATE

    Each contains date entries followed by <button name="price" value="{id}">.
    (Identical DOM to the last-minute pages.)
    """
    months = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
              'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

    def extract_from_section(section_html):
        deals = []
        pattern = re.compile(
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2})'
            r'.*?name="price".*?value="(\d+)">'
            r'.*?&euro;(\d+)',
            re.DOTALL
        )
        for match in pattern.finditer(section_html):
            day, month_str, year, price_id, price = match.groups()
            full_year = 2000 + int(year)
            month = months.get(month_str, 0)
            if month == 0:
                continue
            date_str = f"{full_year}-{month:02d}-{int(day):02d}"
            deals.append({"date": date_str, "priceId": int(price_id), "price": int(price)})
        return deals

    shared_deals = []
    private_deals = []

    tab0_start = html.find('id="div-tab-0"')
    tab1_start = html.find('id="div-tab-1"')

    if tab0_start >= 0 and tab1_start >= 0:
        shared_deals = extract_from_section(html[tab0_start:tab1_start])
        private_deals = extract_from_section(html[tab1_start:])
    elif tab0_start >= 0:
        shared_deals = extract_from_section(html[tab0_start:])
    else:
        shared_deals = extract_from_section(html)

    return shared_deals, private_deals


def parse_offer_end(html):
    """Extract the campaign end date, e.g. 'Offer ends 6 October' -> 2026-10-06.
    Returns an ISO date string or None."""
    months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5,
              'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10,
              'november': 11, 'december': 12}
    m = re.search(r'ends\s+(\d{1,2})\s+([A-Za-z]+)', html)
    if not m:
        return None
    day = int(m.group(1))
    month = months.get(m.group(2).lower())
    if not month:
        return None
    # Campaign is in the current/next year; use current year (campaign is short-lived).
    year = datetime.now().year
    return f"{year}-{month:02d}-{day:02d}"


def main():
    args = sys.argv[1:]
    output_file = None
    quiet = False

    i = 0
    while i < len(args):
        if args[i] in ('-o', '--output') and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] in ('-q', '--quiet'):
            quiet = True
            i += 1
        elif args[i] in ('-h', '--help'):
            print(__doc__)
            sys.exit(0)
        else:
            i += 1

    timestamp = datetime.now().isoformat(timespec='seconds')

    # Detect campaign end date from the overview page.
    overview_html, overview_ok = fetch_page(OVERVIEW_URL)
    offer_ends = parse_offer_end(overview_html) if overview_ok else None

    results = {
        "timestamp": timestamp,
        "campaign": "flash-sale",
        "offerEnds": offer_ends,
        "campaignActive": True,
        "pages": [],
    }

    reachable_pages = 0
    for page in PAGES:
        if not quiet:
            print(f"Fetching {page['slug']}...", end=' ')

        html, ok = fetch_page(page['url'])
        if ok:
            reachable_pages += 1
            if not offer_ends:
                offer_ends = parse_offer_end(html)
                results["offerEnds"] = offer_ends
        shared, private = parse_deals(html) if ok else ([], [])

        results["pages"].append({
            "slug": page['slug'],
            "direction": page['direction'],
            "reachable": ok,
            "shared": shared,
            "private": private,
        })

        if not quiet:
            if ok:
                print(f"{len(shared)} shared, {len(private)} private deals")
            else:
                print("unreachable")

    total_shared = sum(len(p['shared']) for p in results['pages'])
    total_private = sum(len(p['private']) for p in results['pages'])
    total = total_shared + total_private

    # Early return / abort when the campaign is over: every page is either
    # unreachable (pages taken down) or empty (no deals left). Mark it as
    # inactive so downstream tooling and the snapshot history show the end
    # cleanly instead of a silent empty file that looks like a scraper fault.
    if reachable_pages == 0 or total == 0:
        results["campaignActive"] = False
        if not quiet:
            if reachable_pages == 0:
                print("\nAll flash-sale pages unreachable — campaign likely ended.")
            else:
                print("\nNo flash-sale deals on any page — campaign likely ended.")

    if not quiet and results["campaignActive"]:
        print(f"\nTotal: {total_shared} shared + {total_private} private = {total} deals")
        if offer_ends:
            print(f"Offer ends: {offer_ends}")
        print()
        for p in results['pages']:
            print(f"  {p['slug']}:")
            for d in p['shared']:
                print(f"    {d['date']}  shared   €{d['price']}")
            for d in p['private']:
                print(f"    {d['date']}  private  €{d['price']}")
            if not p['shared'] and not p['private']:
                print("    (no deals)")
            print()

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        if not quiet:
            print(f"Saved to {output_file}")
    elif quiet:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
