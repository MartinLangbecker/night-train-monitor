"""Generate fillrate frames for all snapshots and assemble GIF animation."""
import json, glob, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime
from PIL import Image

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
CHART_DIR = os.path.join(PROJECT_DIR, "charts")
FRAME_DIR = os.path.join(CHART_DIR, "frames")
os.makedirs(FRAME_DIR, exist_ok=True)

SURCHARGE_SNAPS = {"20260803", "20260804", "20260810", "20260811"}
MAX_CAP = {"ECO": 108, "BUS": 54, "ECOSLEEPER": 20, "ECOSLEEPERLADY": 20}
LABELS = {"ECO": "Economy", "BUS": "Business", "ECOSLEEPER": "Sleeper", "ECOSLEEPERLADY": "Sleeper Lady"}
COLORS_T = {"ECO": "#2196F3", "BUS": "#FF9800", "ECOSLEEPER": "#9C27B0", "ECOSLEEPERLADY": "#E91E63"}

files = sorted(glob.glob(os.path.join(DATA_DIR, "*_weimar-bohumin-eur.json")))
files = [f for f in files if os.path.basename(f)[:8] not in SURCHARGE_SNAPS]

# Determine global date range (union of all snapshots)
all_dates = set()
for f in files:
    with open(f) as fh:
        d = json.load(fh)
    results = d.get("results", d)
    for k, v in results.items():
        if isinstance(v, dict) and "classes" in v:
            all_dates.add(k)
global_dates = sorted(all_dates)

print(f"Generating {len(files)} frames for {len(global_dates)} travel dates...")

frame_paths = []

for f in files:
    snap = os.path.basename(f)[:8]
    with open(f) as fh:
        d = json.load(fh)
    results = d.get("results", d)

    dates = []
    caps = {cls: [] for cls in MAX_CAP}
    available = {cls: [] for cls in MAX_CAP}

    for date_key in global_dates:
        val = results.get(date_key)
        dates.append(datetime.strptime(date_key, "%Y-%m-%d"))
        if not isinstance(val, dict) or "classes" not in val:
            for cls in MAX_CAP:
                caps[cls].append(0)
                available[cls].append(False)
            continue
        class_data = {c["class"]: c for c in val["classes"]}
        for cls in MAX_CAP:
            if cls in class_data:
                caps[cls].append(class_data[cls].get("capacity") or 0)
                available[cls].append(True)
            else:
                caps[cls].append(0)
                available[cls].append(False)

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    snap_display = f"{snap[:4]}-{snap[4:6]}-{snap[6:]}"
    fig.suptitle(f"Leo Express LE235 Weimar→Bohumín — Füllstand\nSnapshot: {snap_display}",
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
        ax.set_title(f"{LABELS[cls]} (max {max_c})", loc='left', fontsize=11,
                     fontweight='bold', color=COLORS_T[cls])
        ax.axhline(y=100, color='#333', linewidth=0.5, linestyle='--')
        ax.grid(True, alpha=0.2, axis='y')

        if cls in ("ECOSLEEPER", "ECOSLEEPERLADY"):
            for i, (f_val, pct, av) in enumerate(zip(free, fill_pct, avail)):
                if av and f_val > 0 and f_val <= 16:
                    ax.text(i, pct + 2, str(f_val), ha='center', va='bottom',
                            fontsize=6, color='#555')

    tick_positions = range(0, len(dates), 3)
    tick_labels = [dates[i].strftime("%d.%m.") for i in tick_positions]
    axes[-1].set_xticks(tick_positions)
    axes[-1].set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=7)
    axes[-1].set_xlabel("Reisetag")

    legend_elements = [
        mpatches.Patch(color="#4CAF50", label="< 40%"),
        mpatches.Patch(color="#FFC107", label="40–60%"),
        mpatches.Patch(color="#FF9800", label="60–80%"),
        mpatches.Patch(color="#F44336", label="> 80%"),
        mpatches.Patch(color="#BDBDBD", label="n/a"),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=5, fontsize=9,
               bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout(rect=[0, 0.03, 1, 0.94])
    frame_path = os.path.join(FRAME_DIR, f"frame_{snap}.png")
    plt.savefig(frame_path, dpi=100, bbox_inches='tight')
    plt.close()
    frame_paths.append(frame_path)
    print(f"  {snap_display}")

# Assemble GIF
print(f"\nAssembling GIF from {len(frame_paths)} frames (0.5s per frame)...")
frames = [Image.open(p) for p in frame_paths]
gif_path = os.path.join(CHART_DIR, "leo-fillrate-animation.gif")
frames[0].save(
    gif_path,
    save_all=True,
    append_images=frames[1:],
    duration=500,  # 0.5s per frame
    loop=0,
)
print(f"Saved: {gif_path}")
