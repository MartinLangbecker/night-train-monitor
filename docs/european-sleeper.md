# European Sleeper

## Routes

| Train | Route | Frequency | Since |
|-------|-------|-----------|-------|
| ES 474/475 | Berlin – Hamburg – Amsterdam – Brussels – Paris | 3×/week (Di/Do/Sa) | 2024 |
| ES 453/454 | Amsterdam – Rotterdam – Brussels – Dresden – Bad Schandau – Prague | 3×/week | 2023 |
| ES 400/401 | Brussels – Köln – Aachen – Aarau – Arth-Goldau – Göschenen – Bellinzona – Lugano – Como – Milano | 2×/week (Mo/Do + Mi/So) | 09.09.2026 |


## Timetable API

Tagesaktuelle Fahrpläne (mit Bauarbeits-Umleitungen) über die Website:

```
POST https://europeansleeper.eu/timetable/run
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest

departure-date-sql=2026-9-11&r=0
```

### Route-IDs (`r` Parameter)

| r | Zug | Richtung |
|---|-----|----------|
| 0 | Alle | Alle Züge des Tages |
| 1 | ES 453 | Brüssel → Prag |
| 2 | ES 452 | Prag → Brüssel |
| 5 | ES 475 | Paris → Berlin |
| 6 | ES 474 | Berlin → Paris |
| 7 | ES 401 | Brüssel → Milano |
| 8 | ES 400 | Milano → Brüssel |

### Response

HTML-Fragment mit `<div id="452">`, `<div id="474">` etc. pro Zug.
Jeder Zug enthält Halte mit Abfahrt und optional Ankunft (`<i>Arrival HH:MM</i>`).

### Halte (Regelbetrieb, variiert bei Bauarbeiten)

**ES 453/452 (Brüssel ↔ Prag):**
Bruxelles-Midi – Antwerpen – Roosendaal – Amsterdam Bijlmer ArenA – Utrecht – Arnhem – Berlin Gesundbrunnen – Dresden – Bad Schandau – Děčín – Ústí nad Labem – Prague

**ES 474/475 (Berlin ↔ Paris):**
Berlin Gesundbrunnen – Hamburg-Harburg – Bruxelles-Midi – (Liège-Guillemins nur Ri. Berlin) – Mons – Aulnoye-Aymeries – Paris Nord

**ES 401/400 (Brüssel ↔ Milano):**
Bruxelles-Midi – Verviers – Aachen – Köln – Aarau – Arth-Goldau – Göschenen – Bellinzona – Lugano – Como S. Giovanni – Milano Garibaldi

### Hinweise

- Halte variieren je nach Betriebslage (Bauarbeiten). Der Standard-Jahresfahrplan auf der Website nennt z.B. Berlin Hbf + Ostbahnhof und Amsterdam Centraal, das tagesaktuelle Picking zeigt aber Berlin Gesundbrunnen und Amsterdam Bijlmer ArenA.
- Referenz: https://europeansleeper.eu/de/timetable
- Datum-Format: `YYYY-M-D` (kein Zero-Padding)
- ÖBB Scotty Zugsuche (alle Fahrplanvarianten + Verkehrstage): https://fahrplan.oebb.at/bin/trainsearch.exe/dn?trainname=ES+{NR} (z.B. ES+453, ES+474, ES+400)
## Service Overview

- Type: Overnight train
- Booking horizon: ~365 days ahead (from 08.09.2026: Spring + Summer 2027 open)
- Currency: EUR only (no multi-currency arbitrage)
- Operator: European Sleeper Exploitatie B.V. (Utrecht)

## Scraper Usage

```bash
# Interactive
python3 scrapers/es_availability.py hamburg paris --days 183

# Quiet with JSON output
python3 scrapers/es_availability.py hamburg paris --days 183 -q -o data/es/20260813_hamburg-paris.json

# Last-minute deals page
python3 scrapers/es_last_minute.py -q -o data/es/20260813_last-minute-deals.json
```

Options:
```
  <from> <to>       Station names (substring match) or EVA numbers
  [YYYY-MM]         Month to query (optional, use --days instead)
  --days N          Query N days from today
  --json            Auto-named output
  -o, --output F    Custom output file
  -q, --quiet       No console output
```

## Data Model

