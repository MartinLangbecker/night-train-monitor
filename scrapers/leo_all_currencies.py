#!/usr/bin/env python3
"""
Leo Express Multi-Currency Snapshot
Runs leo-availability.py for all currencies (CZK, EUR, PLN) in sequence.

Usage:
  python3 leo-all-currencies.py <from> <to> [options...]

All options are passed through to leo-availability.py.
Appends currency suffix to -o filename if specified.

Examples:
  python3 leo-all-currencies.py 8010366 5100234 --days 60 -q -o data/20260729_weimar-przemysl.json
    → creates: data/20260729_weimar-przemysl-czk.json
               data/20260729_weimar-przemysl-eur.json
               data/20260729_weimar-przemysl-pln.json

  python3 leo-all-currencies.py 8010366 5100234 --days 30
    → interactive output for all 3 currencies
"""

import subprocess
import sys
import os

CURRENCIES = ["CZK", "EUR", "PLN"]
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leo-availability.py")

args = sys.argv[1:]

# Find -o/--output and extract the base filename
output_base = None
output_idx = None
for i, a in enumerate(args):
    if a in ('-o', '--output') and i + 1 < len(args):
        output_base = args[i + 1]
        output_idx = i + 1
        break

# Remove -c/--currency if accidentally passed
clean_args = []
i = 0
while i < len(args):
    if args[i] in ('-c', '--currency') and i + 1 < len(args):
        i += 2  # skip
    else:
        clean_args.append(args[i])
        i += 1

for currency in CURRENCIES:
    cmd_args = list(clean_args)

    # Modify output filename to include currency suffix
    if output_base:
        base, ext = os.path.splitext(output_base)
        currency_file = f"{base}-{currency.lower()}{ext}"
        # Replace the output filename in args
        for i, a in enumerate(cmd_args):
            if a in ('-o', '--output') and i + 1 < len(cmd_args):
                cmd_args[i + 1] = currency_file
                break
    else:
        # No -o: print header between currencies
        sys.stdout.flush()
        print(f"\n{'='*60}")
        print(f"  {currency}")
        print(f"{'='*60}")
        sys.stdout.flush()

    cmd = [sys.executable, SCRIPT] + cmd_args + ['-c', currency]
    subprocess.run(cmd)
