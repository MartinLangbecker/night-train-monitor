# Nighttrain Monitor

Automated price and availability tracking for European night trains (Leo Express, European Sleeper, Snälltåget, RDC EuroNight, SJ).
Daily snapshots, anomaly detection, sellout forecasting, booking recommendations.

## Project Structure

```
bin/       Cron entry points + unified analysis (analyze.py, run-all.sh)
lib/       Snapshot loaders, analysis, tier ladders, prediction tracking
scrapers/  One availability scraper per operator (leo, es, rdc, sj, snalltaget, nox)
tools/     Comparison, tier, capacity, backtest utilities
data/      Daily snapshots per operator (YYYYMMDD_route.json) — gitignored
docs/      Per-operator API notes, pricing model, timeline, use-case
```

Full annotated file tree: [docs/project-structure.md](docs/project-structure.md).

## Quick Start

```bash
# Daily analysis (default: future only, actionable alerts)
python3 bin/analyze.py

# Specific mode
python3 bin/analyze.py --mode sellout
python3 bin/analyze.py --mode alert --route weimar-przemysl-eur
python3 bin/analyze.py --mode anomaly --since 3

# Include past dates
python3 bin/analyze.py --all

# Unified compare (all providers)
python3 tools/compare.py routes
python3 tools/compare.py diff --provider sj --route stockholm-malmoe
python3 tools/compare.py trend --provider rdc --route hamburg-stockholm --date 2026-09-23
python3 tools/compare.py anomaly --provider all --since 3

# Tier ladders
python3 tools/sj_tiers.py stockholm-malmoe
python3 tools/sj_capacity.py --maturity
python3 tools/rdc_tiers.py hamburg-stockholm

# Interactive menu (no args)
python3 tools/compare.py

# ES last-minute deals
python3 tools/es_deals.py praha-bruxelles

# Provider-specific deep dive
python3 tools/snalltaget_compare.py overshoot
python3 tools/leo_currency.py
```

## Analysis Modes

| Mode | What it does | When to use |
|------|-------------|-------------|
| `anomaly` | Price drops, spikes, sellouts, new availability, system-wide tier moves | "What changed?" |
| `fill` | Capacity fill curves (fastest-filling dates) | "What's selling fast?" |
| `sellout` | Linear regression → sellout date prediction | "When will X sell out?" |
| `booking` | Price by lead-time bucket → sweet spot | "When should I book?" |
| `heatmap` | Price by weekday | "Which days are cheapest?" |
| `alert` | Price vs. median at same lead-time | "What's unusually cheap/expensive?" |
| `predict` | Validate past predictions, track accuracy | "Are my forecasts reliable?" |

### Tier-Aware Anomaly Detection (LEO)

Step-priced operators (currently LEO) sell a fixed contingent that climbs a
discrete price ladder as capacity is consumed. A single-tier move is the normal
case (a booking climbs one tier, a cancellation drops one) and carries no
information, so reporting it as an "anomaly" only floods the output.

`anomaly_scan` therefore reconstructs each route's tier ladder empirically from
the observed price history (`lib/tiers.py`, no hand-maintained table) and
absorbs weekend surcharges into their base tier. It then reports:

- **Individual anomalies** — jumps of ≥2 tiers, or prices that fall off the
  known ladder entirely.
- **System-wide tier moves** — a correlated shift where ≥50% of a class's active
  travel dates (min. 3) move in the same tier direction within one snapshot
  interval. This surfaces backend events (e.g. all dates reset to T1) as a
  single consolidated alert instead of dozens of per-date lines.

Operators without a usable ladder fall back to the percentage heuristic
(drop < −5%, spike > 20%).

## Data Collection (Cron)

Runs daily at 00:00 via `bin/run-all.sh`:

| Operator | Routes | Currencies | Window | Method |
|----------|--------|-----------|--------|--------|
| Leo Express | 6 routes (3 pairs × 2 dir) | CZK, EUR | 136 days | GraphQL searchConnections |
| European Sleeper | 6 routes (3 pairs × 2 dir) + deals | EUR | 365 days | REST /search/availability |
| Snälltåget | 10 routes (4 pairs + Nordlicht) | SEK | 120 days | REST /orientation/calendar + searchjourney |
| RDC EuroNight | 2 routes (Hamburg ↔ Stockholm) | EUR | 120 days | GraphQL ReadPriceCategories + tier scan |
| SJ | 8 routes (4 pairs × 2 dir) | SEK | 120 days | REST /search + /offers, adaptive n=1..9 probing |
| NOX Mobility | 2 routes (1 pair × 2 dir) | EUR | 445 days | REST /fare-calendar (≤62-day chunks) + /search |

Filenames: `YYYYMMDD_route.json` (LEO adds `-czk`/`-eur` suffix)

All scrapers take origin/destination as CLI arguments. Routes are configured in `bin/run-all.sh`.
Separate cron job for the limited-time Nordlicht route: `bin/run-nordlicht.sh` (00:20, until 27.11.).
A generic `run()` function handles logging and error tracking for all operators.

