#!/bin/bash
# Sequential availability snapshots — runs nightly via cron
# Each job runs independently; failures don't block subsequent jobs

TODAY=$(date +%Y%m%d)
NOW=$(date '+%Y-%m-%d %H:%M:%S')
BASE=~/Projects/nighttrain-monitor
SCRAPERS="$BASE/scrapers"
LEO_DATA="$BASE/data/leo"
ES_DATA="$BASE/data/es"
SNA_DATA="$BASE/data/snalltaget"
RDC_DATA="$BASE/data/rdc"
NOX_DATA="$BASE/data/nox"

log_leo() { echo "[$NOW] $1" >> "$LEO_DATA/cron.log"; }
log_es()  { echo "[$NOW] $1" >> "$ES_DATA/cron.log"; }
log_sna() { echo "[$NOW] $1" >> "$SNA_DATA/cron.log"; }
log_rdc() { echo "[$NOW] $1" >> "$RDC_DATA/cron.log"; }
log_nox() { echo "[$NOW] $1" >> "$NOX_DATA/cron.log"; }

# Generic runner: run LOGFILE LOGFN DESC CMD...
run() {
    local logfile="$1"; shift
    local logfn="$1"; shift
    local desc="$1"; shift
    if python3 "$@" 2>> "$logfile"; then
        $logfn "OK: $desc"
    else
        $logfn "FAIL: $desc (exit $?)"
    fi
}

log_leo "=== Start run-all ==="
log_es  "=== Start run-all ==="
log_sna "=== Start run-all ==="
log_rdc "=== Start run-all ==="

# Leo Express: Weimar–Przemyśl
cd "$BASE"
run "$LEO_DATA/cron.log" log_leo "weimar-przemysl CZK" "$SCRAPERS/leo_availability.py" 8010366 5100234 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_weimar-przemysl-czk.json"
run "$LEO_DATA/cron.log" log_leo "weimar-przemysl EUR" "$SCRAPERS/leo_availability.py" 8010366 5100234 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_weimar-przemysl-eur.json"
run "$LEO_DATA/cron.log" log_leo "przemysl-weimar CZK" "$SCRAPERS/leo_availability.py" 5100234 8010366 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_przemysl-weimar-czk.json"
run "$LEO_DATA/cron.log" log_leo "przemysl-weimar EUR" "$SCRAPERS/leo_availability.py" 5100234 8010366 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_przemysl-weimar-eur.json"

# Leo Express: Weimar–Frankfurt
run "$LEO_DATA/cron.log" log_leo "weimar-frankfurt CZK" "$SCRAPERS/leo_availability.py" 8010366 8002041 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_weimar-frankfurt-czk.json"
run "$LEO_DATA/cron.log" log_leo "weimar-frankfurt EUR" "$SCRAPERS/leo_availability.py" 8010366 8002041 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_weimar-frankfurt-eur.json"
run "$LEO_DATA/cron.log" log_leo "frankfurt-weimar CZK" "$SCRAPERS/leo_availability.py" 8002041 8010366 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_frankfurt-weimar-czk.json"
run "$LEO_DATA/cron.log" log_leo "frankfurt-weimar EUR" "$SCRAPERS/leo_availability.py" 8002041 8010366 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_frankfurt-weimar-eur.json"

# Leo Express: Weimar–Bohumín
run "$LEO_DATA/cron.log" log_leo "weimar-bohumin CZK" "$SCRAPERS/leo_availability.py" 8010366 5434124 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_weimar-bohumin-czk.json"
run "$LEO_DATA/cron.log" log_leo "weimar-bohumin EUR" "$SCRAPERS/leo_availability.py" 8010366 5434124 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_weimar-bohumin-eur.json"
run "$LEO_DATA/cron.log" log_leo "bohumin-weimar CZK" "$SCRAPERS/leo_availability.py" 5434124 8010366 --days 136 -q -c CZK -o "$LEO_DATA/${TODAY}_bohumin-weimar-czk.json"
run "$LEO_DATA/cron.log" log_leo "bohumin-weimar EUR" "$SCRAPERS/leo_availability.py" 5434124 8010366 --days 136 -q -c EUR -o "$LEO_DATA/${TODAY}_bohumin-weimar-eur.json"

# European Sleeper: Hamburg–Paris
cd "$ES_DATA"
run "$ES_DATA/cron.log" log_es "hamburg-paris" "$SCRAPERS/es_availability.py" hamburg paris --days 365 -q -o "${TODAY}_hamburg-paris.json"
run "$ES_DATA/cron.log" log_es "paris-hamburg" "$SCRAPERS/es_availability.py" paris hamburg --days 365 -q -o "${TODAY}_paris-hamburg.json"
# European Sleeper: Bruxelles-Praha
run "$ES_DATA/cron.log" log_es "bruxelles-praha" "$SCRAPERS/es_availability.py" bruxelles praha --days 365 -q -o "${TODAY}_bruxelles-praha.json"
run "$ES_DATA/cron.log" log_es "praha-bruxelles" "$SCRAPERS/es_availability.py" praha bruxelles --days 365 -q -o "${TODAY}_praha-bruxelles.json"

