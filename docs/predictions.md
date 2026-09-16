# Prediction System

Sellout-Prognosen für Nachtzug-Buchungsklassen. Prognostiziert, wann eine Klasse auf einer Route für ein bestimmtes Reisedatum ausverkauft sein wird.

## Algorithmus

### Datengrundlage

Tägliche Snapshots pro Route erfassen Kapazität und Preis je Buchungsklasse und Reisedatum. Die Fill Curve einer Klasse ist die Zeitreihe `[(snap_date, capacity, price, lead_days)]`.

### Regression (Weighted)

Lineare Regression auf die Capacity-Zeitreihe mit exponentiellen Decay-Gewichten:

- **Halbwertszeit**: 14 Tage (neuere Punkte zählen stärker, aber mit Trägheit)
- **Fallback**: Ungewichtete Regression bei <5 Datenpunkten
- **Gewicht**: `w_i = exp(-λ * (max_day - day_i))`, λ = ln(2)/14

Output: Slope (Plätze/Tag Rückgang), R² (Confidence), extrapolierter Sellout-Zeitpunkt.

### Erzeugungsfilter

Eine Prediction wird nur erstellt wenn:

| Filter | Schwelle |
|--------|----------|
| Datenpunkte | ≥ 7 (= 1 Woche Beobachtung) |
| Kapazitäts-Trend | fallend (slope < 0) |
| Aktuelle Kapazität | ≥ 3 |
| Decline Rate | ≥ 0.1 Plätze/Tag |
| R² (Confidence) | > 0.5 |
| Tage bis Sellout | < 30 |
| Sellout vor Reisedatum | ja |

### Deduplizierung & Supersede

Pro Key `(provider, route, travel_date, class)` existiert maximal eine offene Prediction. Wenn eine neue Berechnung signifikant abweicht:

- Sellout-Datum >7 Tage verschieden, oder
- Confidence-Differenz >0.15

→ alte Prediction wird mit Outcome `superseded` in die History verschoben, neue übernimmt.

### Cooldown

Keys die am selben Tag als `invalidated` oder `wrong_reversal` aufgelöst wurden, werden nicht neu erzeugt (verhindert Endlos-Schleifen).

## Validierung

Täglich (Cron 00:00, nach Scraping) prüft `validate()` jede offene Prediction:

### Sofortige Invalidierung

Kapazität ist >2 über den Wert bei Prediction-Erstellung gestiegen → `invalidated` (Stornierungen haben den Trend umgekehrt).

### Nach Reisedatum

| Letzter Snapshot zeigt | Outcome |
|------------------------|---------|
| Kapazität = 0, Delta ≤1 Tag zum Predicted Sellout | `correct_exact` |
| Kapazität = 0, Delta >1 Tag | `correct_late` |
| Kapazität >0, aber ≤50% des Ausgangswerts | `wrong_trend` |
| Kapazität >0 und ≥ Ausgangswert | `wrong_reversal` |
| Keine Daten verfügbar | `expired` |

### Predicted Sellout überschritten (Reisedatum noch nicht)

| Zustand | Outcome |
|---------|---------|
| Kapazität = 0, ≤1 Tag danach | `correct_exact` |
| Kapazität = 0, >1 Tag danach | `correct_late` |
| >3 Tage überschritten, Kapazität > Ausgangswert | `wrong_reversal` |
| >3 Tage überschritten, Kapazität ≤50% Ausgangswert | `wrong_trend` |
| ≤3 Tage überschritten | bleibt offen (Grace Period) |

## Confidence Decay

Für überfällige Predictions (predicted sellout date vorbei, aber noch nicht aufgelöst):

```
effective_confidence = confidence * max(0.3, 1.0 - 0.15 * days_overdue)
```

| Tage überfällig | Decay Factor | Status |
|-----------------|-------------|--------|
| 0 | 1.00 | active |
| 1 | 0.85 | fading |
| 2 | 0.70 | fading |
| 3 | 0.55 | fading |
| 4 | 0.40 | overdue |
| 5+ | 0.30 (floor) | overdue |

Transiente Felder (`effective_confidence`, `prediction_status`) werden berechnet aber nicht persistiert.

## Accuracy Scoring

### Binäre Accuracy

`correct / (correct + wrong) * 100%`

Zählt alle `correct_*` als correct und alle `wrong_*` als wrong. Excludiert: expired, invalidated, superseded.

### Weighted Score

| Outcome | Gewicht |
|---------|---------|
| `correct_exact` | 1.0 |
| `correct_late` | 0.7 |
| `wrong_trend` | 0.3 |
| `wrong_reversal` | 0.0 |

## Parameter-Tuning & Backtesting

### Aktulle Defaults (Variante C, seit 2026-08-14)

| Parameter | Wert | Begründung |
|-----------|------|-----------|
| Halbwertszeit | 14 Tage | Nachtzug-Kapazität schwankt durch Stornos; kürzere Werte erzeugen instabile Prognosen |
| Supersede-Schwelle | 7 Tage | Tägliche Regression-Schwankungen <7d sind Rauschen, kein echtes Signal |
| Min-Datenpunkte | 7 | 1 Woche Beobachtung bevor Prognose sinnvoll; verhindert frühzeitige Fehlalarme |
| Min-Kapazität | 3 | Unter 3 ist jede Stornierung ein binäres Event |
| Min-Decline-Rate | 0.1/Tag | Extrem langsamer Decline bei niedriger Kapazität = Noise |
| Min-Confidence (R²) | 0.5 | Unter 0.5 passt die Gerade schlecht auf die Daten |

