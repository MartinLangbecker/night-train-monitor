#!/bin/bash
# Snälltåget Nordlicht (Malmö ↔ Narvik) — daily availability snapshot
# Separate cron job: auto-stops after 2026-11-27
#
# Cron entry (daily at 00:20, after run-all.sh):
#   20 0 * * * ~/Projects/nighttrain-monitor/bin/run-nordlicht.sh
#
# Auto-stops after Nov 27 (no-op if date > 2026-11-27)

TODAY=$(date +%Y%m%d)
NOW=$(date '+%Y-%m-%d %H:%M:%S')
BASE=~/Projects/nighttrain-monitor
SNA_DATA="$BASE/data/snalltaget"

# Stop after the inbound travel date
if [ "$TODAY" -gt "20261127" ]; then
    echo "[$NOW] Nordlicht scrape: past Nov 27, skipping" >> "$SNA_DATA/cron.log"
    exit 0
fi

echo "[$NOW] Start nordlicht scrape" >> "$SNA_DATA/cron.log"

cd "$BASE"
if python3 "$BASE/scrapers/snalltaget_nordlicht.py" -q -o "$SNA_DATA" 2>> "$SNA_DATA/cron.log"; then
    echo "[$NOW] OK: nordlicht" >> "$SNA_DATA/cron.log"
else
    echo "[$NOW] FAIL: nordlicht (exit $?)" >> "$SNA_DATA/cron.log"
fi
