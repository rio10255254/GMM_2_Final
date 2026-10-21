"""plot_4sets_basin_scatter.py
4 組 60 次擬合在 (Z5 失焦, Z13 球差) 平面上的散點圖。
顏色區分主/次解,形狀區分組,大星號標解的中心。

執行(在 d:/GMM_2_Final/ 跑):
  python PSF_Fitting/quick_recalibration/validation_experiments/plot_4sets_basin_scatter.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy.io as sio
from matplotlib.lines import Line2D


# 中文字體(Windows 上可用 Microsoft JhengHei)
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


SCRIPT_DIR = Path(__file__).resolve().parent
SETS = [
    {"name": "setA", "subdir": "L0_repeat_fit",      "marker": "o"},
    {"name": "setB", "subdir": "L0_repeat_fit_setB", "marker": "^"},
    {"name": "setC", "subdir": "L0_repeat_fit_setC", "marker": "s"},
    {"name": "setD", "subdir": "L0_repeat_fit_setD", "marker": "D"},
]

# 程式內部編號 x4 → OSA Z5 失焦,x12 → OSA Z13 球差
# tensor 是 0-indexed,所以 x4 對應 index 3、x12 對應 index 11
Z5_IDX = 3
Z13_IDX = 11


def load_set(subdir: str, n_trials: int = 15) -> dict:
    """讀一組:raw tensor (T, Z, F) + mode labels + 主 mode"""
    dj_path = SCRIPT_DIR / subdir / "outputs" / "deep_analysis.json"
    with dj_path.open("r", encoding="utf-8") as f:
        deep = json.load(f)

    tensors = []
    for trial_idx in range(1, n_trials + 1):
        mat_path = SCRIPT_DIR / subdir / "outputs" / f"trial_{trial_idx:02d}" / "PSF_fitted_2D_FOVstack.mat"
        data = sio.loadmat(str(mat_path), squeeze_me=False)
        coef = np.asarray(data["coef_grid"])
        if coef.ndim == 3:
            coef = coef[:, 0, :]
        tensors.append(coef)
    tensor = np.stack(tensors, axis=0)

    labels = deep["sec1_modes"]["labels"]
    probs = {int(k): v for k, v in deep["sec1_modes"]["mode_probabilities"].items()}
    main_mode = max(probs, key=probs.get)

    return {"tensor": tensor, "labels": labels, "main_mode": main_mode}


def main() -> None:
    print("讀取 4 組...")
    for s in SETS:
        loaded = load_set(s["subdir"])
        s.update(loaded)
        print(f"  {s['name']}: tensor {s['tensor'].shape}, main_mode={s['main_mode']}")

    fig, ax = plt.subplots(figsize=(9, 7))

    main_color = "#1f77b4"  # 藍
    sec_color = "#d62728"   # 紅

    # 60 個 trial,每個在 (Z5, Z13) 平面上一個點(跨 9 FOV 平均)
    for s in SETS:
        tensor = s["tensor"]
        labels = s["labels"]
        main_mode = s["main_mode"]
        marker = s["marker"]

        z5 = tensor[:, Z5_IDX, :].mean(axis=1)
        z13 = tensor[:, Z13_IDX, :].mean(axis=1)

        for t in range(len(labels)):
            is_main = labels[t] == main_mode
            color = main_color if is_main else sec_color
            ax.scatter(
                z5[t], z13[t],
                marker=marker, color=color, s=80,
                edgecolors="black", linewidths=0.6, alpha=0.75,
            )

    # 兩個解的中心點(用大星號)— 用 setA 的中心當代表(其他組對齊到同位置)
    setA = SETS[0]
    A_labels = np.array(setA["labels"])
    A_main_mask = A_labels == setA["main_mode"]
    z5_main_c = setA["tensor"][A_main_mask, Z5_IDX, :].mean()
    z13_main_c = setA["tensor"][A_main_mask, Z13_IDX, :].mean()
    z5_sec_c = setA["tensor"][~A_main_mask, Z5_IDX, :].mean()
    z13_sec_c = setA["tensor"][~A_main_mask, Z13_IDX, :].mean()

    ax.scatter(z5_main_c, z13_main_c, marker="*", color=main_color,
               s=600, edgecolors="black", linewidths=1.5, zorder=10)
    ax.scatter(z5_sec_c, z13_sec_c, marker="*", color=sec_color,
               s=600, edgecolors="black", linewidths=1.5, zorder=10)

    # 標解的位置
    ax.annotate(f"主解中心\n({z5_main_c:.2f}, {z13_main_c:.2f})",
                xy=(z5_main_c, z13_main_c), xytext=(z5_main_c - 0.05, z13_main_c + 0.05),
                fontsize=11, fontweight="bold", color=main_color)
    ax.annotate(f"次解中心\n({z5_sec_c:.2f}, {z13_sec_c:.2f})",
                xy=(z5_sec_c, z13_sec_c), xytext=(z5_sec_c + 0.02, z13_sec_c + 0.05),
                fontsize=11, fontweight="bold", color=sec_color)

    ax.set_xlabel("Z5 失焦(defocus)", fontsize=13)
    ax.set_ylabel("Z13 球差(spherical)", fontsize=13)
    ax.set_title("4 組共 60 次擬合在(失焦, 球差)平面的分佈\n"
                 "藍 = 主解,紅 = 次解,形狀區分組",
                 fontsize=14)
    ax.grid(alpha=0.3)

    # legend
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=main_color,
               markeredgecolor="black", markersize=11, label="主解(75% 機率)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=sec_color,
               markeredgecolor="black", markersize=11, label="次解(25% 機率)"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="gray",
               markeredgecolor="black", markersize=16, label="解的中心"),
    ]
    for s in SETS:
        legend_elements.append(
            Line2D([0], [0], marker=s["marker"], color="w", markerfacecolor="lightgray",
                   markeredgecolor="black", markersize=10, label=s["name"])
        )
    ax.legend(handles=legend_elements, loc="best", fontsize=10, framealpha=0.95)

    plt.tight_layout()
    out_path = SCRIPT_DIR / "fig_4sets_basin_scatter.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\n圖儲存到:{out_path}")


if __name__ == "__main__":
    main()
