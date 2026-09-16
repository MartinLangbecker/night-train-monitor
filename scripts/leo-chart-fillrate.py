"""
Fillrate dashboard — shows 4 stacked class panels with color-coded fill bars.

Usage:
  python3 leo-chart-fillrate.py [ROUTE]

  ROUTE  bohumin | przemysl | frankfurt (default: bohumin)

Output: charts/leo-fillrate-{route}.png
"""
import json, glob, os, sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
CHART_DIR = os.path.join(PROJECT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)

SURCHARGE_SNAPS = {"20260803", "20260804", "20260810", "20260811"}

ROUTES = {
    "bohumin": "*_weimar-bohumin-eur.json",
    "przemysl": "*_weimar-przemysl-eur.json",
    "frankfurt": "*_weimar-frankfurt-eur.json",
}

route = sys.argv[1] if len(sys.argv) > 1 else "bohumin"
if route not in ROUTES:
    print(f"Unknown route '{route}'. Use: {', '.join(ROUTES.keys())}")
    sys.exit(1)

files = sorted(glob.glob(os.path.join(DATA_DIR, ROUTES[route])))
latest = None
for f in reversed(files):
    snap = os.path.basename(f)[:8]
    if snap not in SURCHARGE_SNAPS:
        latest = f
        break

snap_date = os.path.basename(latest)[:8]
with open(latest) as fh:
    d = json.load(fh)
results = d.get("results", d)

MAX_CAP = {"ECO": 108, "BUS": 54, "ECOSLEEPER": 20, "ECOSLEEPERLADY": 20}
LABELS = {"ECO": "Economy", "BUS": "Business", "ECOSLEEPER": "Sleeper", "ECOSLEEPERLADY": "Sleeper Lady"}
COLORS = {"ECO": "#2196F3", "BUS": "#FF9800", "ECOSLEEPER": "#9C27B0", "ECOSLEEPERLADY": "#E91E63"}

dates = []
caps = {cls: [] for cls in MAX_CAP}
available = {cls: [] for cls in MAX_CAP}

for date_key in sorted(results.keys()):
    val = results[date_key]
    if not isinstance(val, dict) or "classes" not in val:
        continue
    dates.append(datetime.strptime(date_key, "%Y-%m-%d"))
    class_data = {c["class"]: c for c in val["classes"]}
    for cls in MAX_CAP:
        if cls in class_data:
            caps[cls].append(class_data[cls].get("capacity") or 0)
            available[cls].append(True)
        else:
            caps[cls].append(0)
            available[cls].append(False)

fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
route_display = {"bohumin": "Bohumín", "przemysl": "Przemyśl", "frankfurt": "Frankfurt"}
fig.suptitle(f"Leo Express LE235 Weimar→{route_display[route]} — Füllstand pro Reisetag\n(Snapshot: {snap_date})",
             fontsize=13, fontweight='bold')

for ax_idx, cls in enumerate(["ECO", "BUS", "ECOSLEEPER", "ECOSLEEPERLADY"]):
    ax = axes[ax_idx]
    max_c = MAX_CAP[cls]
    free = np.array(caps[cls])
    avail = available[cls]
    sold = max_c - free
    fill_pct = sold / max_c * 100

    bar_colors = []
    display_pct = []
    for i, pct in enumerate(fill_pct):
        if not avail[i]:
            bar_colors.append("#BDBDBD")
            display_pct.append(5)
        elif pct >= 80:
            bar_colors.append("#F44336")
            display_pct.append(pct)
        elif pct >= 60:
            bar_colors.append("#FF9800")
            display_pct.append(pct)
        elif pct >= 40:
            bar_colors.append("#FFC107")
            display_pct.append(pct)
        else:
            bar_colors.append("#4CAF50")
            display_pct.append(pct)

    ax.bar(range(len(dates)), display_pct, color=bar_colors, width=0.8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_title(f"{LABELS[cls]} (max {max_c})", loc='left', fontsize=11, fontweight='bold',
                 color=COLORS[cls])
    ax.axhline(y=100, color='#333', linewidth=0.5, linestyle='--')
    ax.grid(True, alpha=0.2, axis='y')

    if cls in ("ECOSLEEPER", "ECOSLEEPERLADY"):
        for i, (f_val, pct, av) in enumerate(zip(free, fill_pct, avail)):
            if av and f_val > 0:
                ax.text(i, pct + 2, str(f_val), ha='center', va='bottom', fontsize=7, color='#555')

tick_positions = range(0, len(dates), 2)
tick_labels = [dates[i].strftime("%d.%m.") for i in tick_positions]
axes[-1].set_xticks(tick_positions)
axes[-1].set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=8)
axes[-1].set_xlabel("Reisetag")

legend_elements = [
    mpatches.Patch(color="#4CAF50", label="< 40% belegt"),
    mpatches.Patch(color="#FFC107", label="40–60% belegt"),
    mpatches.Patch(color="#FF9800", label="60–80% belegt"),
    mpatches.Patch(color="#F44336", label="> 80% belegt"),
    mpatches.Patch(color="#BDBDBD", label="nicht angeboten"),
]
fig.legend(handles=legend_elements, loc='lower center', ncol=5, fontsize=9,
           bbox_to_anchor=(0.5, -0.02))

plt.tight_layout(rect=[0, 0.03, 1, 0.94])
out = os.path.join(CHART_DIR, f"leo-fillrate-{route}.png")
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Saved: {out}")
