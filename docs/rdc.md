# RDC EuroNight (EN 344/345)

GraphQL-API: `tickets.rdc-deutschland.de/booking` (keine Auth).

## Scraper

`scrapers/rdc_availability.py`

- Holt alle buchbaren Connections pro Route (ReadTrainConnections)
- EntityTypes einmal pro Route (ReadEntityTypes, gecacht)
- Baseline-Preise als Batch: alle Entities in einem Request pro Booking-Modus (n=1)
- Tier-Scanning: probt n=1..cap pro Entity um Preisgrenzen zu finden
  - Erst n=cap prüfen (1 Request) — wenn kein Jump → fertig
  - Bei Jump: n=2..cap-1 einzeln scannen bis Grenze gefunden
- 2 Routen parallel (ThreadPoolExecutor)

Usage: `python3 rdc_availability.py DEP_ID ARR_ID -q -o data/rdc`

Station IDs: 5=Hamburg, 57=Stockholm, 68=Berlin Lichtenberg, 67=Berlin Gesundbrunnen.
Routes configured in `bin/run-all.sh` (2 calls: hamburg-stockholm + stockholm-hamburg).

Laufzeit: ~10-15 min (73 Connections × 2 Routen, ~600-800 Requests). Output: `data/rdc/YYYYMMDD_route.json`

## Routen

| Route | Dep | Arr | Verkehrstage |
|-------|-----|-----|--------------|
| hamburg-stockholm | 5 (Hamburg) | 57 (Stockholm) | Mo + Mi + Fr |
| stockholm-hamburg | 57 | 5 | Di + Do + Sa |

## Datenformat (ab 26.08.2026)

```json
{
  "2026-09-04": {
    "hash_id": "Z5ELrvXvnJ",
    "date": "2026-09-04",
    "entities": [
      {"id": "Z5RRRzb1J4", "title": "Sitz", "single": [...]},
      {"id": "BKVpAEyGbm", "title": "Liege", "single": [...], "single_tiers": [...], "cabin": [...], "cabin_tiers": [...]},
      {"id": "mkkJKnMnWm", "title": "Bett", "single": [...], "single_tiers": [...], "cabin": [...], "cabin_tiers": [...]},
      {"id": "mdoeXD6Lj4", "title": "Bett 1. Klasse", "cabin": [...], "cabin_tiers": [...]}
    ]
  }
}
```

- `single`: Einzelplatz-Preise (geteiltes Abteil) bei n=1
- `cabin`: Privatabteil-Preise bei n=1
- `single_tiers` / `cabin_tiers`: Tier-Sprünge (nur vorhanden wenn Jump erkannt)
- Leeres Array = ausverkauft
- Sitz hat nur Single (Großraumwagen, kein Abteil)
- Bett 1.Kl hat nur Cabin (nur als ganzes Abteil buchbar)

### Tier-Format

```json
"single_tiers": [{"tier_jump_at": 3, "next_tier_price": 80}]
```

Bedeutung: Bei n=3 springt der Normalpreis auf 80€ → 2 Plätze verbleiben im aktuellen Tier (`tier_jump_at - 1`).
Kein `single_tiers`-Feld = mindestens `cap` Plätze im aktuellen Tier verfügbar.
`next_tier_price` = `null` bei gesetztem `tier_jump_at` bedeutet ausverkauft ab diesem n.

### Per-Booking Caps

| Entity | Single | Cabin |
|--------|--------|-------|
| Sitz | 5 | — |
| Liege | 6 | 6 |
| Bett | 2 | 2 |
| Bett 1.Kl | — | 3 |

Diese Caps sind ein **hartes API-Limit pro Buchungsanfrage**, kein Verfügbarkeits-
Signal. Verifiziert am 2026-09-07 mit `ReadPriceCategories` für Liege Single:
`AmountAdults` 1–6 liefert Preise, ab **n=7 kommt konstant `PriceCategories: []`**
— auch an einem nachfrageschwachen Termin (2026-11-02) mit reichlich freien Plätzen
(alle Fares auf Basistier). Das leere Ergebnis ab n=7 bedeutet also „über Cap
angefragt", nicht „ausverkauft".

### Absolute Tier-Kapazitäten nicht messbar

