"""
Weekly tier status chart — shows 4 classes side by side for 7 consecutive dates.

Usage:
  python3 leo-chart-week.py [START_DATE] [ROUTE]

  START_DATE  First date of the week in YYYY-MM-DD (default: today)
  ROUTE       bohumin | przemysl | frankfurt (default: bohumin)

Output: charts/leo-tier-week-{route}.png
"""
import json, glob, os, sys
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime, timedelta

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

start_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
route = sys.argv[2] if len(sys.argv) > 2 else "bohumin"

if route not in ROUTES:
    print(f"Unknown route '{route}'. Use: {', '.join(ROUTES.keys())}")
    sys.exit(1)

# Generate 7 dates
start = datetime.strptime(start_date, "%Y-%m-%d")
week_dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# Find latest non-surcharge snapshot
files = sorted(glob.glob(os.path.join(DATA_DIR, ROUTES[route])))
latest = None
for f in reversed(files):
    snap = os.path.basename(f)[:8]
    if snap not in SURCHARGE_SNAPS:
        latest = f
        break

if not latest:
    print("No non-surcharge snapshot found")
    sys.exit(1)

snap_date = os.path.basename(latest)[:8]
with open(latest) as fh:
    d = json.load(fh)
results = d.get("results", d)

# Tier definitions
TIERS_BY_ROUTE = {
    "bohumin": {
        "ECO": [(10.0, "T1"), (10.8, "T2"), (21.6, "T3"), (32.0, "T4"), (42.9, "T5"), (64.1, "T6")],
        "BUS": [(25.0, "T1"), (27.9, "T2"), (42.0, "T3"), (55.8, "T4"), (83.3, "T5")],
        "ECOSLEEPER": [(37.5, "T1"), (42.9, "T2"), (64.1, "T3"), (85.8, "T4"), (128.3, "T5")],
        "ECOSLEEPERLADY": [(37.5, "T1"), (42.9, "T2"), (64.1, "T3"), (85.8, "T4"), (128.3, "T5")],
    },
    "przemysl": {
        "ECO": [(34.5, "T1"), (51.6, "T2"), (68.7, "T3"), (102.9, "T4")],
        "BUS": [(25.0, "T1"), (44.5, "T2"), (67.0, "T3"), (89.1, "T4"), (133.7, "T5")],
        "ECOSLEEPER": [(37.5, "T1"), (68.7, "T2"), (102.9, "T3"), (137.0, "T4"), (205.8, "T5")],
        "ECOSLEEPERLADY": [(37.5, "T1"), (68.7, "T2"), (102.9, "T3"), (137.0, "T4"), (205.8, "T5")],
    },
    "frankfurt": {
        "ECO": [(10.0, "T1"), (13.3, "T2"), (17.9, "T3"), (27.9, "T4")],
        "BUS": [(25.0, "T1")],
        "ECOSLEEPER": [(37.5, "T1"), (52.9, "T2")],
        "ECOSLEEPERLADY": [(37.5, "T1"), (52.9, "T2")],
    },
}

MAX_CAP = {"ECO": 108, "BUS": 54, "ECOSLEEPER": 20, "ECOSLEEPERLADY": 20}
LABELS = {"ECO": "Eco", "BUS": "Bus", "ECOSLEEPER": "Slp", "ECOSLEEPERLADY": "Lady"}
TIER_COLORS = {
    "T1": "#4CAF50", "T2": "#8BC34A", "T3": "#FFC107",
    "T4": "#FF9800", "T5": "#F44336", "T6": "#B71C1C",
}
CLASS_ORDER = ["ECO", "BUS", "ECOSLEEPER", "ECOSLEEPERLADY"]
WEEKDAYS = {"0": "Mo", "1": "Di", "2": "Mi", "3": "Do", "4": "Fr", "5": "Sa", "6": "So"}

