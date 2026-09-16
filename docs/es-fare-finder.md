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