### Problemstellung

Das Modell extrapoliert linearen Kapazitätsrückgang auf Null. In der Praxis:

1. **Kein monotoner Abfall** — Stornierungen erzeugen Schwankungen nach oben
2. **Stabilisierung auf niedrigem Niveau** — Kapazität fällt auf 2-5 und bleibt dort (Restposten)
3. **Nachtzüge haben wenig Inventory** — kleine absolute Zahlen (5-50 Plätze pro Klasse), ein einzelner Storno ändert den Trend

### Getestete Varianten (Backtest 2026-07-29 bis 2026-08-14, 17 Tage)

| Variante | Supersede | Halflife | MinPts | Wrong | Invalidated | Superseded | Open |
|----------|-----------|----------|--------|-------|-------------|-----------|------|
| A (aggressiv) | 2d | 7d | 3 | 30 | 23 | 663 | 293 |
| B (stabil) | 5d | 14d | 5 | 19 | 11 | 329 | 246 |
| **C (konservativ)** | **7d** | **14d** | **7** | **8** | **10** | **135** | **196** |

Alle Varianten: 0% Binary Accuracy (kein einziger Sellout im Testzeitraum).

**Warum Variante C gewählt:**
- 75% weniger Fehlprognosen (8 vs 30)
- 80% weniger Supersedes (135 vs 663) → stabilere Predictions
- Konservativ = weniger Predictions insgesamt, aber die die existieren haben mehr Substanz
- Physikalisch begründet (nicht auf Testdaten getuned)

### Overfitting-Risiko

17 Tage sind keine belastbare Datenbasis. Die Parameter wurden bewusst konservativ gewählt und physikalisch begründet statt numerisch optimiert. Empfehlung: nach 4+ Wochen (Anfang September) erneut evaluieren mit Train/Test-Split.

### Backtest wiederholen

```bash
cd ~/Projects/nighttrain-monitor

# Dry run (Default): spielt alle Snapshots chronologisch durch und scored,
# schreibt aber NICHTS. Startet immer bei leerem Zustand.
python3 tools/backtest.py

# Ergebnis in eine Datei schreiben (live predictions.json bleibt unberührt)
python3 tools/backtest.py -o data/predictions.backtest.json

# Nur wenn die produktive Datei bewusst neu aufgebaut werden soll:
python3 tools/backtest.py --write

# Varianten vergleichen (ändert die gespeicherte predictions.json nicht)
python3 tools/backtest-compare.py
```

Der Backtest baut den Zustand jedes Laufs von Grund auf neu auf (kein manuelles
Leeren der Datei nötig). Ohne `-o` oder `--write` ist der Lauf ein Dry Run und
fasst `data/predictions.json` nicht an. Sobald mehr Tage gesammelt wurden,
liefert ein erneuter Lauf aussagekräftigere Ergebnisse.

## Persistenz

`data/predictions.json`:
```json
{
  "predictions": [...],  // Offene Predictions
  "history": [...]       // Aufgelöste mit outcome, resolved_date, actual
}
```

## Cron-Integration

`run-all.sh` (täglich 00:00):
1. Scraped alle Routen (Leo Express + European Sleeper)
2. Führt `python3 bin/analyze.py --mode predict -q` aus
3. Validiert bestehende Predictions gegen neue Daten
4. Erzeugt neue Predictions wo Kriterien erfüllt

## Geplante Erweiterungen (deferred)

### Saisonalität / Wochentags-Korrektur

Freitag/Sonntag verkauft systematisch schneller. Weekday-Factor aus `weekday_heatmap()` als Korrektur auf den extrapolierten Sellout-Zeitpunkt.

**Voraussetzung**: ≥4 Wochen Daten pro Wochentag (4 Samples). Frühestens Mitte September 2026.

### History-basierte Kalibrierung

Systematischen Modell-Bias erkennen und korrigieren.

**Voraussetzung**: ≥50 aufgelöste Predictions (correct + wrong), davon ≥20 correct und ≥10 wrong. Erwartbar erst wenn tatsächliche Sellouts eintreten.

**Kalibrierungs-Ansatz:**
1. Bias-Messung: `actual_sellout_date - predicted_sellout_date` → Median
2. Slope-Korrektur: `calibrated_slope = raw_slope * (1 + bias_factor)`
3. Confidence-Kalibrierung: wenn Predictions mit R²=0.8 nur 60% Trefferquote haben → Output skalieren
4. Segmentierung nach Provider, Klasse, Lead-Time-Bucket

### Re-Evaluation Timeline

| Datum | Aktion |
|-------|--------|
| Anfang September 2026 | Backtest mit 5+ Wochen Daten, prüfen ob Sellouts eingetreten |
| Mitte September 2026 | Saisonalitäts-Korrektur evaluieren (genug Wochentags-Daten?) |
| Oktober 2026 | Kalibrierung wenn ≥50 aufgelöste Predictions |
