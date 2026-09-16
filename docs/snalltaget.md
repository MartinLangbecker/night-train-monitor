# Snälltåget Scraper

## API

Base: `https://apiv2.snalltaget.se`
Token: `GET https://www.snalltaget.se/token/v2` (900s TTL, refresh → 1800s)

Endpoints: `/orientation/calendar`, `/orientation/searchjourney`, `/orientation/searchservices`,
`/interrail/validate`, `/booking`, `/auth/refreshtoken`

## Scraper

- File: `scrapers/snalltaget_availability.py`
- CLI: `python3 snalltaget_availability.py ORIGIN DEST --days 120 -q -o DIR`
- Each call is bidirectional (oppositedate optimization) → 2 output files
- Routes configured in `bin/run-all.sh` (4 calls: Berlin/Hamburg/Dresden→Stockholm, Berlin→Malmö)
- Filters to direct trains only (1 leg)
- Runtime: ~4-7 min for 120 days

## Data Format

`YYYYMMDD_route.json` — dict with date keys:

```json
{
  "2026-09-15": {
    "calendar": {"amount": 499.0, "quota": 17, "capacity": 34},
    "service": {"serviceName": "10300", "serviceType": "STNIGHT", "departure": "...", "arrival": "..."},
    "bundles": [
      {"productFamilyId": "SPSF", "price": 499.0, "originalPrice": 499.0}
    ]
  }
}
```

## Train Numbers

| Train | Type | Route |
|-------|------|-------|
| D 10300 | STNIGHT | Berlin/Hamburg → Stockholm (direct) |
| D 300 | STNIGHT | Berlin/Hamburg → Malmö (night section) |
| 3940 | STTRAIN | Malmö → Stockholm (day train) |

D 300 and D 10300 = same physical train, split at Malmö in the system.

## Shared Berth Finding (Aug 2026)

Shared berths (NTB*) are only offered on transfer connections (D 300 + 3940),
never on D 10300 direct searches. This is despite:
- The same physical Bvcmz 248 wagons running in both
- The comfort-levels page still advertising "Berth in shared compartment"
- The API knowing all NTB* product family codes

Likely a revenue optimization strategy:
- Shared Berth (per person): 1.048–1.998 SEK (was historically 399–499 SEK)
- Private Compartment (whole 6-berth): 1.999–8.499 SEK
- Solo travelers wanting a berth are pushed to buy entire compartment

The scraper currently stores only direct (1 leg) results. To capture NTB prices,
it would need to also store transfer routes — but these are for the same physical train.

## Wagenmaterial

D 300/10300 (Vagonweb May/Jun 2026):
- 4x Bvcmz 248 (Liegewagen, 40-60 Plätze each)
- 2x Bmpz (Sitzwagen, 74 Plätze each)
- Wg 214/215: only Berlin→Malmö
- Wg 217/218: through to Stockholm (via 3940)

## Product Families

Direct (D 10300): SPSF, SPFF, NTPCSF, NTPCFF
Transfer (D 300+3940): SPSF, SPFF, NTBSF, NTBFF, NTPCSF, NTPCFF, SPPCFF, SPPCSF

### Flexibility Suffixes

| Suffix | Name | Conditions |
|--------|------|------------|
| NF | Non-Flexible | Nicht umbuchbar, nicht erstattbar |
| SF | Semi-Flexible | Umbuchbar bis 24h vor Abfahrt |
| FF | Full-Flexible | Erstattbar bis Abfahrt (7 Tage bei NTPC) |

### NF Tariffs (Last-Minute, Day-of-Departure Only)

On the day of departure, SF/FF products are replaced by NF equivalents. NF tariffs are the only bookable option on Day 0 — SF and FF vanish completely. On Day+1 and beyond, only SF/FF are offered. There is no overlap.

Verified live 28.08.2026 (Berlin→Stockholm):

| Day offset | Direct | Transfer |
|------------|--------|----------|
| 0 (today) | NTBNF=999, NTPCNF=3999 | SPNF=1248, NTBNF=1598, NTPCNF=4598 |
| 1 | no service | no service |
| 2 | SPSF, SPFF, NTPCSF, NTPCFF | NTBSF, NTBFF, SPSF, SPFF, NTPCSF, NTPCFF |
| 3+ | SF/FF only | SF/FF only |

NF pricing sits in the mid-range — neither the cheapest nor the most expensive tier. Snälltåget's website shows "Ticket kann nicht umgebucht oder erstattet werden" for NF bundles.

