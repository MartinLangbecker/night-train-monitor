# SJ

## API

- Base URL: `https://prod-api.adp.sj.se`
- Auth: `Ocp-Apim-Subscription-Key` header (key: `d6625619def348d38be070027fd24ff6`)
- Requires `User-Agent` header (403 without)
- REST, no GraphQL, no captcha, no login needed

### Key Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/public/sales/booking/v3/search` | POST | Create search session (returns departureSearchId + passengerListId) |
| `/public/sales/booking/v3/search/{passengerListId}` | PATCH | Modify session: date, route, filters, return journey |
| `/public/sales/booking/v3/departures/search/{id}` | GET | Train connections for a search |
| `/public/sales/booking/v3/departures/{id}/offers` | GET | Prices per class/flex/comfort |

### PATCH /search Behavior

PATCH reuses an existing session (~40 min TTL) to change date, route, and filters without creating a new passenger list.

**Does NOT change passenger count.** The `passengers` field is silently ignored. The sj.se frontend triggers a fresh POST /search when the passenger count changes.

### Search Filters

Night trains only: `{"outboundAdditionalSearchFilters": {"allowedServiceTypes": ["SJ_NT"]}}` — returns only SJ Nattåg departures (1-2 per day vs ~19 total).

Available filter fields: `onlyDirectJourneys`, `allowedServiceTypes`, `excludedServiceTypes`, `departureDateTime`, `arrivalDateTime`, `viaStations`, `interchangeStations`, `minTransferTimeInMinutes`.

### Return Journey

POST/PATCH with `returnDate` + `inboundAdditionalSearchFilters` returns both `departureSearchId` (outbound) and `returnDepartureSearchId` (return = reverse direction). Both share the same `passengerListId`, so offers for both directions can be fetched in one session.

### Budget Calendar

sj.se references a "Budget calendar" (`/en/budget-calendar.html`) for cheapest fares. No dedicated API endpoint exists — the calendar page uses the same search endpoints internally, iterating over dates. The URL currently redirects to the SPA.

## Accommodation Types

| Product | API Code | Capacity | En-suite | Breakfast |
|---|---|---|---|---|
| Sleeping 1st class | `SLEEPER_FIRST_PRIVATE` / `SLEEPER_FIRST_PRIVATE_SOLO` | 1-2 beds | WC + shower | included |
| Sleeping 2nd class shared | `SLEEPER_SECOND_SHARED` | 1-3 beds | — | — |
| Sleeping 2nd class private | `SLEEPER_SECOND_PRIVATE` | 1-3 beds | — | — |
| Couchette shared | `COUCHETTE_SHARED` | up to 6 | — | — |
| Couchette private | `COUCHETTE_PRIVATE` | up to 6 | — | — |

Shared compartments offer gender selection: MEN, LADIES, or MIXED.
Sleeping 2nd class has foldable middle bed (sits 2 by day, sleeps 3 by night).
Couchette: self-service bedding (blanket, pillow, sheets provided).

## Night Trains

| Train | Route | Duration |
|---|---|---|
| D 1/2 | Stockholm ↔ Malmö | 7h42 / 8h04 |
| D 70/71 | Stockholm ↔ Åre/Duved | 9h37 |
| D 91/92 | Stockholm ↔ Umeå | 8h47 |
| D 93/94 | Stockholm ↔ Luleå | 12h23 |

D 1/2 operates ~4-5x/week. D 70/71 similar. Norrland service halved Apr 2026.

## Capacity Probing

### Method

Multi-passenger search: probe the same departure with increasing passenger counts (n=1 up to MAX_N=40). The API returns total price for n passengers. Per-person price = total ÷ n.

When the current tier's contingent is exceeded, the per-person price jumps up for ALL passengers. This reveals tier boundaries:

```
n=1: 435 SEK/pp  → Tier A
n=5: 475 SEK/pp  → Tier B (jump at n=5 → 4 places remain in Tier A)
n=9: 475 SEK/pp  → still Tier B
```

### Adaptive Strategy

1. POST n=1 with same-date return → baseline for both directions (5 API calls)
2. POST n=9 with same-date return → ceiling check (5 calls)
3. If any product price changed: POST n=5 (5 calls)
4. If jump between 1-5: POST n=3 (5 calls). If between 5-9: POST n=7 (5 calls)

Each POST uses `returnDate == departureDate` to get both directions (out + return) in one session. Each probe level requires a fresh POST because PATCH does not change passenger count.

### Request Budget

