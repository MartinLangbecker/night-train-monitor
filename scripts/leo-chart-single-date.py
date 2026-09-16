"""
Single-date tier status chart — shows all 4 classes side by side with tier level,
price, and capacity for a given travel date.

Usage:
  python3 leo-chart-single-date.py [DATE] [ROUTE]

  DATE   Travel date in YYYY-MM-DD format (default: tomorrow)
  ROUTE  bohumin | przemysl | frankfurt (default: bohumin)

Output: charts/leo-single-date-{route}.png
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

# Parse args
target_date = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
route = sys.argv[2] if len(sys.argv) > 2 else "bohumin"

if route not in ROUTES:
    print(f"Unknown route '{route}'. Use: {', '.join(ROUTES.keys())}")
    sys.exit(1)

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

val = results.get(target_date)
if not val or "classes" not in val:
    print(f"No data for {target_date} in {route} snapshot {snap_date}")
    sys.exit(1)

class_data = {c["class"]: c for c in val["classes"]}

# Tier definitions per route
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
LABELS = {"ECO": "Economy", "BUS": "Business", "ECOSLEEPER": "Sleeper", "ECOSLEEPERLADY": "Sleeper Lady"}
TIER_COLORS = {
    "T1": "#4CAF50", "T2": "#8BC34A", "T3": "#FFC107",
    "T4": "#FF9800", "T5": "#F44336", "T6": "#B71C1C",
}
CLASS_ORDER = ["ECO", "BUS", "ECOSLEEPER", "ECOSLEEPERLADY"]

def get_tier_info(cls, price):
    tiers = TIERS_BY_ROUTE[route].get(cls, [])
    for tier_price, tier_label in tiers:
        if abs(price - tier_price) / tier_price < 0.10:
            return tier_label
    return "?"

fig, ax = plt.subplots(figsize=(10, 7))
x_positions = np.arange(len(CLASS_ORDER))
bar_width = 0.6
max_tier_count = max(len(TIERS_BY_ROUTE[route].get(cls, [])) for cls in CLASS_ORDER)

for i, cls in enumerate(CLASS_ORDER):
    if cls not in class_data:
        ax.bar(i, 0.3, bar_width, color='#E0E0E0', edgecolor='#999')
        ax.text(i, 0.5, "nicht\nangeboten", ha='center', va='bottom', fontsize=10, color='#999')
        continue

    price = class_data[cls].get("price")
    cap = class_data[cls].get("capacity") or 0
    max_c = MAX_CAP[cls]
    sold = max_c - cap
    fill_pct = sold / max_c * 100

    tier_label = get_tier_info(cls, price)
    tier_num = int(tier_label[1]) if tier_label != "?" else 0
    color = TIER_COLORS.get(tier_label, "#999")

    ax.bar(i, tier_num, bar_width, color=color, edgecolor='white', linewidth=1.5)
    ax.text(i, tier_num / 2, f"{price:.1f}€", ha='center', va='center',
            fontsize=16, fontweight='bold', color='white')
    ax.text(i, tier_num + 0.15, tier_label, ha='center', va='bottom',
            fontsize=14, fontweight='bold', color='#333')
    ax.text(i, -0.4, f"{cap}/{max_c} frei", ha='center', va='top', fontsize=11, color='#555')
    ax.text(i, -0.7, f"({fill_pct:.0f}% belegt)", ha='center', va='top', fontsize=9, color='#888')

ax.set_xticks(x_positions)
ax.set_xticklabels([LABELS[cls] for cls in CLASS_ORDER], fontsize=13, fontweight='bold')
ax.set_ylabel("Preisstufe", fontsize=12)
ax.set_yticks(range(0, max_tier_count + 2))
ylabels = ["—"] + [f"T{i}" for i in range(1, max_tier_count + 2)]
ylabels[1] = "T1\n(günstig)"
if max_tier_count >= 5:
    ylabels[5] = "T5\n(teuer)"
ax.set_yticklabels(ylabels[:max_tier_count + 2])
ax.set_ylim(-1, max_tier_count + 1.5)
ax.set_xlim(-0.5, len(CLASS_ORDER) - 0.5)
ax.grid(True, alpha=0.15, axis='y')
ax.axhline(y=0, color='#333', linewidth=0.5)

route_display = {"bohumin": "Bohumín", "przemysl": "Przemyśl", "frankfurt": "Frankfurt"}
ax.set_title(f"Leo Express LE235 Weimar→{route_display[route]} — {target_date}\n(Snapshot: {snap_date})",
             fontsize=14, fontweight='bold')

tier_patches = [mpatches.Patch(facecolor=TIER_COLORS[f"T{i}"], label=f"T{i}")
                for i in range(1, max_tier_count + 1)]
ax.legend(handles=tier_patches, loc='upper right', fontsize=9, title="Preisstufe")

plt.tight_layout()
out = os.path.join(CHART_DIR, f"leo-single-date-{route}.png")
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f"Saved: {out}")