The API spec documents all NF codes (SPNF, NTBNF, NTPCNF, FCSNF, NTPCCNF) and maps them to ComfortZone `NRR` (Not Rebookable or Refundable). The scraper's midnight cron never captures NF because it runs at 00:00 — the earliest departure is ~17:00 the same day, so Day 0 has already flipped to NF by then. NF tariffs in snapshot data are therefore an artifact of the scrape timing.

### Transfer Product Assignment (Compartment Anomaly)

Transfer connections (D 300 + 3940) assign compartment products to **one leg only**,
depending on the boarding station. The product applies to the leg with matching accommodation,
the other leg gets a regular seat:

| Origin | Product | Compartment assigned to | Other leg |
|--------|---------|------------------------|-----------|
| Berlin | NTPCSF/NTPCFF | D 300 (Wg 214, Liegewagen) | 3940: regular seat (Wg 11) |
| Hamburg | SPPCSF/SPPCFF | 3940 (Wg 9, Sitzabteil) | D 300: regular seat (Wg 213) |

Evidence (booking 13.09.2026):
- Berlin NTPCSF 5.298 SEK → Wagen 214, Abteil 2 (Liegewagen on D 300) + Wagen 11, Sitzplatz 21 (3940)
- Hamburg SPPCSF 3.795 SEK → Wagen 213, Sitzplatz 34 (D 300) + Wagen 9, Abteil 5 (3940)

This means:
- You cannot book a Liegewagen compartment on D 300 AND a seat compartment on 3940
- The system does not allow per-leg comfort selection for transfers (unlike outbound/inbound)
- Product codes encode which leg gets the compartment: NTPC = night leg, SPPC = day leg
- Berlin passengers cannot access SPPC products; Hamburg passengers cannot access NTPC on transfers
- Pricing differs significantly: Berlin transfer cheapest seat 1.298 SEK vs Hamburg 798 SEK (same arrival time)

**Customer impact:** The product name "Privates Abteil" (Private Compartment) suggests
a compartment for the entire journey. In reality, one leg is a regular seat assignment.
A Berlin customer paying 5.298 SEK for "Privates Abteil" sits in a Liegewagen compartment
until Malmö, then 5h on a regular seat to Stockholm. This is not communicated during booking —
only the confirmation with wagon numbers reveals the split.

## Meråkerbanen Trondheim Extension (Test Train)

Commercial test run 5–6 September 2026. Four wagons of the seasonal Malmö–Storlien night train
extended to Trondheim and back via the electrified Meråkerbanen. First direct passenger service
Sweden–Trondheim since the Nabotåget (Östersund–Trondheim) ended in 2007.

Snälltåget aims for regular service Malmö–Stockholm–Åre–Storlien–Trondheim from summer 2027.

### Background

- Meråkerbanen electrification completed 2025
- Jernbanedirektoratet (NO) rejected application from Snälltåget/Norrtåg for regular service
  (November 2025), citing competition with two Norwegian local trains
- Potential legal dispute unresolved
- Freight traffic on Meråkerbanen has ceased entirely

### Test Train Schedule

**Zug 24 — Malmö → Trondheim (5 September 2026)**

| Station | Arr | Dep |
|---------|-----|-----|
| Malmö C | — | 15:35 |
| Lund | — | 16:00 |
| Hässleholm | — | 17:35 |
| Alvesta | — | 18:25 |
| Nässjö | — | 19:10 |
| Linköping | — | 20:15 |
| Norrköping | — | 20:45 |
| Stockholm C | — | 22:55 |
| Uppsala | — | 23:30 |
| Östersund | — | 06:00 |
| Undersåker | — | 07:00 |
| Åre | — | 07:20 |
| Duved | — | 07:30 |
| Enafors | — | 07:55 |
| Storlien | 08:10 | 08:20 |
| Hell | — | 09:54 |
| Trondheim S | 10:30 | — |

**Zug 25 — Trondheim → Malmö (6 September 2026)**

| Station | Arr | Dep |
|---------|-----|-----|
| Trondheim S | — | 12:54 |
| Hell | — | 13:28 |
| Storlien | 14:59 | — |
| Enafors | — | 15:35 |
| Duved | — | 16:10 |
| Åre | — | 16:27 |
| Undersåker | — | 16:55 |
| Östersund | — | 18:00 |
| Uppsala | — | 22:55 |
| Stockholm C | — | 23:35 |
| Norrköping | — | 02:15 |
| Linköping | — | 02:50 |
| Nässjö | — | 04:45 |
| Alvesta | — | 05:40 |
| Hässleholm | — | 06:45 |
| Lund | — | 07:25 |
| Malmö C | 07:40 | — |

