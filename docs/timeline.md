# Leo Express LE232/LE235 — Beobachtungs-Timeline

Chronologische Dokumentation aller beobachteten Änderungen an Route, Pricing,
Konfiguration und Verfügbarkeit. Quellen: API-Snapshots, Website, ÖBB SCOTTY, DB InfraGo.

## Juni 2026

- **26.06.** Betriebsstart LE232/LE235, Frankfurt Flughafen Fernbf ↔ Bohumín
  - Nur Sitzwagen (Economy + Business)
  - Betriebstage: Di–Sa

## Juli 2026

- **~01.07.** (ca.) Wechsel Endpunkt Frankfurt Flughafen → Frankfurt (Main) Süd
  - Grund unklar (Bauarbeiten? Trassenkonflikt?)
- **~10.07.** (ca.) Liegewagen erstmals im Zug (Quelle: Reiseberichte)
- **30.07.** Verlängerung bis Przemyśl Główny (PL) betrieblich gestartet
  - Liegewagen: 1× RIC B6-1, 10 Abteile × 4 Liegen = 40 Plätze
  - Aufteilung: 5 Abteile ECOSLEEPER (mixed) + 5 Abteile ECOSLEEPERLADY (women-only)
  - Betriebstage Przemyśl-Abschnitt: Do/Fr/Sa (hin), Fr/Sa/So (rück)

## August 2026

- **01.08.** Beginn systematische Datenerhebung (tägliche Snapshots, 6 Routen × 2 Währungen)
- **15.08.** Sep/Okt-Tickets für Przemyśl freigeschaltet (12 neue Daten auf einen Schlag)
  - Alle Sleeper/Lady starten bei T1 (37,50€ / 899 CZK)
  - Website behauptet weiterhin "nur bis 29.08." — API verkauft bis 24.10.
- **~16.08.** T1 Sleeper beginnt zu verschwinden auf Sep-Daten (Buchungen)
- **18.08.** **Systemwechsel: Sleeper/Lady-Preise gekoppelt**
  - Vorher: unabhängige Tier-Berechnung pro 20-Bett-Pool (35–42% unterschiedliche Preise)
  - Nachher: identischer Preis, vermutlich gemeinsamer 40-Bett-Tier-Zähler
  - Betrifft alle 6 Routen gleichzeitig (Backend-Änderung über Nacht)
- **~18.08.** (ca.) Interrail-Reservierung für Sleeper/Lady gesperrt
  - Vorher: 0€ Aufpreis für Liegewagen mit Interrail/Eurail
  - Nachher: "ausverkauft" bei Sleeper/Lady, nur noch ECO/BUS kostenlos
  - Keine öffentliche Kommunikation der Änderung
- **22.08.** Kein T1 Sleeper mehr verfügbar (alle Daten mindestens T2)
  - T1-Fenster war ~7 Tage offen (15.–22.08.)
  - Lady bei 20/20 Plätzen trotzdem T2 → bestätigt Kopplung

## September 2026

- **07.09.** Sleeper/Lady-Kopplung weiterhin aktiv, seit 18.08. stabil
  - Verifiziert an 957 Preispaaren (Route Weimar–Przemyśl EUR, Snapshots 29.07.–07.09.)
  - Vor 18.08.: jeder Snapshot 7–17 abweichende Paare (getrennte Tier-Zähler)
  - Ab 18.08.: 0 Abweichungen an jedem einzelnen Tag (21 Tage durchgehend gekoppelt)
  - In einigen Wochen erneut prüfen
- **07.09.** Live-API-Check gegen graph.leoexpress.com/le (unauthentifiziert):
  - Introspection weiterhin offen, 169 Types total (161 fachlich + 8 __intern). Doku-Wert 158 war Initialstand, ohne Anpassung auf 169 erhöht.
  - `creditExchangeRates` ohne Auth abrufbar, Raten unverändert: CZK=1, EUR=24, PLN=5.
  - Interrail-Status bestätigt: `interraileco` gibt nur Economy (0€), `interrailbus` nur Business (0€). Sleeper/Sleeper Lady für Interrail weiterhin gesperrt (Gegenprobe Adult zeigt alle 4 Klassen).
  - Nebenbefund: GraphQL-Root-Feld heißt `searchResults`, nicht `searchConnections` (nur operationName). `persons`=RateArgument, departure_time/arrival_time=StructuredDate.
  - Sleeper-Angebot endet 24.10. (Przemyśl-Ende); Bohumín-Service bis 12.12. nur noch ECO. Stützt Kurswagen-Hypothese (Liegewagen hängt am PL-Abschnitt). Nov/Dez bisher ohne Sleeper konfiguriert.
- **14.09.** Rabattaktion "1+50%" (Code `LE50`) angekündigt
  - Quelle: https://x.com/leoexpress/status/2099357629407477992 (6:40, 14.09.2026)
  - 50% Rabatt auf jedes zweite Ticket, gerade Ticketzahl, gleiche Verbindung/Datum/Zeit
  - Gültig für Economy, **Economy Sleeper und Economy Sleeper Lady** (`class_id: [8,7,3]`)
  - Verkaufsfenster 14.–18.09.2026, Fahrten bis 12.12.2026, `deleted_at: 2026-09-21`
  - Anwendung nur via REST `POST /api/salecode/apply` (session-gebunden); `checkSalecodeRemains` erkennt den 1+50%-Typ nicht (Error 1060)
  - Live verifiziert (15.09., weimar–przemyśl 22.10., 9× Sleeper): 1132.20€ → 880.60€ (4 Paare à 62.9€ Rabatt)
  - Wechselwirkung mit Tier-Kaskade dokumentiert (siehe USE-CASE.md → Voucher × Tier Interaction): Paar lohnt nur bei `p2 ≤ 1.5·p1`, Sprung auf T6 frisst die Ersparnis