# European Sleeper: Bruxelles-Milano (ab 09.09.2026)
run "$ES_DATA/cron.log" log_es "bruxelles-milano" "$SCRAPERS/es_availability.py" bruxelles milano --days 365 -q -o "${TODAY}_bruxelles-milano.json"
run "$ES_DATA/cron.log" log_es "milano-bruxelles" "$SCRAPERS/es_availability.py" milano bruxelles --days 365 -q -o "${TODAY}_milano-bruxelles.json"

run "$ES_DATA/cron.log" log_es "last-minute-deals" "$SCRAPERS/es_last_minute.py" -q -o "${TODAY}_last-minute-deals.json"


# Snälltåget (4 bidirectional pairs = 8 route files)
log_sna "Start snalltaget"
cd "$BASE"

run "$SNA_DATA/cron.log" log_sna "berlin-stockholm"  "$SCRAPERS/snalltaget_availability.py" Berlin 740000001 --days 120 -q -o "$SNA_DATA"
run "$SNA_DATA/cron.log" log_sna "hamburg-stockholm" "$SCRAPERS/snalltaget_availability.py" Hamburg 740000001 --days 120 -q -o "$SNA_DATA"
run "$SNA_DATA/cron.log" log_sna "berlin-malmoe"     "$SCRAPERS/snalltaget_availability.py" Berlin "Malmö C" --days 120 -q -o "$SNA_DATA"
run "$SNA_DATA/cron.log" log_sna "dresden-stockholm" "$SCRAPERS/snalltaget_availability.py" Dresden 740000001 --days 120 -q -o "$SNA_DATA"

# RDC EuroNight (2 directions)
log_rdc "Start rdc"

run "$RDC_DATA/cron.log" log_rdc "hamburg-stockholm" "$SCRAPERS/rdc_availability.py" 5 57 -q -o "$RDC_DATA"
run "$RDC_DATA/cron.log" log_rdc "stockholm-hamburg" "$SCRAPERS/rdc_availability.py" 57 5 -q -o "$RDC_DATA"


# SJ night train tier scan (4 routes × 2 directions, parallel)
SJ_DATA="$BASE/data/sj"
log_sj()  { echo "[$NOW] $1" >> "$SJ_DATA/cron.log"; }
log_sj "=== Start run-all ==="

run "$SJ_DATA/cron.log" log_sj "stockholm-malmoe" "$SCRAPERS/sj_availability.py" 740000001 740000003 --days 120 -q -o "$SJ_DATA" &
run "$SJ_DATA/cron.log" log_sj "stockholm-duved"  "$SCRAPERS/sj_availability.py" 740000001 740000308 --days 120 -q -o "$SJ_DATA" &
run "$SJ_DATA/cron.log" log_sj "stockholm-umea"   "$SCRAPERS/sj_availability.py" 740000001 740000144 --days 120 -q -o "$SJ_DATA" &
run "$SJ_DATA/cron.log" log_sj "stockholm-lulea"  "$SCRAPERS/sj_availability.py" 740000001 740000190 --days 120 -q -o "$SJ_DATA" &
wait  # all 4 SJ routes finish before continuing

# NOX Mobility (1 route, 2 directions) — Hamburg <-> München
# Season 2027-03-23..2027-12-10, ~6 days/week. --days 445 reaches season end.
log_nox "=== Start run-all ==="
cd "$BASE"
run "$NOX_DATA/cron.log" log_nox "hamburg-muenchen" "$SCRAPERS/nox_availability.py" aa8c46ab-660f-4a1d-9422-1dd1d1d8e045 9fb61762-46bf-462f-9e1a-a859d96a87ac --days 445 -q -o "$NOX_DATA"
run "$NOX_DATA/cron.log" log_nox "muenchen-hamburg" "$SCRAPERS/nox_availability.py" 9fb61762-46bf-462f-9e1a-a859d96a87ac aa8c46ab-660f-4a1d-9422-1dd1d1d8e045 --days 445 -q -o "$NOX_DATA"

# Analyze: validate predictions + generate new ones
cd "$BASE"
run "$LEO_DATA/cron.log" log_leo "analyze" bin/analyze.py --mode predict -q

log_leo "=== End run-all ==="
log_es  "=== End run-all ==="
log_sna "=== End run-all ==="
log_rdc "=== End run-all ==="
log_sj  "=== End run-all ==="
log_nox "=== End run-all ==="
