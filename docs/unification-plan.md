# Vereinheitlichung Leo Express + European Sleeper

## Ist-Zustand

### Bereits unified
- `lib/loaders.py` — einheitliches Format `{date: {class: {capacity, price}}}` für beide Provider
- `lib/analysis.py` — provider-agnostische Analyse (fill_curves, sellout, booking_window, etc.)
- `bin/analyze.py` — nutzt unified lib, arbeitet auf beiden Providern
- `tools/compare.py` — provider-agnostisch (diff/trend/anomaly/routes) für alle 5 Provider, baut auf `lib/loaders` + `lib/analysis` (Stand 07.09.2026)
- `tools/sj_tiers.py` — SJ Tier-Leiter-Analyse (Pendant zu `rdc_tiers.py`/`leo_tiers.py`)

### Noch dupliziert
- (erledigt) `es_compare.py` + `leo_compare.py` durch `tools/compare.py` ersetzt und entfernt. ES-`deals`-Logik nach `tools/es_deals.py` ausgelagert.

### Nur Leo
- `tools/leo_tiers.py` — Tier-Erkennung aus Kapazitätsschwellen
- `tools/leo_currency.py` — Multiwährungs-Vergleich (CZK/EUR/PLN)
- `tools/leo_network.py` — Netzweite Übersicht
- `tools/leo_segment_pricing.py` — Teilstrecken-Preise
- `tools/leo_surcharge_analysis.py` — Wochenend-Aufschlag-Erkennung

### Nur ES
- Fare-Varianten (easy-night / good-night / flex-night) — Leo hat nur einen Preis pro Klasse
- Last-Minute-Deals-Tracking
- Kapazitätssprung-Erkennung (Wagenzugaben)

## Ziel-Architektur

```
tools/
├── compare.py              Unified: diff, trend, anomaly (ersetzt es_compare + leo_compare)
├── tiers.py                Unified: Tier-Erkennung (Leo: kapazitätsbasiert, ES: vorlaufzeit+kapazität)
├── pricing_model.py        Unified: Pricing-Modell-Analyse (Korrelation Preis/Kapazität/Vorlaufzeit)
├── currency.py             Leo-spezifisch (ES hat nur EUR)
├── network.py              Leo-spezifisch (ES hat feste Routen)
├── capacity_events.py      Unified: Wagenzugaben, Stornos, Kopplungsänderungen erkennen
└── deals.py                ES-spezifisch (Last-Minute-Seite)
```

## Schritt-für-Schritt

### Phase 1: compare.py vereinheitlichen
- `tools/compare.py` als unified wrapper mit `--provider leo|es|all`
- Nutzt `lib/loaders.py` (existiert schon)
- Diff/Trend/Anomaly-Logik ist identisch
- Route-Discovery via `loaders.get_all_routes()`
- Leo/ES-spezifische Formatierung in Output-Layer

**Status (07.09.2026): erledigt.** `tools/compare.py` mit `--provider {es|leo|snalltaget|rdc|sj|all}`, Modi diff/trend/anomaly/routes plus interaktivem Menü (Aufruf ohne Argumente). Route-Discovery via `loaders.get_all_routes()`, anomaly via `lib.analysis.anomaly_scan`. ES-`deals`-Logik als eigenständiges `tools/es_deals.py` ausgelagert (ES-spezifisch, nutzt separate Last-Minute-Datei). `es_compare.py` und `leo_compare.py` entfernt.

### Phase 2: Tier-Analyse verallgemeinern
- `tools/tiers.py` mit zwei Modellen:
  - `--model capacity` (Leo): Preis = f(Restkapazität)
  - `--model hybrid` (ES): Preis = f(Vorlaufzeit, Kapazität, Nachfrage)
- Automatische Modell-Erkennung anhand Provider

### Phase 3: Pricing-Modell-Analyse (neu)
- `tools/pricing_model.py`: Korrelationsanalyse
  - Kapazität vs. Preis (Scatter + R²)
  - Vorlaufzeit vs. Preis (Buckets)
  - Preisänderungs-Richtung (steigt/sinkt/stabil über Zeit)
- Vergleichende Ausgabe: "Leo = deterministisch, ES = aktiv gesteuert"

### Phase 4: Kapazitäts-Events
- `tools/capacity_events.py`: Erkennt automatisch:
  - Wagenzugaben (Kapazitätssprung >50 in einem Snapshot)
  - Kupplungsänderungen (Leo: Sleeper+Lady synchron)
  - Ausverkäufe (Kapazität → 0/None)
  - Stornowellen (Kapazität steigt unerwartet)

## Datenformat-Unterschiede (Referenz)

| Aspekt | Leo | ES |
|--------|-----|-----|
| Kapazität | 0-100 (abstrakt) | Absolute Platzzahl |
| Preis pro Klasse | 1 Preis (Tier-basiert) | Bis zu 3 Fare-Varianten |
| Währungen | CZK, EUR, PLN | EUR |
| Klassen-Benennung | ECOSLEEPER, ECOSLEEPERLADY, ECO, BUS | couchette-5, comfort-single, berth-double, etc. |
| Daten-Quelle | GraphQL API | REST API (Azure) |
| Pricing-Modell | Deterministisch (Kapazitätsschwellen) | Hybrid (Vorlaufzeit + Nachfrage) |
| Preissenkungen | Nie (nur bei Storno → Kapazität steigt → Tier sinkt) | Ja (aktiv bei schwacher Nachfrage) |
| Wagenzugaben | Nicht beobachtet | Nachgewiesen |

## Priorität

1. **Phase 3** zuerst — liefert sofort Vortragsmaterial (Vergleich Leo vs. ES)
2. **Phase 4** — automatische Event-Erkennung spart manuelle Analyse
3. **Phase 1** — Code-Hygiene, weniger Duplikation
4. **Phase 2** — langfristig nützlich, aber Tier-Logik ist komplex