```json
{
  "2026-08-19": {
    "date": "2026-08-19",
    "train": "474",
    "classes": [
      {"type": "couchette-5", "free": 240, "price": 129.99, "fares": {"easy-night": 129.99, "good-night": 159.99, "flex-night": 169.99}},
      {"type": "couchette-5-women-only", "free": 242, "price": 129.99, "fares": {...}},
      {"type": "berth-double", "free": 1, "price": 359.99, "fares": {...}},
      {"type": "comfort-single", "free": null, "price": null, "fares": {}}
    ]
  },
  "2026-08-18": {"info": "no service"}
}
```

- `free` = remaining capacity (can be null for sold-out classes)
- `price` = lowest fare (easy-night)
- `fares` = all fare variants with separate prices

## Analysis (es-compare.py)

```bash
python3 tools/compare.py diff --provider es --route hamburg-paris
python3 tools/compare.py trend --provider es --route hamburg-paris --date 2026-09-15
python3 tools/compare.py anomaly --provider es --route hamburg-paris
python3 tools/es_deals.py hamburg-paris
python3 tools/compare.py routes
```

## European Sleeper Pass

Unlimited travel on all ES routes. Only reservation fee on top (fixed prices, no yield management).

### Pass Prices

| Pass | Validity | Adult (12+) | Child (4–11) |
|------|----------|-------------|--------------|
| Holiday Traveller | 1 month | 149€ | 99€ |
| Extended Traveller | 3 months | 299€ | 199€ |
| Frequent Traveller | 12 months | 799€ | 499€ |

Conditions:
- Pass must be valid on arrival day
- Non-refundable, non-transferable
- Reservations: 100% refundable up to 30 days before, 50% up to 15 days

### Reservation Prices (fixed, year-round)

| Class | Reservation | Normal ticket (yield) |
|-------|-------------|----------------------|
| Budget (Seat) | 11–21€ | 15–170€ |
| Classic 5-person (shared) | 64–74€ | 80–220€ |
| Classic Private (5 pers.) | 229–269€ | 270–1070€ |
| Comfort Triple | 79–99€ | 96–226€ |
| Comfort Double | 119–139€ | 126–326€ |
| Comfort Single | 149–169€ | 286–676€ |
| Comfort Plus Triple | 89–109€ | 130–260€ |
| Comfort Plus Double | 129–149€ | 160–360€ |
| Comfort Plus Single | 159–179€ | 320–710€ |

### Break-Even Analysis

| Pass | Fahrten | Cost/trip (Couchette) | Cost/trip (Comfort Double) |
|------|---------|----------------------|---------------------------|
| Holiday (149€) | 2 | 144€ | 204€ |
| Holiday (149€) | 4 | 106€ | 166€ |
| Extended (299€) | 6 | 119€ | 179€ |
| Extended (299€) | 8 | 106€ | 166€ |
| Frequent (799€) | 12 | 136€ | 196€ |
| Frequent (799€) | 24 | 102€ | 162€ |

### Strategy with Price Monitoring

| Ticket Tier | Recommendation |
|-------------|---------------|
| T1–T2 (60–90€) | Book normally (cheaper than any pass) |
| T3–T4 (110–160€) | Pass worthwhile from 2+ trips/month |
| T5+ (170€+) | Pass worthwhile from 1–2 trips |
| Sold out | Pass + reservation as fallback |

### Open Questions

- Separate reservation contingent for pass holders?
- Can pass holders reserve on sold-out trains?
- Does the pass cover new routes that launch during validity?

## Booking Window Extension (August 2026)

ES newsletter 27.08.2026: From 8 September 2026, Spring + Summer 2027 bookings open. First time two seasons are released at once.

Scraper window extended from 183 to 365 days (`bin/run-all.sh`) to capture the full booking range. Non-service dates are stored as `{"info": "no service"}` entries with negligible file size.

Also announced: New route Brussels/Amsterdam → Copenhagen/Malmö with RDC from April 2028 (3×/week, Budget/Classic/Comfort + potential Deluxe class with double bed and private shower).

## Fare Finder (Price Calendar)

Seit August 2026 bietet European Sleeper einen "Good Fare Finder" auf der Website an (Beta).
Technisch ein PHP-basiertes Calendar-Frontend auf `europeansleeper.eu`, unabhängig von der
Azure Booking-API.