### API & Booking

Trondheim S is bookable via the standard Snälltåget API under UIC code `760001126`.
The booking flow works with the same endpoints as regular routes:

- Calendar: `direction=outbound`, `origin="Malmö C"`, `destination="760001126"`
- SearchJourney: `origin="Malmö C"`, `destination="760001126"`, `departure="2026-09-05"`
- Inbound: `origin="760001126"`, `destination="Malmö C"`, `departure="2026-09-06"`

**Pricing (snapshot 26.08.2026):**

| Direction | Product | Price (SEK) | Note |
|-----------|---------|-------------|------|
| Malmö→Trondheim (Zug 24) | NTBSF (Shared Berth) | 749 | Cheapest |
| | NTBFF (Shared Berth refundable) | 848 | |
| | NTPCSF (Private Compartment) | 1.499 | 50% off (orig 2.999) |
| | NTPCFF (Private Compartment refundable) | 3.499 | |
| Trondheim→Malmö (Zug 25) | SPSF (Seat) | 699 | Cheapest |
| | SPFF (Seat refundable) | 798 | |
| | NTBSF (Shared Berth) | 999 | |
| | NTBFF (Shared Berth refundable) | 1.098 | |
| | NTPCSF (Private Compartment) | 3.999 | |
| | NTPCFF (Private Compartment refundable) | 4.499 | |

**Key observations:**
- Zug 24 (outbound): **No seat product** — only berth/compartment. 4 bundles total.
- Zug 25 (inbound): Full product range including seats. 6 bundles.
- Calendar capacity: outbound cap=10 (!), inbound cap=59
- Private Compartment on Zug 24 has 50% launch discount (1.499 vs. 2.999 original)
- Tablebooking (Krogen dinner) available with 21 time slots outbound, 7 inbound

**Scraper:** removed after the test run ended (6 Sep 2026). The 24 snapshots remain under `data/snalltaget/*_{malmoe-trondheim,trondheim-malmoe}.json` and stay queryable via `tools/snalltaget_compare.py` / `tools/compare.py`.

### Notes

- Hell station: connection to Nordlandsbanen, near Trondheim-Værnes airport
- Rolling stock: Sitzwagen, Buffetwagen, Liegewagen (4 wagons extended beyond Storlien)
- Border crossing at Storlien (SE/NO)
- Swedish Mittbanan (Stockholm–Storlien) already electrified; Meråkerbanen (Storlien–Trondheim) since 2025
- Source: Snälltåget via Jürg Streuli / Järnvägar, 26.08.2026



## Nordlicht Sonderzug (Malmö ↔ Narvik)

Einmaliger Nachtzug nördlich des Polarkreises, November 2026. 2.156 km Malmö–Narvik.

### Fahrplan

**Zug 20 — Malmö → Narvik (23. November 2026)**

| Station | Zeit |
|---------|------|
| Malmö C | 13:15 |
| Lund C | 13:30 |
| Hässleholm C | 14:05 |
| Alvesta | 14:50 |
| Nässjö C | 15:30 |
| Linköping C | 16:35 |
| Norrköping C | 17:01 |
| Stockholm C | 18:55 |
| Uppsala C | 19:30 |
| Gävle | 20:45 |
| Ånge | 23:59 |
| Boden | 08:45+1 |
| Polarkreis | 09:58+1 |
| Gällivare | 11:30+1 |
| Kiruna | 13:00+1 |
| Abisko | 14:45+1 |
| Björkliden | 15:00+1 |
| Riksgränsen | 15:40+1 |
| Narvik | 16:34+1 |

**Zug 21 — Narvik → Malmö (27. November 2026)**

| Station | Zeit |
|---------|------|
| Narvik | 12:40 |
| Riksgränsen | 14:00 |
| Björkliden | 14:35 |
| Abisko | 14:45 |
| Kiruna | 16:40 |
| Gällivare | 17:55 |
| Polarkreis | 18:45 |
| Boden | 20:20 |
| Ånge | 04:35+1 |
| Gävle | 07:05+1 |
| Uppsala C | 08:00+1 |
| Stockholm C | 08:35+1 |
| Norrköping C | 10:11+1 |
| Linköping C | 10:40+1 |
| Nässjö C | 11:45+1 |
| Alvesta | 12:25+1 |
| Hässleholm C | 13:30+1 |
| Lund C | 14:25+1 |
| Malmö C | 14:45+1 |