Folge des Caps: Die **absolute Größe eines Tier-Kontingents ist aus der API nicht
ableitbar**, sobald das Tier mehr als `cap` Plätze umfasst (Liege bis 60/Wagen).
Das Tier-Probing sieht nie über `cap` hinaus — ein `tier_jump_at` wird nur sichtbar,
wenn die Restzahl im aktuellen Tier unter `cap` fällt (Liege ≤5, Sitz ≤4, Bett ≤1,
Bett 1.Kl ≤2). Erhöhen des Probing-Fensters ist versperrt (API antwortet ab n>cap
mit leerem Ergebnis).

Was mit Konfidenz bleibt:
- **Tier-Preisleitern** (diskrete Normalpreis-Stufen) — voll belastbar.
- **Ordinale Ausverkaufsreihenfolge** — Spar/Interrail vor Normal, Bett 1.Kl zuerst knapp.
- **Untere Schranken** der Restkapazität nur im Tier-Endspurt (≤cap Plätze), d.h. für
  einzelne stark gebuchte Termine — nicht für das Gesamtkontingent.

Für absolute Restkapazitäten müsste RDC ein `free`/`capacity`-Feld liefern (wie Leo);
tut es nicht. Kapazität ist zusätzlich durch „fährt nach Bedarf"-Wagen physisch
variabel (siehe Wagenreihung), was selbst die Obergrenze pro Termin verschiebt.

## Preiskategorien

| ID | Name | Stornierbar |
|----|------|-------------|
| 35 | Normalpreis | Ja (gestaffelt) |
| 34 | Sparpreis | Nein |
| 36 | Interrail | Nein |

## Preistiers (Normalpreis, empirisch bestätigt 26.-31.08.2026)

| Entity | T1 | T2 | T3 | T4 | T5 | T6 |
|--------|-----|-----|-----|-----|-----|-----|
| Sitz Single | 40€ | 54€ | 60€ | 72€ | 80€ | 90€ |
| Liege Single | 80€ | 120€ | 150€ | 170€ | 200€ | — |
| Liege Cabin | 240€ | 360€ | 430€ | 470€ | 500€ | — |
| Bett Single | 200€ | 250€ | 300€ | 330€ | — | — |
| Bett Cabin | 300€ | 375€ | 450€ | 495€ | — | — |
| Bett 1.Kl Cabin | 420€ | 495€ | 525€ | 600€ | — | — |

Multipliers: Sparpreis = 0.85× Normal, Interrail = 0.80× Normal.

Sitz hat 6 Tiers (vorher nur 2 bekannt). Bett Single/Cabin haben je einen neuen Tier 4 (330€/495€).
Spar-Kontingent ist separat und kleiner als Normal — Spar/Interrail werden zuerst SOLD OUT.

**Liege T1 (80€ Single / 240€ Cabin) — noch dünn belegt.** Diese untersten Liege-
Stufen traten bisher nur an wenigen Nachfrage-Tiefpunkten auf: durchgängig am
ersten RDC-Betriebstag (Stockholm→Hamburg 01.09., stabil über 7 Snapshots, ≥6
Plätze im Tier — kein Restplatz-Effekt), plus vereinzelt Hamburg→Stockholm 09.09.
und 16.09. (je ein Mittwoch, 100€). Zu wenige Beobachtungen für eine starke
Aussage: 80€/240€ könnte ein echtes Basistier für sehr schwache Termine sein oder
sich als reguläres T1 etablieren, sobald mehr schwach nachgefragte Termine in den
Verkauf kommen (z.B. nach dem Fahrplanwechsel 12.12.2026 bzw. mit deren
Verkaufsstart). Bis dahin gilt praktisch **T2 (120€/360€) als Regeleinstieg**.

## Beobachtungen (26.-31.08.2026, 6 Tage Daten)

123 Preisänderungen in 6 Tagen. Hauptmuster:

- **Tier-Aufstieg**: Sitz 40→90€, Liege 120→200€, Bett 200→300€ für nahe Termine (Sep)
- **Tier-Rückgang** (Stornierungen): Bett 300→250→300€, Sitz 80→40€ — Preise bewegen sich in beide Richtungen
- **Spar verschwindet vor Normal**: Spar- und Interrail-Kontingent werden zuerst SOLD OUT, Normal bleibt
- **Bett 1.Kl ausverkauft**: 16.10. komplett SOLD OUT (alle Kategorien), 07.09. kurzzeitig SOLD OUT dann zurück
- **Nov-Dec**: Alles auf T1 (Basispreise) — noch keine Nachfrage