def get_tier_info(cls, price):
    tiers = TIERS_BY_ROUTE[route].get(cls, [])
    for tier_price, tier_label in tiers:
        if abs(price - tier_price) / tier_price < 0.10:
            return tier_label
    return "?"

max_tier_count = max(len(TIERS_BY_ROUTE[route].get(cls, [])) for cls in CLASS_ORDER)

fig, ax = plt.subplots(figsize=(14, 7))

n_dates = len(week_dates)
n_classes = len(CLASS_ORDER)
group_width = 0.8
bar_width = group_width / n_classes

for date_idx, date_key in enumerate(week_dates):
    val = results.get(date_key)
    if not val or "classes" not in val:
        continue
    class_map = {c["class"]: c for c in val["classes"]}

    for cls_idx, cls in enumerate(CLASS_ORDER):
        x = date_idx + (cls_idx - n_classes / 2 + 0.5) * bar_width

        if cls not in class_map:
            ax.bar(x, 0.2, bar_width * 0.9, color='#E0E0E0', edgecolor='#CCC', linewidth=0.5)
            continue

        price = class_map[cls].get("price")
        cap = class_map[cls].get("capacity") or 0
        max_c = MAX_CAP[cls]

        tier_label = get_tier_info(cls, price)
        tier_num = int(tier_label[1]) if tier_label != "?" else 0
        color = TIER_COLORS.get(tier_label, "#999")

        ax.bar(x, tier_num, bar_width * 0.9, color=color, edgecolor='white', linewidth=0.8)

        # Price inside bar
        if tier_num >= 2:
            ax.text(x, tier_num / 2, f"{price:.0f}€", ha='center', va='center',
                    fontsize=9, fontweight='bold', color='white')
        else:
            ax.text(x, tier_num + 0.1, f"{price:.0f}€", ha='center', va='bottom',
                    fontsize=8, color='#333')

        # Free count below bar
        ax.text(x, -0.25, f"{cap}", ha='center', va='top', fontsize=7, color='#888')

# X-axis: date + weekday
x_labels = []
for d in week_dates:
    dt = datetime.strptime(d, "%Y-%m-%d")
    wd = WEEKDAYS[str(dt.weekday())]
    x_labels.append(f"{wd}\n{d[5:]}")

ax.set_xticks(range(n_dates))
ax.set_xticklabels(x_labels, fontsize=10)
ax.set_ylabel("Preisstufe", fontsize=11)
ax.set_yticks(range(0, max_tier_count + 2))
ylabels = ["—"] + [f"T{i}" for i in range(1, max_tier_count + 2)]
ax.set_yticklabels(ylabels[:max_tier_count + 2])
ax.set_ylim(-0.6, max_tier_count + 1)
ax.grid(True, alpha=0.15, axis='y')
ax.axhline(y=0, color='#333', linewidth=0.5)

route_display = {"bohumin": "Bohumín", "przemysl": "Przemyśl", "frankfurt": "Frankfurt"}
ax.set_title(f"Leo Express LE235 Weimar→{route_display[route]} — Woche ab {start_date}\n"
             f"(Snapshot: {snap_date} | Zahlen unter Balken = freie Plätze)",
             fontsize=13, fontweight='bold')

# Legends
tier_patches = [mpatches.Patch(facecolor=TIER_COLORS[f"T{i}"], label=f"T{i}")
                for i in range(1, max_tier_count + 1)]
leg1 = ax.legend(handles=tier_patches, loc='upper right', fontsize=9, title="Preisstufe", ncol=max_tier_count)

class_patches = [mpatches.Patch(facecolor='#666', label=f"{LABELS[cls]}")
                 for cls in CLASS_ORDER]
ax.annotate("Pro Datum: Eco | Bus | Slp | Lady", xy=(0.01, 0.97),
            xycoords='axes fraction', fontsize=8, color='#666', va='top')

plt.tight_layout()
out = os.path.join(CHART_DIR, f"leo-tier-week-{route}.png")
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Saved: {out}")