### API & Booking

Narvik: UIC `760002402`. Buchbar über die Standard-API.

20% Rabatt auf Private Compartment (Semi-Flex) bei Hin+Rück-Buchung. Der Rabatt greift über den `oppositedate`-Parameter im SearchJourney.

### Pricing (Snapshot 31.08.2026)

**Outbound (Zug 20, Malmö→Narvik):**

| Product | Single | Return | Rabatt |
|---------|--------|--------|--------|
| NTBSF (Liege semi) | 2.124 | 2.124 | — |
| NTBFF (Liege full) | 2.223 | 2.223 | — |
| NTPCSF (Comp semi) | 8.499 | 6.799 | -20% |
| NTPCFF (Comp full) | 8.999 | 8.999 | — |

**Inbound (Zug 21, Narvik→Malmö):**

| Product | Single | Return | Rabatt |
|---------|--------|--------|--------|
| NTPCSF (Comp semi) | 8.499 | 6.799 | -20% |
| NTPCFF (Comp full) | 8.999 | 8.999 | — |

Kein Liegeplatz auf der Rückfahrt, nur Private Compartment. Outbound cap=1 (fast ausverkauft am 31.08., Preise von ~800 auf 2.124 SEK innerhalb von 4 Stunden gestiegen).

Private Compartment = Flatrate pro Abteil (8.499/8.999 SEK), egal ob 1-6 Personen. Ab 4 Personen günstiger als Liegeplatz pro Kopf.

### Scraper

`scrapers/snalltaget_nordlicht.py` — separater Cron-Job (`bin/run-nordlicht.sh`, 00:20).

Erfasst sowohl Return-Preise (mit oppositedate, 20%-Rabatt) als auch Single-Preise (ohne oppositedate). Output:
- `direct`: Return-Trip-Preise (mit Rabatt)
- `direct_single`: Einzelfahrt-Preise (voller Preis)

Auto-Stop nach 27.11.2026.

## Dresden Extension

The Stockholm→Hamburg→Berlin route extends to Dresden on Fridays (southbound D 10301) and Sundays (northbound D 10300). Service is weekly, 14 dates per direction through November 2026.

Station code: `Dresden` (name-based, same as Berlin/Hamburg).

### Dual-Use: Inlandsstrecke als letzter Zug des Tages

D 300 bedient Berlin Hbf → Hamburg Hbf in 2:34h (Abfahrt ~21:11, Ankunft ~23:45). Der Sitzwagen ist auf dieser Strecke als Inlandsverbindung buchbar — 149 SEK Festpreis (112 SEK p.P. mit Together-Rabatt ≈ 10€). Bei cap=72 und quota=37 (Nov 2026) praktisch unbegrenzt verfügbar. Dual-Use: abends nutzen Inlandsreisende den Sitzwagen Berlin→Hamburg als letzten Zug des Tages, während Skandinavien-Reisende im selben Zug ab Hamburg über Nacht im Liegewagen weiterfahren.

**Offene Frage: Berth auf Inlandsstrecke.** Die API erlaubt Buchung von Shared Berth (NTBSF) für Berlin→Hamburg (2:34h). Die Liegewagen starten in Sitzkonfiguration (Reisende stellen selbst um). Bettwäsche liegt unverpackt im Abteil. Unklar: Wird der Liegeplatz ab Hamburg erneut verkauft? Wenn der Berlin-Reisende die Bettwäsche benutzt, ist das Abteil für den Nachtabschnitt "verbraucht" — kein Wechsel im fahrenden Zug. Möglicherweise wird das Berlin-Berth-Kontingent separat vom Hamburg-Kontingent gehalten (konsistent mit per-Origin-Kontingentmanagement), sodass der Platz gar nicht doppelt verkauft wird. Noch auffälliger: Auch Private Compartment (NTPCSF) ist Berlin→Hamburg buchbar — 6 Liegen für 2:34h Fahrt, bei denen das gesamte Abteil für den Nachtabschnitt blockiert wäre.

