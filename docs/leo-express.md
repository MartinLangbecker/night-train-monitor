# Leo Express (LE232/LE235)

## Service Overview

- Route: Frankfurt (Main) Süd – Weimar – Dresden – Praha – Bohumín – Przemyśl Główny
- Launched: Jul 25, 2026
- Type: Overnight train
- Booking horizon: ~136 days ahead

## Station Codes

| Station | EVA Code |
|---------|----------|
| Frankfurt (Main) Süd | 8002041 |
| Weimar | 8010366 |
| Erfurt | 8010101 |
| Dresden Hbf | 8010085 |
| Praha hl.n. | 5457076 |
| Ostrava hl.n. | 5434364 |
| Bohumín | 5434124 |
| Przemyśl Główny | 5100234 |

Meta-codes: `PRZEMYSL`, `PRAHA`, `OSTRAVA`, `KRAKOW`, `DRESDEN`, `BRATISLAVA`

## Timetable

### Key times (stable across most periods)

| Station | LE232 (→ Frankfurt) | LE235 (→ East) |
|---------|--------------------|--------------------|
| Przemyśl Główny | dep 12:04 | arr 11:25 |
| Bohumín | dep 17:45/17:57 | dep 05:36/06:01 |
| Ostrava hl. n. | dep 17:56/18:05 | dep 05:27 |
| Olomouc hl. n. | dep 19:21 | dep 04:08 |
| Praha hl. n. | dep 22:32 | dep 01:17 |
| Dresden Hbf | dep 01:38 | dep 22:30 |
| Leipzig Hbf | dep 02:54 | dep 20:43 |
| Weimar | dep 04:07 | dep 18:59 |
| Erfurt Hbf | dep 04:23 | dep 18:44 |
| Fulda | dep 05:59 | dep 16:54 |
| Frankfurt/Main-Süd | arr 07:22–07:26 | dep 15:03 |
| Frankfurt Flughafen | arr 07:53 (P6 A) | dep 14:39 (P6 B) |

### Service Periods

| # | Dates | Polish section | Frankfurt Flughafen |
|---|-------|----------------|---------------------|
| 1 | 25.7 – 29.7 | No | No |
| 4 | 1.8 – 29.8 | Variant A only (5 days/wk) | No |
| 5 | 30.8 – 16.9 | No | No |
| 6 | 17.9 – 12.12 | No (pending) | Yes (partial) |

### Beförderungsverbot

Local trips between Polish stations are forbidden — the train cannot be used for domestic Polish travel.

## Rolling Stock

Currently 3 coaches + locomotive. Expansion to up to 8 coaches announced.

| Coach | Class | Seats/Berths | Layout |
|-------|-------|-------------|--------|
| 1 | Economy (ECO) | 69 | Open seating, seats 12-80 |
| 2 | Business (BUS) | 54 | 9 compartments × 6 seats, seats 1-54 |
| 3a | Economy Sleeper (ECOSLEEPER) | 20 | 5 compartments × 4 berths |
| 3b | Economy Sleeper Lady (ECOSLEEPERLADY) | 20 | 5 compartments × 4 berths |
| | **Total** | **163** | |

Sleeper and Sleeper Lady share one coach (10 compartments total, 5+5). Sleeper Lady compartments are women-only.

### Capacity vs. Demand (Aug 2026)

- 163 seats/berths per train, 2 trains/day (LE232 + LE235)
- Observed: ~78 passengers/day average (both directions), ~48% load factor
- Peak days (Fri/Sat): 55-65% load factor
- Weak days (Mon/Tue): 17-27% load factor
- Leo Express claims ~100 pax/day (slightly optimistic based on our data)
- Long-term target: 400 pax/train (requires ~2.5× current capacity, i.e. 6-8 coaches)

### Capacity Anomalies in Scraper Data

- ECO capacity varies by segment: ~136 on Frankfurt-Weimar, ~119 on Weimar-Bohumín, ~63 on full Przemyśl route. Not all 69 physical seats are sold on every segment — some are reserved for boarding passengers at intermediate stops.
- 14-15 Aug 2026: Massive ECO capacity jump (~1500 seats appeared across all dates). Likely a system-wide reallocation or inventory reset.
- 26-27 Aug 2026: +340 Sleeper capacity appeared. Sleeper contingent adjustment.

## Price Reset Events

The API occasionally returns T1 prices (37.50€ Sleeper) for dates that are normally priced at T2–T5 during daytime. Observed twice on Weimar–Bohumín Sleeper:

| Date | Snapshot | T1 share | Notes |
|------|----------|----------|-------|
| 2026-08-15 00:00 | midnight scrape | 78.6% | +24 new Przemyśl dates appeared (Polish section release). New dates naturally start at T1, so partly explained. |
| 2026-08-27 00:00 | midnight scrape | 64.3% | No new dates. Live API check at 16:30 same day shows T2–T5. Confirmed: prices dropped on existing dates, then reverted. |

