"""plot_centroid_distances_v2.py
Polished version of plot_centroid_distances.py — cleaner color, typography, layout.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.linewidth": 0.8,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#444",
})


SCRIPT_DIR = Path(__file__).resolve().parent
SETS = [
    {"name": "setA", "letter": "A", "subdir": "L0_repeat_fit"},
    {"name": "setB", "letter": "B", "subdir": "L0_repeat_fit_setB"},
    {"name": "setC", "letter": "C", "subdir": "L0_repeat_fit_setC"},
    {"name": "setD", "letter": "D", "subdir": "L0_repeat_fit_setD"},
]

HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "sage_terra",
    ["#8fa68a", "#b8c1a3", "#d4c8a8", "#d0a288", "#a86852", "#6b3e2e"],
)
WITHIN_COLOR = "#2a6f97"
ACROSS_COLOR = "#bc4749"


def load_centroid_15d(subdir: str) -> dict:
    with (SCRIPT_DIR / subdir / "outputs" / "deep_analysis.json").open("r", encoding="utf-8") as f:
        deep = json.load(f)
    centroids_zerf = deep["sec3_mode_separations"]["mode_centroids_per_coef_per_fov"]
    out = {}
    for mode_str, zf in centroids_zerf.items():
        zf_arr = np.array(zf)
        out[int(mode_str)] = zf_arr.mean(axis=1)
    return out


def align_modes(centroids_by_set: dict, ref_set: str) -> list:
    ref_modes = centroids_by_set[ref_set]
    ref_keys = list(ref_modes.keys())
    if ref_modes[ref_keys[0]][3] < ref_modes[ref_keys[1]][3]:
        ref_main_key = ref_keys[0]
    else:
        ref_main_key = ref_keys[1]
    ref_main_vec = ref_modes[ref_main_key]

    main_list, sec_list = [], []
    for s in SETS:
        modes = centroids_by_set[s["name"]]
        m_keys = list(modes.keys())
        d0 = np.linalg.norm(modes[m_keys[0]] - ref_main_vec)
        d1 = np.linalg.norm(modes[m_keys[1]] - ref_main_vec)
        if d0 < d1:
            main_list.append((f"{s['letter']}-main", modes[m_keys[0]]))
            sec_list.append((f"{s['letter']}-sec", modes[m_keys[1]]))
        else:
            main_list.append((f"{s['letter']}-main", modes[m_keys[1]]))
            sec_list.append((f"{s['letter']}-sec", modes[m_keys[0]]))
    return main_list + sec_list


def pairwise_distance_matrix(items: list) -> np.ndarray:
    n = len(items)
    M = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            M[i, j] = np.linalg.norm(items[i][1] - items[j][1])
    return M


def main() -> None:
    centroids_by_set = {s["name"]: load_centroid_15d(s["subdir"]) for s in SETS}
    items = align_modes(centroids_by_set, "setA")
    labels = [lab for lab, _ in items]
    D = pairwise_distance_matrix(items)

    main_idx = [0, 1, 2, 3]
    sec_idx = [4, 5, 6, 7]
    within = []
    for i, j in combinations(main_idx, 2):
        within.append(D[i, j])
    for i, j in combinations(sec_idx, 2):
        within.append(D[i, j])
    across = []
    for i in main_idx:
        for j in sec_idx:
            across.append(D[i, j])
    within = np.array(within)
    across = np.array(across)

    fig = plt.figure(figsize=(13, 5.4), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1], wspace=0.28)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    # ============ left: heatmap ============
    vmax = max(D.max(), 0.01)
    im = ax1.imshow(D, cmap=HEATMAP_CMAP, vmin=0, vmax=vmax, aspect="equal")
    for i in range(8):
        for j in range(8):
            v = D[i, j]
            txt_color = "white" if v > vmax * 0.62 else "#1a1a1a"
            ax1.text(j, i, f"{v:.2f}",
                     ha="center", va="center",
                     color=txt_color, fontsize=8.5)

    ax1.set_xticks(range(8))
    ax1.set_yticks(range(8))
    ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=9.5)
    ax1.set_yticklabels(labels, fontsize=9.5)

    # Subtle white block separators
    ax1.axhline(3.5, color="white", linewidth=2.2)
    ax1.axvline(3.5, color="white", linewidth=2.2)

    ax1.set_title("Pairwise distance between basin centroids",
                  loc="left", fontsize=12, pad=12,
                  fontweight="semibold")

    cbar = fig.colorbar(im, ax=ax1, shrink=0.78, pad=0.02)
    cbar.set_label("15-dim Euclidean distance", fontsize=10)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(width=0.6, length=3, labelsize=9)

    for spine in ax1.spines.values():
        spine.set_visible(False)
    ax1.tick_params(width=0.6, length=3)

    # ============ right: distribution ============
    rng = np.random.default_rng(0)
    x_within = rng.normal(0, 0.05, len(within))
    x_across = rng.normal(1, 0.05, len(across))

    # subtle box plots as background
    bp = ax2.boxplot([within, across], positions=[0, 1], widths=0.45,
                     patch_artist=True, showfliers=False, zorder=1)
    for patch, color in zip(bp["boxes"], [WITHIN_COLOR, ACROSS_COLOR]):
        patch.set_facecolor(color)
        patch.set_alpha(0.10)
        patch.set_edgecolor(color)
        patch.set_linewidth(0.9)
    for median in bp["medians"]:
        median.set_color("none")
    for whisker in bp["whiskers"]:
        whisker.set_color("#999")
        whisker.set_linewidth(0.7)
    for cap in bp["caps"]:
        cap.set_color("#999")
        cap.set_linewidth(0.7)

    ax2.scatter(x_within, within, s=58, color=WITHIN_COLOR,
                alpha=0.85, edgecolors="white", linewidths=0.9,
                zorder=3, label=f"within-basin (n={len(within)})")
    ax2.scatter(x_across, across, s=58, color=ACROSS_COLOR,
                alpha=0.85, edgecolors="white", linewidths=0.9,
                zorder=3, label=f"across-basin (n={len(across)})")

    ax2.hlines(within.mean(), -0.22, 0.22, color=WITHIN_COLOR,
               linewidth=2.0, zorder=4)
    ax2.hlines(across.mean(), 0.78, 1.22, color=ACROSS_COLOR,
               linewidth=2.0, zorder=4)
    ax2.text(0.27, within.mean(),
             f"mean {within.mean():.2f}",
             va="center", color=WITHIN_COLOR, fontsize=9.5)
    ax2.text(1.27, across.mean(),
             f"mean {across.mean():.2f}",
             va="center", color=ACROSS_COLOR, fontsize=9.5)

    ax2.set_xlim(-0.55, 1.75)
    ax2.set_ylim(-0.05, across.max() * 1.20)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["within-basin", "across-basin"], fontsize=10.5)
    ax2.set_ylabel("Centroid distance (15-dim)", fontsize=11)

    ratio = across.mean() / within.mean()
    ax2.annotate("",
                 xy=(1, across.mean()), xytext=(0, within.mean()),
                 arrowprops=dict(arrowstyle="-",
                                 color="#666", linewidth=0.8,
                                 linestyle=(0, (4, 3))))
    ax2.text(0.5, (across.mean() + within.mean()) / 2 + 0.025,
             f"{ratio:.1f}× separation",
             ha="center", va="bottom",
             fontsize=11, color="#222", fontweight="semibold")

    ax2.set_title("Within- vs across-basin distance",
                  loc="left", fontsize=12, pad=12,
                  fontweight="semibold")
    ax2.grid(axis="y", alpha=0.22, linestyle="-", linewidth=0.5)
    ax2.set_axisbelow(True)
    ax2.tick_params(width=0.6, length=3)

    plt.tight_layout()
    out = SCRIPT_DIR / "fig_centroid_distance_proof_v2.png"
    plt.savefig(out, dpi=220, bbox_inches="tight", facecolor="white")
    print(f"saved: {out}")
    print(f"within: mean={within.mean():.4f}, range=[{within.min():.4f}, {within.max():.4f}]")
    print(f"across: mean={across.mean():.4f}, range=[{across.min():.4f}, {across.max():.4f}]")
    print(f"ratio = {ratio:.2f}x")


if __name__ == "__main__":
    main()