Added to daily scraper on 27.08.2026. Output files: `YYYYMMDD_dresden-stockholm.json`, `YYYYMMDD_stockholm-dresden.json`.

## Calendar Fields: capacity vs quota

The calendar API returns three fields per date: `amount`, `capacity`, `quota`.

Analysis of 1,772 data points across all routes (27.08.2026):

| Field | Meaning | Range |
|-------|---------|-------|
| `amount` | Calendar display price ('from X SEK') — the cheapest tier currently bookable | 149–5498 SEK |
| `capacity` | Remaining seats across all products for this origin | 1–292 |
| `quota` | Remaining seats at the `amount` price — across all services (STNIGHT + STTRAIN) on that date | 1–199 |

Key findings:
- `capacity > quota` in 90% of cases — capacity covers all tiers, quota only the cheapest
- `capacity` is **per origin**, not per physical train. Same train, same date: Hamburg cap=143, Berlin cap=33
- `quota → 0` triggers a price tier jump. Average quota at price increase: 4.8
- `capacity` can jump upward (e.g., 13→66) when Snälltåget releases additional contingent
- On dates with both day train (D 306/307 STTRAIN) and night train (D 10300/10301 STNIGHT), `capacity` and `quota` aggregate across both services. The day train currently operates Hamburg↔Stockholm only, so this contamination only affects Hamburg routes. Berlin and Dresden calendar data refers purely to the night train

## Zug 25 (Stockholm–Malmö Nachtzug)

Zug 25 is the seasonal overnight train Stockholm→Malmö (separate from D 300/10300). It appears in transfer connections (Zug 25 + D 307) for Stockholm→Hamburg bookings. Verified via booking API on 30.08.2026.

### Wagon Structure

| Wagen | Typ | Products | inventoryClass |
|-------|-----|----------|---------------|
| 109 | Liegewagen | Shared Berth, Private Compartment | NT |
| 115 | Mischtyp | 2.Kl Sitz, 1.Kl Sitz, 1.Kl Privatabteil | SP, FC, FD |
| 119 | Liegewagen | Private Compartment (Flex only) | NT |

Wg 115 combines open seating (2nd + 1st class) and 1st class private compartments in one wagon. Seat numbering: 1st class compartments at low numbers (Platz 3/9, Abteile 1-2), 1st class seats in the middle (Platz 17-20), 2nd class seats at high numbers (Platz 50-52).

