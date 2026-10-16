"""plot_basin_alignment.py
Cross-set mode alignment, before vs. after.

Each set is shown as a labelled disc (A / B / C / D) instead of distinct shapes.
All discs are vertically staggered to avoid any overlap.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.linewidth": 1.0,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "legend.fontsize": 10,
    "legend.frameon": True,
    "legend.framealpha": 1.0,
    "legend.edgecolor": "#bbbbbb",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


SCRIPT_DIR = Path(__file__).resolve().parent
# vertical Y level for each set (relative offset on top of basin bottom).
# Spacing >= 0.12 ensures discs at marker size 700 never overlap.
SETS = [
    {"name": "setA", "letter": "A", "subdir": "L0_repeat_fit",      "y_offset": 0.18},
    {"name": "setB", "letter": "B", "subdir": "L0_repeat_fit_setB", "y_offset": 0.34},
    {"name": "setC", "letter": "C", "subdir": "L0_repeat_fit_setC", "y_offset": 0.50},
    {"name": "setD", "letter": "D", "subdir": "L0_repeat_fit_setD", "y_offset": 0.66},
]

Z5_INDEX = 3  # internal x4 -> OSA Z5 defocus

COLOR_MODE1 = "#1f77b4"
COLOR_MODE2 = "#d62728"


def load_mode_centroids(subdir: str) -> dict:
    with (SCRIPT_DIR / subdir / "outputs" / "deep_analysis.json").open("r", encoding="utf-8") as f:
        deep = json.load(f)
    centroids_zerf = deep["sec3_mode_separations"]["mode_centroids_per_coef_per_fov"]
    out = {}
    for mode_str, zf in centroids_zerf.items():
        out[int(mode_str)] = float(np.array(zf)[Z5_INDEX].mean())
    return out


def landscape(x: np.ndarray) -> np.ndarray:
    """double-well, both basins at the same depth"""
    b1 = -1.0 * np.exp(-((x - 0.15) / 0.10) ** 2)
    b2 = -1.0 * np.exp(-((x - 0.78) / 0.18) ** 2)
    return b1 + b2 + 1.6


def draw_panel(ax, sets_data, mode: str, label: str):
    x = np.linspace(-0.05, 1.10, 600)
    y = landscape(x)
    ax.plot(x, y, color="#222", linewidth=1.4, zorder=2)

    bottom_left = landscape(np.array([0.15]))[0]
    bottom_right = landscape(np.array([0.78]))[0]

    for s in sets_data:
        for mode_id, z5 in s["centroids"].items():
            in_left = z5 < 0.4
            if mode == "raw":
                color = COLOR_MODE1 if mode_id == 1 else COLOR_MODE2
            else:
                color = COLOR_MODE1 if in_left else COLOR_MODE2

            base_y = bottom_left if in_left else bottom_right
            y_pos = base_y + s["y_offset"]

            ax.scatter(z5, y_pos, s=700, color=color,
                       edgecolors="black", linewidths=1.2, zorder=5)
            ax.text(z5, y_pos, s["letter"],
                    ha="center", va="center",
                    color="white", fontweight="bold", fontsize=12, zorder=6)

    ax.set_xlim(-0.05, 1.10)
    ax.set_ylim(bottom_left - 0.05, y.max() + 0.05)
    ax.set_xlabel("Defocus coefficient (Z5)")
    ax.set_yticks([])
    ax.set_title(label, loc="left", fontweight="bold", pad=10)


def main() -> None:
    sets_data = [
        {**s, "centroids": load_mode_centroids(s["subdir"])} for s in SETS
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)

    draw_panel(axes[0], sets_data, mode="raw",
               label="(a) Before alignment  —  raw cluster labels")
    draw_panel(axes[1], sets_data, mode="aligned",
               label="(b) After alignment  —  nearest-centroid to setA")

    axes[0].set_ylabel("Loss  (conceptual)")

    legend_a = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_MODE1,
               markeredgecolor="black", markersize=10, label="mode 1"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_MODE2,
               markeredgecolor="black", markersize=10, label="mode 2"),
    ]
    legend_b = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_MODE1,
               markeredgecolor="black", markersize=10, label="main basin"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_MODE2,
               markeredgecolor="black", markersize=10, label="secondary basin"),
    ]
    axes[0].legend(handles=legend_a, loc="upper center", ncol=2)
    axes[1].legend(handles=legend_b, loc="upper center", ncol=2)

    plt.tight_layout()
    out = SCRIPT_DIR / "fig_basin_alignment.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