| Scenario | Sessions (POSTs) | API Calls | Coverage |
|---|---|---|---|
| No jump | 2 | 10 | 1 date × 2 directions (n=1 + n=40 ceiling) |
| Jump detected | 5-7 | 25-35 | 1 date × 2 directions (binary search, logarithmic) |
| No night train | 1 | 5 | 1 date × 2 directions |

120 days × 4 routes: ~1200-2000 API calls, ~30-50 minutes. (MAX_N=40 adds only
~2 probes per date with a jump — binary search is logarithmic in the ceiling.)

### Comparison with RDC

| Property | SJ | RDC |
|---|---|---|
| Max probing | 40 passengers (no API cap) | 5-6 per entity type (hard API cap) |
| Typical contingent | ≥5 per tier (jumps at 5-9) | 2-4 per tier |
| Session reuse | Return journey = 2 dates | Per-connection hash |
| Price field | `journeyPrices.price.amount` (total) | `SinglePrice.Amount` (per person) |
| Classes in 1 response | All seat + bed classes | Batched entity requests |
| Night train filter | `SJ_NT` service type | N/A (only night trains) |

### No API Cap → Absolute Contingent Sizes (verified 2026-09-07)

Unlike RDC (hard cap: API returns nothing above n=6), the SJ API answers for
arbitrary passenger counts. Verified: n=20 and n=40 both return prices; a class
only drops out once the request exceeds that class's **total remaining contingent**
for the date. That drop-out point IS the absolute contingent size.

`MAX_N` was raised 9 → 40 to exploit this. The binary search stays cheap
(logarithmic), so dates without a jump still cost just n=1 + n=MAX_N.

Example (Stockholm→Malmö, snapshot 2026-09-07, NOFLEX):

| Date | Class | First tier jump | Sold out at | Contingent |
|------|-------|-----------------|-------------|-----------|
| 08.09 | SLEEPER_FIRST_PRIVATE_SOLO | — | n=6 | **5** |
| 09.09 | SLEEPER_FIRST_PRIVATE_SOLO | — | n=12 | **11** |
| 13.09 | SLEEPER_SECOND_SHARED | n=13 | n=13 | **12** |
| 08.09 | SLEEPER_SECOND_SHARED | n=17 | — | ≥16 (jump only) |

With the old MAX_N=9 the n=11–17 boundaries were invisible ("≥8"). Now the
absolute size of the SHARED / SOLO contingents is measurable for the common
demand range. Large SECOND/COUCHETTE tiers (>40) can still exceed the window.

**How the tier rises with n** (10.09, per-person): the price steps up each time a
cheaper contingent is exhausted, e.g. SECOND 565→605 at n=4, →645 at n=14, →695 at
n=32; COUCHETTE 1035→1125 at n=6, →1215 at n=14, gone at n=28; SLEEPER 2nd shared
1385→1475 at n=7, gone at n=20. Each jump n means "n-1 places left in the current
tier"; the disappearance n means "n-1 = total places across all tiers".

Caveat unchanged: SECOND prices can move backwards (cancellations), so summing
tier contingents is only clean for the monotonic SHARED sleeper/couchette classes.

### Ausblick: mögliches `capacity`-Feld (aufgeschoben)

Mit MAX_N=40 kennen wir jetzt konkrete Restplatzzahlen im aktuellen (billigsten
verfügbaren) Tier: `places_left = tier_jump_at - 1`. Denkbar wäre, das analog zu
Leo (`capacity`) / ES (`free`) als explizites Feld pro Klasse abzulegen, statt es
aus `tier_jump_at` ableiten zu müssen.

**Entscheidung: vorerst nicht umbauen.** Zuerst mehr Snapshots mit MAX_N=40
sammeln, um das Verhalten über verschiedene Nachfragelagen zu sehen. Erst danach
prüfen, ob `tier_jump_at` in ein abgeleitetes `capacity`/`free = tier_jump_at - 1`
umgewandelt werden soll.

Randbedingungen für einen späteren Umbau:
- Nur das **aktuelle Tier** ist gemeint (Restplätze zum aktuell günstigsten Preis),
  nicht die Gesamtkapazität über alle Tiers.
- `tier_jump_at = null` (kein Sprung im Fenster) → `capacity` wäre „≥ MAX_N", also
  kein exakter Wert. Ein abgeleitetes Feld müsste diesen Fall kennzeichnen.