Wg 115 is an **AB3K** (Nr. 4870 or 4872) — a 1960s Swedish 1st/2nd class compartment coach. 20 seats 1st class (two compartments + small salon with 2 freestanding armchairs) + 32 seats 2nd class (two-part salon). 24.1m, 160 km/h, WiFi + power outlets (retrofitted). Only 2 remain in Snälltåget service. Source: [järnväg.net/vagnguide/ab3](https://www.jarnvag.net/vagnguide/ab3)

Full Snälltåget rolling stock overview: [järnväg.net/snalltaget](https://www.jarnvag.net/snalltaget)

### Product Pricing (30.08.2026, Zug 25 leg only)

| Product | Tariff | Wg | Rebookable | Refundable |
|---------|--------|-----|-----------|------------|
| 2.Kl Sitz | SPRB/SPRF | 115 | 599 | 698 |
| Berth Shared | NMR_NTBRB/RF | 109 | 749 | 848 |
| 1.Kl Sitz | FCRB/FCRF | 115 | 749 | 848 |
| Privatabteil | NMR_NTPCRB/RF_1 | 109/119 | 1,499 | 1,749 |
| 1.Kl Privatabteil | FCPCRB/RF_1 | 115 | 3,296 | 4,346 |

1st class seat and shared berth cost the same (749 SEK rebookable). Choice depends on preference: reclining seat in 1st class or berth in shared compartment.

### Per-Segment Tariff Assignment

Transfer bookings require different tariff codes per segment. The searchjourney bundles contain combined tariffs, but booking must split them:

- Zug 25 (STNIGHT): night train tariff (NMR_NTBRB, FCRB, etc.)
- D 307 (STTRAIN): day train tariff (SPRB, SPRF)

Using the same tariff on both segments fails with "Tariff conditions broken".

## Per-Origin Contingent Management

Snälltåget allocates capacity separately per boarding station. The same physical train on the same date shows different cap/quota/prices depending on the query origin:

| Date | Dresden cap | Berlin cap | Hamburg cap |
|------|------------|------------|-------------|
| 01.09. (northbound) | — | 33 | 143 |
| 04.09. (southbound) | 12 | 12 | 85 |
| 22.09. (northbound) | — | 55 | 168 |

Hamburg receives 3–5× more contingent than Berlin. Dresden shares Berlin's contingent on overlapping dates.

Consequence: Hamburg sells through tiers faster (higher demand), reaching premium pricing, while Berlin/Dresden remain in low tiers due to low awareness. This creates overshoot opportunities.

## Overshoot Pricing (Hidden City Ticketing)

The same physical compartment on the same train costs significantly different amounts depending on the booked segment:

| Date | Product | Stockholm→Hamburg | Stockholm→Berlin | Stockholm→Dresden | Save |
|------|---------|------------------|-----------------|-------------------|------|
| 11.09. | Compartment | 5,999 | 5,999 | **4,999** | 1,000 SEK |
| 30.10. | Compartment | 5,999 | **3,999** | 5,999 | 2,000 SEK |
| 27.11. | Comp-Flex | 6,499 | 5,499 | **4,499** | 2,000 SEK |
| 04.09. | Compartment (NB) | 7,999 | **3,999** | — | 4,000 SEK |

Southbound: Book to a further station (Berlin/Dresden instead of Hamburg), exit at your actual stop.
Northbound: Book from an earlier station (Berlin instead of Hamburg). The compartment is reserved and stays empty until boarding.

Savings are concentrated in Compartment products (1,000–4,000 SEK / 90–360€). Seat price differences are marginal (49–200 SEK).

Tool: `python3 tools/snalltaget_compare.py overshoot`

## Berth-Seat Price Inversion

On transfer routes (D 300+3940 / 3943+301), shared berths (NTBSF) can be cheaper than seats (SPSF):

| Date | Route | T:Seat | T:Berth | Saving |
|------|-------|--------|---------|--------|
| 30.08. | berlin-stockholm | 1,498 | 1,248 | 250 SEK |
| 30.08. | dresden-stockholm | 1,498 | 1,248 | 250 SEK |

The inversion occurs because seat and berth have separate yield tiers. When seats are in higher demand (e.g., for the daytime Malmö→Stockholm leg), the seat tier rises above the berth tier.

Tool: `python3 tools/snalltaget_compare.py inversion`

## Tier Structure

Observed price levels per product (from snapshot-to-snapshot jumps):

| Product | Observed tiers (SEK) | Jump trigger |
|---------|---------------------|---------------|
| Seat (SPSF) | 499, 699, 799, 848, 999, 1,248 | quota ≈ 5 |
| Compartment (NTPCSF) | 1,999, 2,998, 3,998, 3,999, 4,999, 5,999, 7,999 | quota ≈ 5 |
| T:Berth (NTBSF) | 1,048–1,998 (11 levels) | fine-grained |
| T:Berth-Flex (NTBFF) | 1,246–2,446 (17 levels) | very fine-grained |

Transfer products have much finer tier granularity than direct products — likely because transfer pricing combines two legs.

Tool: `python3 tools/snalltaget_compare.py tiers [ROUTE]`

## "Together" Discount (Mengenrabatt)

Snälltåget applies an automatic 25% discount on Seat tickets (SPSF, SPFF) when ≥2 passengers are booked together. Officially documented on snalltaget.se/en/together and /en/comfort-levels.

| Passengers | SPSF per pax | Discount |
|-----------|-------------|----------|
| 1 | 499 SEK | — |
| 2+ | 374 SEK | -25% |

- Applies to: Seats only (SP products). Not Compartments (NTPC), not Berths (NTB).
- Cancellation risk: If one traveler in a Together booking cancels, the remaining ticket is recalculated at full price.
- Our scraper queries with 1 passenger → always sees the full price. The Together discount is invisible in snapshot data.

Verified via API: `searchjourney` with `passengers: [{"type":"AD"},{"type":"AD"}]` returns `originalPrice=998` (2×499) and `price=748` (2×374). The booking endpoint confirms 374 SEK per seat.

Together discount scales linearly — all passengers pay the reduced rate, not just the additional ones:

| Pax | SPSF total | Per Pax |
|-----|-----------|---------|
| 1 | 499 | 499 |
| 2 | 748 | 374 |
| 3 | 1,122 | 374 |
| 4 | 1,496 | 374 |
| 5 | 1,870 | 374 |
| 6 | 2,244 | 374 |

Compartment pricing with multiple passengers:

| Pax | NTPCSF total | Note |
|-----|-------------|------|
| 1 | 1,999 | 50% discount (orig 3,999) |
| 2 | 1,999 | Same price for whole compartment |
| 5 | 3,999 | Full price |

The Private Compartment price appears to be per-compartment (not per-person) at low occupancy, switching to per-person at higher occupancy.

### Compartment Tariff Code Convention

The tariff code suffix encodes the number of passengers sharing the compartment:

| Pax | Tariff | NTPCSF | NTPCFF | Note |
|-----|--------|--------|--------|------|
| 1 | `NMR_NTPCRB_1` | 1,999 | 4,499 | Solo-Incentive: 50% off NTPCSF (orig 3,999) |
| 2 | `NMR_NTPCRB_2` | 1,999 | 2,249 | Same NTPCSF, but NTPCFF drops 50%! |
| 3 | `NMR_NTPCRB_3` | 2,999 | 3,374 | Mid-tier |
| 4 | `NMR_NTPCRB_4` | 3,999 | 4,499 | Full price |
| 5 | `NMR_NTPCRB_5` | 3,999 | 4,499 | Full price |
| 6 | `NMR_NTPCRB_6` | 3,999 | 4,499 | Full price |

(Prices from Berlin→Stockholm, 20.11.2026, Tier 1.)

When booking with `_1`, each passenger gets their own 6-berth compartment. With `_N` (N>1), all N share one compartment. Passenger 1 pays the full compartment price, passengers 2-N pay 0 SEK. All are assigned consecutive berth numbers in the same compartment.

Sweet spot: **2 persons at `_2`** — NTPCFF costs only 2,249 SEK for a whole private 6-berth compartment with full refund. At `_1` the same NTPCFF costs 4,499. Solo travelers booking `_2` with a phantom second passenger save 50% on the refundable compartment. Officially supported per FAQ: "Wenn Sie mit weniger Personen reisen, ist keine Umbuchung erforderlich." (snalltaget.se/de/haufige-fragen)

**Tier-dependent:** The 50% discount at `_2` only applies in the lowest NTPCFF tier (4,499 SEK). At higher tiers (5,499 / 6,499 / 8,499), 1-pax and 2-pax prices are identical. Verified across 16 date/route combinations: all November dates (low demand, Tier 1) show the discount, all September/October dates (higher demand) do not.

## Booking API Behavior (Tier Probing PoC)

Tested on 27.08.2026 with `POST /booking` + `POST /booking/{pnr}/cancel`:

- Bookings without payment create a **provisional** reservation (`isProvisional: true`)
- Real seat assignments: Wagen 216, Platz 45/73/74 (Bmpz Sitzwagen)
- Provisional bookings **expire after 1 hour** (`expiryTimestamp = createTimestamp + 1h`)
- **No impact on calendar capacity/quota or searchjourney prices** — the yield management ignores provisional bookings
- Conclusion: Tier boundaries cannot be probed via booking. Only daily snapshots and natural quota decay reveal tier jumps.

## Compartment Exhaustion Test (27.08.2026)

Provisorische Bookings (ohne Payment) beeinflussen das Yield Management doch — aber erst bei hoher Auslastung. Test: 20 sequentielle 6-Pax-Compartment-Bookings auf Berlin→Stockholm 20.11.2026.

### Abteil-Karte (Berlin-Kontingent)

| # | Wagen | Plätze | Abteil | Booking-Preis | Search NTPCSF |
|---|-------|--------|--------|---------------|---------------|
| 1–5 | 218 | 11-66 | 1,2,3,5,6 | 3.999 | 1.999 |
| 6–8 | 217 | 61-86 | 6,7,8 | 3.999 | 1.999 |
| 9 | 217 | 51-56 | 5 | 3.999 | **2.499** ★ Tier-Sprung |
| 10–12 | 217 | 21-46 | 2,3,4 | 4.999 | 2.499 |
| 13 | 217 | 11-16 | 1 | 4.999 | **—** (verschwindet) |
| 14 | — | — | — | **FAILED** | "No logical or physical availability" |

- **13 Abteile** für Berlin-Kontingent verfügbar (von 20 physischen, 2×10 pro Wagen)
- 7 Abteile anderweitig belegt (Hamburg-Kontingent, Shared Berths, echte Buchungen)
- Wg 218: 5 Abteile (Nr. 1,2,3,5,6 — Abteil 4 fehlt)
- Wg 217: 8 Abteile (Nr. 1-8 — Abteil 9,10 nicht verfügbar)
- **Tier 1→2 Sprung nach 8 Abteilen** (1.999→2.499 SEK in 1-Pax-Suche)
- Calendar cap/quota bleiben unverändert (72/37) — betreffen nur Sitze
- Post-Cancel: Alles zurück auf Anfang (1.999 SEK, alle Produkte verfügbar)

### September vs November Exhaustion

| Date | Compartments available | Price (NTPCSF 6p) | cap | Note |
|------|----------------------|-------------------|-----|------|
| 20.09. | **2** (Wg 217 only) | 5,999 | 22 | Near-term, high demand |
| 20.11. | **13** (Wg 217+218) | 3,999 | 72 | Far-future, low demand |

18 of 20 physical compartments are already sold/blocked on 20.09 — only 2 remain for Berlin contingent.

## Transfer Route Pricing

On transfer routes (D 300+3940 / 3943+301), pricing correlates with segment length — Hamburg is cheapest (shortest), Dresden most expensive (longest). This is the expected pattern. The anomaly on **direct** routes is the opposite: Hamburg is often more expensive despite being shorter, because per-origin yield tiers push Hamburg into higher price bands.

| Date | Product | →Hamburg | →Berlin | →Dresden |
|------|---------|---------|---------|---------|
| 11.09. | SPSF | **998** | 1,098 | 1,248 |
| 25.09. | NTPCSF | 5,498 | **4,498** | 5,498 |
| 25.09. | SPSF | **998** | 1,098 | 1,098 |

Berth prices (NTBSF/NTBFF) are identical across all origins on transfers. Compartment transfer pricing shows occasional Berlin savings (25.09.: 4,498 vs 5,498) — worth monitoring but no systematic overshoot pattern.

## Seat Exhaustion Test (27.08.2026)

Fine-grained test: 1 seat at a time, price check after each. Berlin→Stockholm 20.11.2026, Wg 216 (Bmpz, 74 Plätze laut Wagenplan, 72 verfügbar = 2 real gebucht).

### Exakte Tier-Grenzen

| Plätze belegt | SPSF | SPFF | Event |
|--------------|------|------|-------|
| 0–36 | 499 | 499 | Tier 1 (SPSF = SPFF) |
| **37** | 499 | **598** | SPFF springt zuerst (quota-Grenze!) |
| 37–55 | 499 | 598 | SPSF hält Tier 1 |
| **56** | **549** | **648** | SPSF + SPFF springen gemeinsam |
| 56–71 | 549 | 648 | |
| **72** | — | — | Seats verschwinden aus Suche |
| 73+ | | | "No logical or physical availability" |

### quota = Restplätze im SPFF-Tier

Calendar zeigte `cap=72, quota=37, amount=499`. Der SPFF-Sprung passiert bei exakt Booking #37 — das beweist: **quota = Restplätze zum aktuellen Flex-Preis**. SPSF (Semi-Flex) hat ein eigenes, größeres Kontingent (56 Plätze bei 499 SEK).

NTPCSF/NTPCFF blieben während des gesamten Seat-Exhaustion-Tests unverändert (1.999/4.499) — Compartment-Tiers sind vollständig unabhängig von Sitz-Kontingenten.

### Flex vs. Semi-Flex Spread

| Plätze | SPSF | SPFF | Spread | Hinweis |
|--------|------|------|--------|---------|
| 0–36 | 499 | 499 | 0 | Identisch in Tier 1 |
| 37–55 | 499 | 598 | 99 | Flex steigt, Semi-Flex bleibt |
| 56–71 | 549 | 648 | 99 | Beide höher, Spread konstant |

Für preisbewusste Reisende: Semi-Flex (SPSF) bleibt länger günstig als Full-Flex (SPFF). Der Flex-Aufpreis lohnt sich primär in Tier 1, wo beide gleich kosten.

### Sitzplatzwahl (Seat Picker Workaround)

Snälltågets Online-Buchung bietet keine Sitzplatzauswahl (Stand Aug 2026, laut FAQ "in Kürze verfügbar"). Da die Booking-API echte Platznummern zuweist und Bookings ohne Payment stornierbar sind, kann man gewünschte Plätze gezielt reservieren: alle ungewünschten PNRs stornieren, gewünschten PNR behalten und im Browser bezahlen.