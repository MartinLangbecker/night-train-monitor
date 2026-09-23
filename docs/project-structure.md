# Project Structure

```
nighttrain-monitor/
├── bin/
│   ├── analyze.py              Unified analysis (anomaly + forecast + predictions)
│   ├── run-all.sh              Cron entry: daily data collection
│   └── run-nordlicht.sh        Cron entry: limited-time Nordlicht route
├── lib/
│   ├── loaders.py              Snapshot loading (ES + LEO + RDC + Snälltåget + SJ + NOX formats)
│   ├── analysis.py             Fill curves, sellout prediction, tier alerts, anomaly scan
│   ├── tiers.py                Data-driven price-tier ladders (step-aware anomaly detection)
│   ├── predictions.py          Prediction tracking (persist + validate)
│   └── formatting.py           Output formatting
├── scrapers/
│   ├── leo_availability.py     Leo Express API scraper
│   ├── leo_all_currencies.py   Wrapper: CZK + EUR + PLN
│   ├── es_availability.py      European Sleeper scraper
│   ├── es_last_minute.py       ES last-minute deals page scraper
│   ├── rdc_availability.py     RDC EuroNight GraphQL scraper (tier-scanning)
│   ├── sj_availability.py        SJ night train scraper (adaptive tier probing)
│   ├── snalltaget_availability.py  Snälltåget REST API scraper
│   ├── snalltaget_common.py      Shared Snälltåget API functions
│   ├── snalltaget_nordlicht.py   Snälltåget Nordlicht scraper (Malmö ↔ Narvik)
│   ├── snalltaget_tier_probe.py  Snälltåget reserve→measure→cancel tier probe (PoC)
│   └── nox_availability.py     NOX Mobility scraper (direct capacity, no tier scan)
├── tools/
│   ├── compare.py              Unified: diff, trend, anomaly, routes, interactive (all providers)
│   ├── es_deals.py             ES: last-minute deals vs regular prices
│   ├── snalltaget_compare.py    Snälltåget: diff, trend, tiers, overshoot, inversion
│   ├── leo_currency.py         Multi-currency comparison
│   ├── leo_network.py          Network-wide availability overview
│   ├── leo_segment_pricing.py  Sub-route pricing analysis
│   ├── leo_surcharge_analysis.py  Weekend surcharge timing
│   ├── leo_tiers.py            Price tier discovery
│   ├── rdc_tiers.py            RDC: Normalpreis tier ladder + live tier position
│   ├── sj_tiers.py             SJ: per-class/flex tier ladder (route-specific)
│   ├── sj_capacity.py         SJ: tier-capacity delta, maturity, sellout forecast
│   ├── fill_compare.py         Cross-operator fill rate comparison
│   ├── pricing_model.py        Distance-based pricing model fitting
│   ├── backtest.py             Replay snapshots through the prediction system
│   └── backtest-compare.py     Parameterized backtest variants comparison
├── data/
│   ├── leo/                    LEO snapshots (YYYYMMDD_route.json)
│   ├── es/                     ES snapshots (YYYYMMDD_route.json)
│   ├── snalltaget/             Snälltåget snapshots (YYYYMMDD_route.json)
│   ├── rdc/                    RDC EuroNight snapshots (YYYYMMDD_route.json)
│   ├── sj/                     SJ night train snapshots (YYYYMMDD_route.json)
│   ├── nox/                    NOX Mobility snapshots (YYYYMMDD_route.json)
│   └── predictions.json        Forecast tracking state
├── charts/                     Generated visualizations
├── scripts/                    Chart generation scripts (LEO)
└── docs/
    ├── leo-express.md          LEO: timetable, station codes, API details
    ├── european-sleeper.md     ES: schedule, pass analysis, tier structure
    ├── rdc.md                  RDC: GraphQL API, tier scanning, wagon data
    ├── sj.md                   SJ: REST API, adaptive tier probing, night trains
    ├── snalltaget.md           Snälltåget: REST API, routes, product families
    ├── nox.md                  NOX Mobility: REST API, direct capacity, Hamburg↔München
    ├── pricing-model.md        Tier mechanics, capacity thresholds, surcharges
    ├── predictions.md          Prediction & backtest algorithm documentation
    ├── project-structure.md    This file
    ├── timeline.md             Chronological change log (route/config/pricing)
    └── USE-CASE.md             Research questions + detailed findings
```
