"""plot_centroid_distances.py
Quantitative evidence that all 4 sets see the same pair of basins.

(a) 8x8 Euclidean distance matrix of the 4 sets x 2 modes centroids
    (15-dim Zernike, averaged across 9 FOVs), rows/cols sorted by
    "main vs secondary" -> block-diagonal structure makes "same pair" visible.

(b) Distribution of within-basin distances vs across-basin distances.
    Within: 12 pairs (same-basin pairs across sets).
    Across: 16 pairs (main vs secondary across sets).
    The two distributions do not overlap -> same pair confirmed quantitatively.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11,
    "axes.linewidth": 1.0,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


SCRIPT_DIR = Path(__file__).resolve().parent
SETS = [
    {"name": "setA", "letter": "A", "subdir": "L0_repeat_fit"},
    {"name": "setB", "letter": "B", "subdir": "L0_repeat_fit_setB"},
    {"name": "setC", "letter": "C", "subdir": "L0_repeat_fit_setC"},
    {"name": "setD", "letter": "D", "subdir": "L0_repeat_fit_setD"},
]


def load_centroid_15d(subdir: str) -> dict:
    """Return {mode_id: 15-dim centroid (avg over 9 FOVs)}"""
    with (SCRIPT_DIR / subdir / "outputs" / "deep_analysis.json").open("r", encoding="utf-8") as f:
        deep = json.load(f)
    centroids_zerf = deep["sec3_mode_separations"]["mode_centroids_per_coef_per_fov"]
    out = {}
    for mode_str, zf in centroids_zerf.items():
        zf_arr = np.array(zf)
        out[int(mode_str)] = zf_arr.mean(axis=1)
    return out


def align_modes(centroids_by_set: dict, ref_set: str) -> list:
    """
    Returns ordered list of (label, vec) sorted as:
        A-main, B-main, C-main, D-main, A-sec, B-sec, C-sec, D-sec
    using nearest-centroid alignment to ref_set's main mode.
    """
    ref_modes = centroids_by_set[ref_set]
    # ref main = mode with smaller defocus (Z5 index 3)
    ref_keys = list(ref_modes.keys())
    if ref_modes[ref_keys[0]][3] < ref_modes[ref_keys[1]][3]:
        ref_main_key, ref_sec_key = ref_keys[0], ref_keys[1]
    else:
        ref_main_key, ref_sec_key = ref_keys[1], ref_keys[0]
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

    # split distances: within-basin vs across-basin
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

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.8),
                                    gridspec_kw={"width_ratios": [1.15, 1]})

    # --- (a) 8x8 distance matrix ---
    vmax = max(D.max(), 0.01)
    im = ax1.imshow(D, cmap="magma_r", vmin=0, vmax=vmax, aspect="equal")
    for i in range(8):
        for j in range(8):
            v = D[i, j]
            txt_color = "white" if v > vmax * 0.55 else "black"
            ax1.text(j, i, f"{v:.2f}", ha="center", va="center",
                     color=txt_color, fontsize=9)
    ax1.set_xticks(range(8))
    ax1.set_yticks(range(8))
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.set_yticklabels(labels)
    # block boundary
    ax1.axhline(3.5, color="#e63946", linewidth=2.5)
    ax1.axvline(3.5, color="#e63946", linewidth=2.5)
    ax1.set_title("(a) Pairwise Euclidean distance matrix",
                  loc="left", fontweight="bold", pad=10)
    fig.colorbar(im, ax=ax1, shrink=0.75, label="distance (15-dim)")

    # --- (b) within vs across distribution ---
    rng = np.random.default_rng(0)
    x_within = rng.normal(0, 0.06, len(within))
    x_across = rng.normal(1, 0.06, len(across))

    ax2.scatter(x_within, within, s=70, color="#1f77b4",
                alpha=0.75, edgecolors="black", linewidths=0.6,
                label=f"within-basin  (n={len(within)})")
    ax2.scatter(x_across, across, s=70, color="#d62728",
                alpha=0.75, edgecolors="black", linewidths=0.6,
                label=f"across-basin  (n={len(across)})")

    # mean lines
    ax2.hlines(within.mean(), -0.25, 0.25, color="#1f77b4",
               linewidth=2.5, zorder=3)
    ax2.hlines(across.mean(), 0.75, 1.25, color="#d62728",
               linewidth=2.5, zorder=3)
    ax2.text(0.30, within.mean(),
             f"mean = {within.mean():.2f}",
             va="center", color="#1f77b4", fontsize=10)
    ax2.text(1.30, across.mean(),
             f"mean = {across.mean():.2f}",
             va="center", color="#d62728", fontsize=10)

    ax2.set_xlim(-0.5, 1.7)
    ax2.set_ylim(-0.1, across.max() * 1.15)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["within-basin", "across-basin"])
    ax2.set_ylabel("Centroid distance (15-dim Euclidean)")
    ax2.set_title("(b) Distance distributions",
                  loc="left", fontweight="bold", pad=20)
    ax2.grid(axis="y", alpha=0.3)
    # ratio annotation
    ratio = across.mean() / within.mean()
    ax2.text(0.5, across.max() * 1.05,
             f"across / within = {ratio:.1f}×",
             ha="center", fontsize=11, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#fffbe7",
                       edgecolor="#c0a000", linewidth=1.0))

    plt.tight_layout()
    out = SCRIPT_DIR / "fig_centroid_distance_proof.png"
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"saved: {out}")
    print(f"\nwithin-basin distance:  mean = {within.mean():.4f}, "
          f"range = [{within.min():.4f}, {within.max():.4f}]")
    print(f"across-basin distance:  mean = {across.mean():.4f}, "
          f"range = [{across.min():.4f}, {across.max():.4f}]")
    print(f"ratio (across/within):  {ratio:.1f}x")


if __name__ == "__main__":
    main()