- Das Rohsignal `tier_jump_at` / `next_tier_price` sollte erhalten bleiben (die
  Tier-Analyse in `sj_tiers.py` baut darauf auf); ein `capacity`-Feld wäre additiv.

### Kapazitäts-Zeitreihenanalyse (`tools/sj_capacity.py`)

Seit dem Snapshot **2026-09-08** (MAX_N 9 → 40) liefert fast jede verfügbare
Klasse eine numerische `capacity = tier_jump_at - 1` (Restplätze im aktuell
günstigsten Tier). `tools/sj_capacity.py` wertet diese Zeitreihe aus.

**Bedeutung von `capacity`:** untere Schranke der echten Restkapazität. Nach der
Tier-Grenze gibt es meist weitere Plätze im nächsten (teureren) Tier. Ein
Kapazitäts-*Rückgang* zwischen zwei Snapshots = so viele Plätze wurden gebucht
(oder die Tier-Grenze hat sich verschoben).

**Datenreife (wichtig für Aussagekraft):**

| Snapshots | Aussage |
|-----------|---------|
| 1 | nur aktuelle Tier-Position (dafür `sj_tiers.py`) |
| 2 | Tages-Delta: Buchungen/Stornierungen (sofort nutzbar) |
| ≥ 7 numerische Punkte | Sellout-Regression via `lib.analysis.sellout_prediction` |

Snapshots **vor** dem 2026-09-08 haben `capacity = None` für jedes Tier mit > 9
freien Plätzen. Diese Punkte dürfen **nicht** in eine Regression einfließen (sie
sehen aus wie fehlende Daten und verfälschen den Trend). `sj_capacity.py`
filtert `None`-Punkte deshalb konsequent heraus und rechnet nur auf der
erweiterten Historie (Default `--since 20260908`).

**Was mit den ersten zwei erweiterten Snapshots (08.→09.09.) möglich war:** ein
belastbares Tages-Delta. Beispiel (3393 Klassen-Datum-Paare mit numerischer
Kapazität in beiden Snapshots): 495 Rückgänge (Buchungen), 168 Anstiege
(Stornierungen/Tier-Reset), Rest unverändert. Für eine Sellout-Prognose reichen
2 Punkte **nicht** — dafür sind ≥ 7 tägliche Snapshots ab dem 08.09. nötig
(also frühestens um den 14.09.).

**Modi:**

```bash
python3 tools/sj_capacity.py                    # Tages-Delta, alle SJ-Routen
python3 tools/sj_capacity.py stockholm-malmoe   # eine Route
python3 tools/sj_capacity.py --min-drop 4       # nur Rückgänge >= 4 Plätze
python3 tools/sj_capacity.py --maturity         # Datenreife-Report pro Klasse
python3 tools/sj_capacity.py --forecast         # Sellout-Prognose wo Daten reichen
python3 tools/sj_capacity.py --since 20260908   # Snapshot-Untergrenze setzen
```

`--maturity` zeigt, wie viele Serien schon regressionsreif sind und wie viele
tägliche Snapshots bis zur ersten Prognose fehlen. `--forecast` nutzt dieselbe
gewichtete lineare Regression wie `bin/analyze.py` (keine eigene Mathematik).

### Private Compartments

PRIVATE comfort types show price *decreases* at higher passenger counts. This is expected: the per-person cost of a private compartment drops when shared (e.g., 2673 SEK/pp at n=1 → 1215 at n=3 for SLEEPER_SECOND_PRIVATE). This is compartment cost-sharing, not a tier boundary.

## Scraper

Script: `scrapers/sj_availability.py` — takes origin + destination as CLI arguments.
Each call produces 2 output files (outbound + return via same-date return journey).

```bash
python3 sj_availability.py 740000001 740000003 --days 120 -q -o data/sj/
# → YYYYMMDD_stockholm-malmoe.json + YYYYMMDD_malmoe-stockholm.json
```

### Routes (configured in `bin/run-all.sh`)

| Route | Origin | Destination | Trains |
|---|---|---|---|
| stockholm-malmoe | 740000001 | 740000003 | D 1/2 |
| stockholm-duved | 740000001 | 740000308 | D 70/71 |
| stockholm-umea | 740000001 | 740000144 | D 91/92 |
| stockholm-lulea | 740000001 | 740000190 | D 93/94 |

Return directions (malmoe-stockholm, etc.) are automatically included via same-date return journey.

### Output

One file per route per crawl: `data/sj/YYYYMMDD_route.json` (8 files per run).

