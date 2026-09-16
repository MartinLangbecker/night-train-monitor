"""
European Sleeper Last-Minute Deals Scraper

Fetches the 4 last-minute landing pages and extracts available deal dates.
Tracks prices (which vary per date) and which dates
have deals available or disappear over time.

Usage:
  python es-last-minute.py [-o FILE] [-q]

Options:
  -o, --output F  Save results to file (default: stdout)
  -q, --quiet     No console output

Output format:
  JSON with all active deals grouped by page/direction.

Cron:
  20 6 * * * cd ~/Projects/es-availability/data && python3 ~/Projects/es-availability/es-last-minute.py -q -o "$(date +%Y%m%d)_last-minute-deals.json"
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
        "slug": "hamburg-berlin",
        "url": "https://www.europeansleeper.eu/last-minutes-hamburg-berlin",
        "direction": "Paris/Brussels → Hamburg/Berlin",
        "train": "475",
    },
    {
        "slug": "brussels-paris",
        "url": "https://www.europeansleeper.eu/last-minutes-brussels-paris",
        "direction": "Hamburg/Berlin → Paris/Brussels",
        "train": "474",
    },
    {
        "slug": "berlin-prague",
        "url": "https://www.europeansleeper.eu/last-minutes-berlin-prague",
        "direction": "Brussels/Amsterdam → Berlin/Prague",
        "train": "453",
    },
    {
        "slug": "amsterdam-brussels",
        "url": "https://www.europeansleeper.eu/last-minutes-amsterdam-brussels",
        "direction": "Berlin/Prague → Amsterdam/Brussels",
        "train": "454",
    },
]


def fetch_page(url):
    """Fetch HTML content of a page."""
    result = subprocess.run(
        [CURL, '-s', '-L', url],
        capture_output=True, text=True, encoding='utf-8'
    )
    return result.stdout


def parse_deals(html):
    """Extract deal dates and price IDs from the page HTML.
    
    The page has two tab divs:
      <div id="div-tab-0"> = CLASSIC (shared couchette)
      <div id="div-tab-1"> = CLASSIC PRIVATE
    
    Each contains date entries followed by <button name="price" value="{id}">.
    """
    months = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
              'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

    def extract_from_section(section_html):
        """Extract date + priceId + price from a section of HTML."""
        deals = []
        # Date appears before button, price (&euro;NN) inside the button content
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

    # Split HTML into shared and private sections using tab div IDs
    shared_deals = []
    private_deals = []

    tab0_start = html.find('id="div-tab-0"')
    tab1_start = html.find('id="div-tab-1"')

    if tab0_start >= 0 and tab1_start >= 0:
        shared_section = html[tab0_start:tab1_start]
        private_section = html[tab1_start:]
        shared_deals = extract_from_section(shared_section)
        private_deals = extract_from_section(private_section)
    elif tab0_start >= 0:
        shared_deals = extract_from_section(html[tab0_start:])
    else:
        shared_deals = extract_from_section(html)

    return shared_deals, private_deals


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
    results = {"timestamp": timestamp, "pages": []}

    for page in PAGES:
        if not quiet:
            print(f"Fetching {page['slug']}...", end=' ')

        html = fetch_page(page['url'])
        shared, private = parse_deals(html)

        page_data = {
            "slug": page['slug'],
            "direction": page['direction'],
            "train": page['train'],
            "shared": shared,
            "private": private,
        }
        results["pages"].append(page_data)

        if not quiet:
            print(f"{len(shared)} shared, {len(private)} private deals")

    # Summary
    total_shared = sum(len(p['shared']) for p in results['pages'])
    total_private = sum(len(p['private']) for p in results['pages'])

    if not quiet:
        print(f"\nTotal: {total_shared} shared + {total_private} private = {total_shared + total_private} deals")
        print()
        for page_data in results['pages']:
            print(f"  {page_data['slug']} ({page_data['train']}):")
            for d in page_data['shared']:
                print(f"    {d['date']}  shared   €{d['price']}")
            for d in page_data['private']:
                print(f"    {d['date']}  private  €{d['price']}")
            if not page_data['shared'] and not page_data['private']:
                print(f"    (no deals)")
            print()

    # Save
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        if not quiet:
            print(f"Saved to {output_file}")

    elif quiet:
        # If quiet and no output file, still print JSON to stdout
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