## Prediction Tracking

`bin/analyze.py` maintains `data/predictions.json`:
- Generates sellout predictions via weighted linear regression on capacity decline
- Validates predictions daily (via cron) against actual capacity data
- Graduated outcomes: `correct_exact`, `correct_late`, `wrong_trend`, `wrong_reversal`
- Auto-invalidates predictions when capacity reverses (rises >2 above baseline)
- Supersedes stale predictions when new data yields significantly different forecasts
- Confidence decay: overdue predictions show fading R² in output
- Minimum threshold: only predicts for classes with ≥3 capacity and decline ≥0.1/day

See [docs/predictions.md](docs/predictions.md) for full algorithm documentation.

## Covered Services

### Leo Express (LE232/LE235)
- Frankfurt (Main) Süd – Weimar – Dresden – Praha – Bohumín – Przemyśl Główny
- Overnight service, launched July 2026
- 4 classes: Economy, Business, Economy Sleeper, Economy Sleeper Lady
- See: [docs/leo-express.md](docs/leo-express.md)

### European Sleeper
- ES 474/475: Berlin – Hamburg – Amsterdam – Brussels – Paris (3×/week)
- ES 453/454: Amsterdam – Brussels – Dresden – Prague (3×/week)
- ES 400/401: Brussels – Köln – Aarau – Gotthard – Como – Milano (2×/week, from 09.09.2026)
- See: [docs/european-sleeper.md](docs/european-sleeper.md)

### RDC EuroNight (EN 344/345)
- Berlin Lichtenberg / Hamburg – Stockholm Central
- Operated by BTE/SJ, 3×/week per direction (season 01.09.–12.12.2026)
- 4 accommodation types: Sitz, Liege (6-berth), Bett (2-berth), Bett 1.Klasse (Deluxe)
- Tier-scanning reveals real-time demand via price jumps
- See: [docs/rdc.md](docs/rdc.md)

### Snälltåget (D 10300/10301)
- Berlin / Hamburg – Stockholm (direct overnight, same physical train as D 300)
- Dresden – Stockholm extension (Fridays southbound, Sundays northbound)
- Seasonal (Apr–Dec), daily except some gaps
- Products: Seat (semi-flex/full-flex), Private Compartment
- Shared berths (NTB) only available via transfer routing (D 300 + 3940)
- 10 routes tracked (4 pairs × 2 dir + Dresden↔Stockholm)
- Cross-origin pricing anomalies discovered (same train, different prices depending on booking origin)
- Nordlicht Sonderzug: Malmö ↔ Narvik (23./27. Nov 2026), nördlich des Polarkreises
- See: [docs/snalltaget.md](docs/snalltaget.md)


### SJ (D 1/2, D 70/71, D 91/92, D 93/94)
- Stockholm ↔ Malmö, Duved, Umeå, Luleå
- Year-round domestic night trains, ~4-5×/week
- 3 accommodation types: Couchette (6-berth), Sleeping 2nd (3-berth), Sleeping 1st (1-2 berth, en-suite)
- Adaptive tier probing via multi-passenger search (n=1→9)
- See: [docs/sj.md](docs/sj.md)

### NOX Mobility (1791/1790)
- Hamburg – Bremen – Augsburg – München (single route, overnight)
- German startup, season 2027-03-23 – 2027-12-10, ~6 days/week
- 2 tariff classes: Basic, Flex
- **Real remaining capacity exposed directly** (`availability.available`) — no tier scanning needed, unlike LEO/RDC/SJ
- See: [docs/nox.md](docs/nox.md)

## Performance

All scrapers use `http.client.HTTPSConnection` with keep-alive for persistent TLS
connections. On the Raspberry Pi, this reduces per-request latency from ~3-5s (new TLS
handshake each time) to ~0.05-0.2s (reused connection). Automatic reconnect on
connection drop (retry once).

| Scraper | Calls/Run | Runtime |
|---------|-----------|---------|
| SJ | ~400-1200 | ~1 min (4 routes parallel) |
| RDC | ~600-800 | ~4 min |
| Snälltåget | ~200-400 | ~20s |
| European Sleeper | ~100-200 | ~30s |
| Leo Express | ~140-300 | ~2 min |

## Documentation

- [Leo Express Details](docs/leo-express.md) — timetable, station codes, API, currencies
- [European Sleeper Details](docs/european-sleeper.md) — schedule, pass analysis, fares
- [RDC EuroNight](docs/rdc.md) — GraphQL API, tier scanning, wagon formation
- [SJ Night Trains](docs/sj.md) — REST API, adaptive tier probing, accommodation types
- [NOX Mobility](docs/nox.md) — REST API, direct capacity, Hamburg↔München
- [Snälltåget](docs/snalltaget.md) — REST API, routes, product families, NTB finding
- [Pricing Model](docs/pricing-model.md) — tier mechanics, capacity thresholds, surcharges
- [Timeline](docs/timeline.md) — chronological change log
- [Research & Findings](docs/USE-CASE.md) — original research log with discoveries