### Endpoints

```
POST https://europeansleeper.eu/price-calendar/tab
POST https://europeansleeper.eu/price-calendar/calendar
POST https://europeansleeper.eu/price-calendar/receipt
```

Alle Endpoints liefern **HTML-Fragmente** (kein JSON). Content-Type: `application/x-www-form-urlencoded`.

### Headers (erforderlich)

```
x-requested-with: XMLHttpRequest
origin: https://europeansleeper.eu
referer: https://europeansleeper.eu/fare-finder
content-type: application/x-www-form-urlencoded; charset=UTF-8
```

Session-Cookie (`PHPSESSID`) optional — funktioniert auch ohne, aber der Tab-Endpoint
initialisiert den serverseitigen State.

### Workflow

1. **`/price-calendar/tab`** — Route + Passagiere setzen, liefert Compartment-Auswahl als HTML
2. **`/price-calendar/calendar`** — Monatskalender mit Preisen pro Tag für gewählte Klasse
3. **`/price-calendar/receipt`** — Preisdetails für eine konkrete Verbindung

### Parameter (tab)

```
departureStation=8020401        # EVA-Nummer
arrivalStation=8700015          # EVA-Nummer
ticket=retour                   # retour | single
passengerTypes-72=1             # Erwachsene
passengerTypes-73=0             # Kinder (4–11)
passengerTypes-44=0             # Interrail-Reservierung
petCount=0
b-voornaam=                     # Vorname (leer = anonym)
b-achternaam=                   # Nachname
b-email=
b-telefoon=
```

### Parameter (calendar, zusätzlich)

```
compartment=2                   # Klassen-ID (aus Tab-Response)
train_compartments_id=5         # Compartment-Typ-ID
3-sharing=shared                # Sharing-Modus pro Klasse
2-sharing=shared
4-sharing=shared
1-sharing=shared
cal-off[outward]=0              # Monats-Offset (0=aktuell, 1=nächster)
cal-off[return]=0
```

### Compartment-IDs (beobachtet)

| compartment | train_compartments_id | Klasse |
|---|---|---|
| 3 | ? | Budget (Sitzplatz) |
| 2 | 5 | Classic (5er Couchette, shared) |
| 4 | ? | Comfort Standard |
| 1 | ? | Comfort Plus |

### Response-Format (calendar)

HTML-Tabelle mit `<td>` pro Tag:

```html
<!-- Verfügbar -->
<td data-date="20260826" rel="outward-20260826">
  26 <span class="text-shock-orange">
    <i class="text-xs">&euro;</i> 189 <small class="text-xs">99</small>
  </span>
</td>

<!-- Ausverkauft -->
<td ...>
  24 <span class="line-through text-light-aubergine">
    <i class="text-xs">&euro;</i> 189 <small class="text-xs">99</small>
  </span>
</td>

<!-- Kein Betrieb -->
<td class="blanco">25</td>
```

- `text-shock-orange` = buchbar
- `line-through text-light-aubergine` = ausverkauft (Preis trotzdem sichtbar!)
- `class="blanco"` ohne data-date = kein Betriebstag

### Vergleich mit Azure Booking-API

| | Fare Finder (PHP) | Azure-API |
|---|---|---|
| Format | HTML | JSON |
| Scope pro Request | 1 Monat, 1 Klasse | 1 Tag, alle Klassen |
| Kapazität (free seats) | Nein (nur OK/SOLD) | Ja |
| Fare-Varianten | Nein (nur günstigster) | Ja (easy/good/flex) |
| Auth | Session-basiert | Keine |
| Vorteil | Schneller Überblick, Ausverkauft-Status | Vollständige Daten |

### Parsing-Regex

```python
import re
td_pattern = re.compile(
    r'<td[^>]*data-date="(\d{8})"[^>]*rel="(outward|return)-\d+"[^>]*>\s*'
    r'(\d+)\s*'
    r'<span class="([^"]*)">\s*'
    r'<i[^>]*>&euro;</i>\s*'
    r'(\d+)\s*'
    r'<small[^>]*>(\d+)</small>',
    re.DOTALL
)
# Groups: (date, direction, day, css_class, price_whole, price_cents)
# css_class contains "line-through" → sold out
```
