# Nordlicht Scraper — Raspi Setup

## Dateien auf den Pi kopieren

```bash
scp -i ~/.ssh/pi-raspberry scrapers/snalltaget_nordlicht.py pi@192.168.16.16:~/Projects/night-train-monitor/scrapers/
scp -i ~/.ssh/pi-raspberry bin/run-nordlicht.sh pi@192.168.16.16:~/Projects/night-train-monitor/bin/
```

## Auf dem Pi

```bash
ssh -i ~/.ssh/pi-raspberry pi@192.168.16.16

# Executable machen
chmod +x ~/Projects/night-train-monitor/bin/run-nordlicht.sh

# Testlauf
cd ~/Projects/night-train-monitor
python3 scrapers/snalltaget_nordlicht.py

# Cron-Job einrichten (20 min nach dem Hauptlauf)
crontab -e
# Einfügen:
20 0 * * * ~/Projects/night-train-monitor/bin/run-nordlicht.sh
```

## Prüfen

```bash
# Log checken
tail -5 ~/Projects/night-train-monitor/data/snalltaget/cron.log

# Output checken
ls -la ~/Projects/night-train-monitor/data/snalltaget/*narvik*
```

## Nach dem 27. November entfernen

```bash
ssh -i ~/.ssh/pi-raspberry pi@192.168.16.16

# Cron-Eintrag löschen
crontab -e
# Zeile mit run-nordlicht.sh entfernen

# Optional: Dateien aufräumen (Daten behalten, Skripte löschen)
rm ~/Projects/night-train-monitor/bin/run-nordlicht.sh
rm ~/Projects/night-train-monitor/scrapers/snalltaget_nordlicht.py
```

## Hinweise

- Skript stoppt automatisch nach dem 27.11. (date-check im Shell-Script)
- Output: `YYYYMMDD_malmoe-narvik.json` + `YYYYMMDD_narvik-malmoe.json`
- Kapazität outbound extrem niedrig (cap=1 am 31.08.) — tägliches Tracking wichtig
- Nur 1 API-Call für searchjourney (oppositedate liefert beide Richtungen)
- Zug 20 outbound: NTB (Liegeplatz) + NTPC (Private Compartment)
- Zug 21 inbound: nur NTPC (Private Compartment), kein NTB
- Laufzeit: ~3 Sekunden (3 API-Calls: 2× calendar + 1× searchjourney)