```json
{
  "2026-09-01": {
    "departures": [
      {
        "departureDateTime": "2026-09-01T23:17:00+02:00",
        "serviceName": "1",
        "nightTrain": true,
        "seats": {
          "SECOND": {
            "NOFLEX": {"price": 435, "tier_jump_at": 5, "next_tier_price": 475}
          }
        },
        "beds": {
          "COUCHETTE_SHARED": {
            "NOFLEX": {"price": 775, "tier_jump_at": null, "next_tier_price": null}
          }
        },
        "probed_ns": [1, 5, 9],
        "status": ["AVAILABLE"]
      }
    ]
  },
  "2026-09-02": {
    "info": "no night train departures"
  }
}
```

Fields:
- `price`: per-person price in SEK at n=1
- `tier_jump_at`: passenger count where price increased (n-1 = places remaining in current tier), or null (no jump, ≥9 remain)
- `next_tier_price`: per-person price after jump. `null` with `tier_jump_at` set means the product is sold out at that passenger count (API returns no offers)
- `probed_ns`: which passenger counts were actually tested

### Cron

Midnight via `bin/run-all.sh` (crontab: `0 0 * * *`).

## Competition with Snälltåget

### Stockholm ↔ Malmö

SJ D 1/2 (night, sleeper/couchette) vs Snälltåget IC 3940/3941 (day, seat only). Different product segments.

### Stockholm ↔ Åre/Duved

Direct competition in summer: D 70 (SJ, 22:40→08:04) vs D 24 (Snälltåget, ~22:55→07:35). Nearly identical arrival times. D 70 year-round, D 24 summer only.

### Combo: SJ + Snälltåget

D 1 arr Malmö 06:59 + IC 307 dep 16:15 → Hamburg 21:57 (9h16 layover).
Reverse: IC 306 arr Malmö 15:35 + D 2 dep 22:17 → Stockholm 06:21 (6h42 layover).

## Scotty Gattungen

- SJ night trains: **D** (D 1, D 2, D 70, D 92, D 94)
- Snälltåget day: **IC** (IC 3940, IC 306)
- Snälltåget night: **D** (D 10300, D 300, D 24)

## Beobachtungen (28.-31.08.2026, 4 Tage Daten)

### Pricing-Modell

SJ verwendet kein diskretes Tier-System wie RDC (3-6 feste Stufen). Stattdessen quasi-kontinuierliche dynamische Preise mit ~10 SEK-Inkrementen:

| Klasse | Preisspanne (NOFLEX) | Beobachtete Stufen | Typische Schritte |
|--------|---------------------|-------------------|-------------------|
| SECOND (Sitz) | 195 – 1.675 SEK | 90 | 10 SEK (nach Initialspr. 195→345) |
| COUCHETTE_SHARED | 515 – 2.665 SEK | 110 | 10 SEK |
| SLEEPER_SECOND_SHARED | 695 – 3.375 SEK | 121 | 10-80 SEK |
| SLEEPER_SECOND_PRIVATE | 319 – 5.995 SEK | 132 | unregelmäßig (6-506 SEK) |
| SLEEPER_FIRST_PRIVATE_SOLO | 1.485 – 6.905 SEK | 103 | 10-440 SEK |

SECOND hat einen charakteristischen Initialsprung (195→345 SEK, +150), danach 10er-Schritte. Bei allen Klassen werden die Sprünge am oberen Ende größer (beschleunigte Preiserhöhung bei Knappheit).

### Preisbewegungen (4 Tage)

270 Änderungen in 20 Reisedaten.

| Klasse | Typischer Sprung | Richtung |
|--------|-----------------|----------|
| SECOND | ±40 SEK | bidirektional (Stornierungen!) |
| COUCHETTE_SHARED | +90 SEK | fast nur aufwärts |
| SLEEPER_SECOND_SHARED | +80-90 SEK | nur aufwärts |
| SLEEPER_SECOND_PRIVATE | +176-198 SEK | nur aufwärts |
| SLEEPER_FIRST_PRIVATE_SOLO | +170 SEK | nur aufwärts |

Sitz-Preise bewegen sich in beide Richtungen (Tier-Rückgänge durch Stornierungen), Schlaf-/Liegeplätze steigen nur.

### PRIVATE Semantik

`price` bei n=1 = Gesamtpreis fürs Abteil. `next_tier_price` bei `tier_jump_at=2` = Marginalkosten für 2. Person (~319-647 SEK). Nicht der nächste Preistier, sondern der Zuschlag für einen zusätzlichen Mitreisenden.
