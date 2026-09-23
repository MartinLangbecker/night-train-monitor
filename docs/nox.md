# NOX Mobility

German night-train startup ([noxmobility.com](https://noxmobility.com)). Public REST/JSON API at `api.noxmobility.com`, no auth, CORS-enabled (`Origin: https://noxmobility.com`).

## Route

One route so far: **Hamburg Hbf ↔ München Hbf** (via Bremen and Augsburg, ~10h 51m).

- **1791** southbound (Hamburg → München), **1790** northbound (München → Hamburg).
- Same physical unit, `train.name = "NOX2"`.
- Season **2027-03-23 .. 2027-12-10**, ~6 days/week (one rest day per week, ES-like).
- 4 municipalities in the whole network: Hamburg, Bremen, Augsburg, München.

## Station IDs (municipality UUIDs)

| City | UUID | DB code |
|------|------|---------|
| Hamburg | `aa8c46ab-660f-4a1d-9422-1dd1d1d8e045` | HH |
| München | `9fb61762-46bf-462f-9e1a-a859d96a87ac` | M |
| Bremen | `9b341d10-f83b-4a5a-bf31-88b19fdb2d00` | HB |
| Augsburg | `6469cec1-d997-4e19-a7ff-ba4a0e85e769` | A |

## Capacity — directly exposed (no tier scanning)

Unlike LEO/RDC/SJ, NOX returns **real remaining capacity** in the search response:

```json
"availability": {"total": 78, "available": 46, "status": "available"}
```

So `capacity = available` is exact — no multi-passenger probing or tier
reconstruction. `total` varies by date (observed 58 and 116) as the consist /
contingent changes, so it is stored per snapshot, not assumed constant.

Price is dynamic and loosely tracks fill (e.g. 50/58 → 107 €, empty → 65 €), but
capacity comes straight from `available`.

## Endpoints used by the scraper

| Endpoint | Purpose |
|----------|---------|
| `GET /api/trips/fare-calendar?from=&to=&dateFrom=&dateTo=&adults=1` | Per-day status (`available` / `no_service`). **Max 62-day range** per request (HTTP 400 beyond). |
| `GET /api/trips/search?from=&to=&date=&adults=1` | Trip with `availability` + per-tariff prices. |

Scraper flow per direction: fare-calendar (chunked ≤62 days) to find service
days, then one `search` per available day. ~2×95 requests over the full season —
far lighter than the tier-scanning providers.

## Tariffs

Two classes: **Basic** (`TICKET_BASIC`) and **Flex** (`TICKET_FLEX`). Prices are
plain EUR numbers. Child fare = 75 % of adult, infants free; VAT 10 %.

## Snapshot format

`data/nox/YYYYMMDD_<from>-<to>.json`, one file per direction:

```json
{
  "2027-03-25": {"trainNumber": "1791", "available": 48, "total": 58,
                 "status": "available",
                 "classes": [{"type": "Basic", "price": 107},
                             {"type": "Flex", "price": 157}]},
  "2027-03-26": {"info": "no service"},
  "2027-03-27": {"__error__": "HTTP 500: ..."}
}
```

`load_nox_snapshot` (in `lib/loaders.py`) maps this to the unified
`{travel_date: {class: {capacity, price}}}` with `capacity = available`.

## Scraper

```bash
python3 scrapers/nox_availability.py <fromId> <toId> --days 445 -q -o data/nox
```

Wired into `bin/run-all.sh` (2 directions, `--days 445` reaches the season end).

## Notes

- No auth anywhere; payment (not scraped) is handed off to SumUp.
- Backend is NestJS: errors use `{statusCode, error, message, path, timestamp}`;
  validation `message` is an array of strings.
- Full booking API (prepare → booking → ancillaries → pay) is documented in the
  `night-train-apis` repo (`noxmobility-api.yaml`, skill); only search/capacity
  is relevant for monitoring.