Hourly monitoring (20:00–03:00 on 27–28 Aug) showed no T1 anomaly — prices were stable at normal tiers throughout the observation window. The Aug 28 midnight scrape also showed no T1.

**Conclusion:** The T1 drops are sporadic, non-reproducible events — likely a server-side inventory or pricing reset that is quickly reverted. Not a regular nightly window. Only Weimar–Bohumín Sleeper was affected; Weimar–Przemyśl remained stable at T3–T6.

## API Notes

GraphQL endpoint: `https://graph.leoexpress.com/le` (requires `Origin: https://www.leoexpress.com` header).

The query field is `searchResults(...)`, not `searchConnections(...)`. The API spec in night-train-apis documents `searchConnections` as the operation name, but the actual resolver field on the Query type is `searchResults`. The `operationName` in the request can be anything (it's just a label); the field name in the query body is what matters.

Response structure uses `class_info` (array of objects with `record_id`, `capacity`, `occupied`, `rates`) separate from `classes` (array with `id`, `short`, `name`). The `record_id` in `class_info` maps to `id` in `classes`. Capacity = `capacity - occupied`.

## Scraper Usage

```bash
# Interactive (table output)
python3 scrapers/leo_availability.py 8010366 5100234 --days 30

# EUR prices, quiet, save to file
python3 scrapers/leo_availability.py 8010366 5100234 --days 136 -q -c EUR -o data/leo/20260813_weimar-przemysl-eur.json

# All 3 currencies
python3 scrapers/leo_all_currencies.py 8010366 5100234 --days 30
```

Options:
```
  --days N          Query N days from today
  -c, --currency C  CZK, EUR, PLN (default: CZK)
  -o, --output F    Save JSON to file
  -q, --quiet       No console output
  --diff            Compare with previous JSON
```

## Data Model

```json
{
  "timestamp": "2026-08-13T00:01:23",
  "from": "8010366",
  "to": "5100234",
  "results": {
    "2026-08-13": {
      "classes": [
        {"class": "BUS", "name": "Business", "capacity": 38, "price": 67.0, "is_promo": false, "cashback": 0},
        {"class": "ECO", "name": "Economy", "capacity": 31, "price": 68.7, ...},
        {"class": "ECOSLEEPER", "name": "Economy Sleeper", "capacity": 7, "price": 137.0, ...},
        {"class": "ECOSLEEPERLADY", "name": "Economy Sleeper Lady", "capacity": 12, "price": 102.9, ...}
      ]
    },
    "2026-08-14": {"info": "no service"},
    "2026-10-15": {"error": "Noch keine Tickets verfügbar"}
  }
}
```

## Currency Notes

- Internal rates: 1 EUR = 24 CZK, 1 PLN = 5 CZK (fixed)
- CZK:PLN perfectly fixed (no arbitrage), PLN not tracked in cron
- CZK:EUR mostly 24:1 with occasional independent EUR pricing
- Real market rate: 1 EUR ≈ 25.3 CZK → paying in CZK saves ~5%

### Paying in CZK

1. Switch currency to CZK (before searching)
2. Book normally
3. At payment: Google Pay → Zpět → Platební karta (credit card)
4. Pay with multi-currency card (Wise/Revolut) → charged in CZK

Direct "credit card" method uses GPWebPay which returns 403. The GoPay route works.

## Service Notes

- Polish section: 5 days/week in August (variant A), pending from September
- Night portion (Frankfurt ↔ Bohumín): daily
- API returns next available train for non-service days; script detects and records `{"info": "no service"}`

## Charts

| Chart | Script | Description |
|-------|--------|-------------|
| `leo-single-date-{route}.png` | `scripts/leo-chart-single-date.py` | Single date: 4 classes with tier, price, capacity |
| `leo-tier-week-{route}.png` | `scripts/leo-chart-week.py` | 7-day view: tier status per class per day |
| `leo-fillrate-{route}.png` | `scripts/leo-chart-fillrate.py` | Fill rate dashboard: 4 panels with occupancy % |

```bash
python3 scripts/leo-chart-single-date.py 2026-08-28 bohumin
python3 scripts/leo-chart-week.py 2026-08-18 bohumin
python3 scripts/leo-chart-fillrate.py bohumin
# Routes: bohumin | przemysl | frankfurt
```

## Data Quality Notes

- The GraphQL endpoint can return an empty response for a single date query. The
  scraper records this as `{"error": "Expecting value: ..."}` for that date
  (`__error__` marker in `lib/loaders.py`). These are skipped by `anomaly_scan`
  and never counted as sellouts. Known occurrences: 165 total, mostly a broad
  outage on 2026-08-23.
- `"Noch keine Tickets verfügbar"` marks future dates before their sales window
  opens — not an error.
- Sellout detection ignores implausible one-step drops from high capacity to zero
  (scrape-window gaps); see `SELLOUT_MAX_PREV_CAP` in `lib/analysis.py` and the
  "Data Quality & Detection Caveats" section in `USE-CASE.md`.