## Fahrplanwechsel (geplant)

- **18.09.** Rückkehr Frankfurt Flughafen Fernbf (Mo–Fr), Frankfurt Süd nur noch Sa+So
  - Quelle: ÖBB SCOTTY / MERITS
  - Leo API verkauft Flughafen bisher nur Di+Mi ab 27.10.
  - Täglicher Betrieb (statt Di–Sa)
- **24.10.** Letztes buchbares Datum Przemyśl-Abschnitt
- **25.10.** Kapazitätssprung auf allen Routen: nur noch ECO, 100+ Plätze, kein Sleeper
  - Vermutung: Liegewagen ist an PL-Verlängerung gebunden, entfällt mit Przemyśl-Ende
  - Oder: neue Daten noch nicht vollständig konfiguriert (werden nachgepflegt)
- **12.12.** Fahrplan bis Bohumín laut Buchungssystem


## Vor dem Vortrag prüfen (kurz vor 10.10.)

- [x] Introspection noch offen? → ja (07.09., 169 Types)
- [x] creditExchangeRates noch ohne Auth abrufbar? → ja (07.09., CZK=1/EUR=24/PLN=5)
- [x] Sleeper/Lady noch gekoppelt? → ja (07.09., seit 18.08. stabil)
- [x] Interrail-Status Sleeper (immer noch gesperrt?) → ja gesperrt (07.09.; eco→ECO, bus→Business)
- [x] Neue Daten nach 24.10.? → kein Sleeper nach 24.10., Bohumín-Service bis 12.12. nur ECO (07.09.)
- [x] EUR/CZK-Kurs → Leo fix 24 CZK/EUR (07.09.); Markt ~25,3 → CZK ~5% günstiger
- [x] Type-Count → 169 (07.09.; 158 war Initialstand)
- [ ] Fahrplanwechsel 18.09. eingetreten? Flughafen aktiv?

Falls API geschlossen: im Vortrag erwähnen ("war offen bis X, wurde zwischen Y und Z geschlossen — noch beeindruckender, ich zeige euch was ich retten konnte").

## Offene Fragen

- Kommt der Liegewagen nach dem 24.10. zurück? (Winterfahrplan? Neue PL-Verlängerung?)
- Wird die Przemyśl-Strecke über den 24.10. hinaus verlängert?
- Hängt der Sleeper physisch am polnischen Streckenteil? (Kurswagen-Logik: Sleeper fährt nur Bohumín↔Przemyśl?)
- Wird die Sleeper/Lady-Kopplung beibehalten oder war es ein Fehler?
- Werden Nov/Dez-Daten mit Sleeper nachkonfiguriert?

---

# Snälltåget D 10300/10301 — Beobachtungs-Timeline

## August 2026

- **24.08.** Beginn systematische Datenerhebung (4 Routenpaare: Berlin↔Stockholm, Hamburg↔Stockholm, Berlin↔Malmö + Trondheim-Testfahrt)
- **26.08.** Trondheim-Testfahrt erstmals in API buchbar (Zug 24/25, 05.–06.09.2026)
  - Outbound: kein Sitzplatz, nur Berth/Compartment. Cap=10 (4 Wagen)
  - Inbound: volles Sortiment inkl. Sitze. Cap=59
  - Compartment outbound mit 50% Launch-Rabatt (1.499 statt 2.999 SEK)
- **27.08.** Dresden als 5. Routenpaar aufgenommen (Dresden↔Stockholm)
  - Service: Freitags southbound (D 10301), Sonntags northbound (D 10300)
  - 14 Betriebstage pro Richtung durch November 2026
- **27.08.** Overshoot-Pricing entdeckt: gleicher Zug, gleicher Tag, verschiedene Preise pro Buchungsherkunft
  - Compartment Stockholm→Dresden bis 1.000 SEK günstiger als →Berlin/Hamburg
  - Northbound Berlin→Stockholm bis 4.000 SEK günstiger als Hamburg→Stockholm
  - Ursache: per-Origin Kontingentmanagement mit separaten Yield-Tiers
- **27.08.** Per-Origin Kapazitätsunterschiede bestätigt
  - Hamburg: cap 85–290 (Haupteinstieg, hohe Nachfrage)
  - Berlin: cap 1–70 (wenig bekannt, 'totes Inventar')
  - Dresden: cap 4–73 (wöchentlich, teilt Berlin-Kontingent)
- **27.08.** Berth-Seat-Inversion auf Transfer-Routen (30.08.: NTBSF 1.248 < SPSF 1.498)
- **27.08.** Tier-Analyse: 16 Preisstufen, Sprung bei quota ≈ 5
- **27.08.** `tools/snalltaget_compare.py` erstellt (diff, trend, tiers, overshoot, inversion)
- **27.08.** `lib/loaders.py` erweitert: Snälltåget + RDC Loader, `bin/analyze.py` erkennt alle 4 Operatoren (24 Routen)

# European Sleeper — Beobachtungs-Timeline

## August 2026

- **27.08.** ES Newsletter: Buchungsfenster-Erweiterung ab 08.09.2026 (Spring + Summer 2027)
  - Erstmals zwei Saisons gleichzeitig freigegeben
  - Scraper-Window von 183 auf 365 Tage erweitert
- **27.08.** Neue Route angekündigt: Brussels/Amsterdam → Copenhagen/Malmö (ab April 2028, mit RDC, 3×/Woche)