## Tier-Analyse

`tools/rdc_tiers.py` — leitet die kanonischen Normalpreis-Tiers datengetrieben aus den Snapshots ab (Preise, die an ≥25% der Snapshot-Tage auftreten, gelten als Tier; Abweichungen <5% als Rundungsrauschen). Getrennt nach Entity (Sitz/Liege/Bett/Bett 1.Kl) und Modus (Single/Cabin).

Ausgabe pro Entity/Modus:
- Kanonische Tier-Leiter mit Übergängen (T1→T2 +%, Gesamtspreizung)
- Fare-Multiplier empirisch aus den Daten (Spar/Interrail vs. Normal)
- **Live tier position**: welche zukünftigen Reisedaten kurz vor einem Preissprung stehen (aus `tier_jump_at`/`next_tier_price`), inkl. verbleibender Plätze im aktuellen Tier

```bash
python3 tools/rdc_tiers.py                    # beide Routen
python3 tools/rdc_tiers.py hamburg-stockholm  # eine Route
python3 tools/rdc_tiers.py --entity Liege     # nach Entity filtern
```

Anders als der generische `analyze.py --mode alert` (statistische Median-Abweichung, tier- und währungsagnostisch) bildet dies das diskrete Tier-System korrekt ab. Tiers, die im aktuellen Datenfenster nicht auftreten, fehlen in der Ausgabe (datengetrieben) und füllen sich mit mehr Snapshots.

## Wagenreihung (Vagonweb, 02.09.–12.12.2026)

Zuglänge 309 m. Lok: Vectron 193 (RPOOL).

| Wagen | Bauart | Kategorie | Plätze |
|-------|--------|-----------|--------|
| 21-23 | Bvcmz 248.5 | Liegewagen (6er-Abteil) | 60/Wg |
| 24 | Bvcmbz 249.1 | Liegewagen + barrierefrei | 32-48 |
| 25-28 | WLABmz AB32 | Schlafwagen | Pl. 13-26 (2.Kl) + Pl. 71-76 (1.Kl Deluxe) |
| 31-33 | Bimz 264 | Sitzwagen (2. Klasse) | 60/Wg |

Wagen 21-22, 28, 32-33: "fährt nach Bedarf" (flexible Kapazität).

### Reale Zugbildungen (Vagonweb, einzelne Daten)

Vagonweb dokumentiert für einzelne Termine die **tatsächlich gefahrene** Wagenreihung
(nicht nur den Regelplan). Bisher zwei Beobachtungen — sie zeigen, dass die Bildung
pro Umlauf variiert (v.a. Anzahl Schlafwagen):

**EN 345 (Stockholm→Hamburg), Di 1.9. / Mi 2.9.2026:**
- Liege 2.Kl: Wg 22+23 (je 60) + Wg 24 (32–48) = **152–168**
- Schlafwagen: **2** (Wg 25+26), je 2.Kl 13–26 + 1.Kl 2–6 → 2.Kl **26–52**, 1.Kl **4–12**
- Sitz: Wg 31 = 25 (Abteil) + 35 (Großraum) = **60**

**EN 344 (Hamburg→Stockholm), Mi 2.9. / Do 3.9.2026:**
- Liege 2.Kl: Wg 22+23 (je 60) + Wg 24 (32–48) = **152–168** (ein Liegewagen als
  „verschlossen" vermerkt → ggf. real weniger nutzbar)
- Schlafwagen: **3** (Wg 25+26+27) → 2.Kl **39–78**, 1.Kl **6–18**
- Sitz: Wg 31 = 60

Diese Zahlen sind **physische Obergrenzen** für den jeweiligen Termin. Sie erlauben
Plausibilitätschecks der beobachteten Tiers, aber **keine** Ableitung der online
verkauften Kontingente (siehe „Absolute Tier-Kapazitäten nicht messbar").

**Offen: Anteil des online verkauften Kontingents.** Wie groß der online buchbare
Anteil relativ zur physischen Kapazität ist, ist unbekannt. Die per-Booking-Caps
(Sitz 5, Liege 6, …) sind ein Anfrage-Limit und sagen nichts über die Kontingent-
größe aus. Es gibt bislang keinen Beleg dafür, wie viel RDC online vs. über andere
Kanäle verkauft — diese Frage bleibt offen.
