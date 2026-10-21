"""Render 0.8 px step_std evolution chart for Q2 presentation."""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

BLUE = "#2E86AB"
GREEN = "#06A77D"
ORANGE = "#F18F01"
RED = "#D62828"
GREY = "#888888"

# baseline 演進主線(依時序)
baselines = [
    # (label, x, y, date, color)
    ("R18\n探索期\nbaseline", 1, 0.285, "pre-2/11", GREY),
    ("R25\n絕對中心", 3, 0.212, "3/16", BLUE),
    ("R26\n首個正式\nbaseline", 4, 0.191, "3/17", BLUE),
    ("R30\n多頭架構", 6, 0.168, "3/17-18", BLUE),
    ("COMBO\n當前正式\nbaseline", 12, 0.132, "4/8", GREEN),
]

# 失敗實驗
failures = [
    ("R27", 4.6, 0.196),
    ("R28", 5.0, 0.228),
    ("R29", 5.4, 0.217),
    ("R31", 7.0, 0.185),
    ("R32", 7.5, 0.332),
    ("R38", 10.0, 0.159),
]

# 核准替代方案
alternates = [
    ("R33\n核准替代\n(GMF極致)", 9, 0.119, ORANGE),
    ("R38v2\n核准替代\n(視覺優先)", 11, 0.134, ORANGE),
]

fig, ax = plt.subplots(figsize=(15, 8.5))

# --- 背景:前任 baseline 參考線 ---
ax.axhline(y=0.191, color=BLUE, linestyle=":", alpha=0.35, linewidth=1)
ax.axhline(y=0.168, color=BLUE, linestyle=":", alpha=0.35, linewidth=1)
ax.axhline(y=0.132, color=GREEN, linestyle=":", alpha=0.5, linewidth=1.2)

ax.text(13.3, 0.191, "R26 水位", color=BLUE, fontsize=11, alpha=0.75, va="center")
ax.text(13.3, 0.168, "R30 水位", color=BLUE, fontsize=11, alpha=0.75, va="center")
ax.text(13.3, 0.132, "COMBO 水位", color=GREEN, fontsize=12, alpha=0.95, va="center", fontweight="bold")

# --- 主線:baseline 演進 ---
x_bl = [b[1] for b in baselines]
y_bl = [b[2] for b in baselines]
ax.plot(x_bl, y_bl, "-", color=BLUE, linewidth=2.5, zorder=3, alpha=0.85)

for label, x, y, date, color in baselines:
    size = 280 if label.startswith("COMBO") else 180
    ax.scatter(x, y, s=size, c=color, edgecolors="white", linewidths=2.5, zorder=5)
    # 數值
    ax.annotate(
        f"{y:.3f}",
        (x, y),
        textcoords="offset points",
        xytext=(0, 14),
        ha="center",
        fontsize=13,
        fontweight="bold",
        color=color,
        zorder=6,
    )
    # 標籤 + 日期
    offset_y = -55 if label.startswith("COMBO") else -65
    ax.annotate(
        f"{label}\n({date})",
        (x, y),
        textcoords="offset points",
        xytext=(0, offset_y),
        ha="center",
        fontsize=11,
        color=color,
        zorder=6,
    )

# --- 失敗點(每個獨立調整位置避開重疊) ---
failure_label_offsets = {
    "R27": (13, -5, "left"),
    "R28": (13, 3, "left"),
    "R29": (13, -3, "left"),
    "R31": (13, 3, "left"),
    "R32": (14, 0, "left"),
    "R38": (13, 3, "left"),
}
for label, x, y in failures:
    ax.scatter(x, y, s=150, marker="x", c=RED, linewidths=3.2, zorder=4)
    dx, dy, ha = failure_label_offsets[label]
    if label == "R32":
        ax.annotate(
            f"{label}  {y:.3f}  (災難級失敗)",
            (x, y),
            textcoords="offset points",
            xytext=(dx, dy),
            ha=ha,
            va="center",
            fontsize=11,
            color=RED,
            fontweight="bold",
        )
    else:
        ax.annotate(
            f"{label}  {y:.3f}",
            (x, y),
            textcoords="offset points",
            xytext=(dx, dy),
            ha=ha,
            va="center",
            fontsize=11,
            color=RED,
        )

# --- 核准替代 ---
for label, x, y, color in alternates:
    ax.scatter(x, y, s=220, marker="D", c=color, edgecolors="white", linewidths=2, zorder=4)
    ax.annotate(
        f"{y:.3f}",
        (x, y),
        textcoords="offset points",
        xytext=(0, 14),
        ha="center",
        fontsize=13,
        fontweight="bold",
        color=color,
    )
    ax.annotate(
        label,
        (x, y),
        textcoords="offset points",
        xytext=(0, -60),
        ha="center",
        fontsize=11,
        color=color,
    )

# --- 改善幅度標示(置於最上方,不遮擋任何資料點或線) ---
ax.text(
    7.5,
    0.405,
    "R26 → COMBO   改善 -31%   (0.191 → 0.132)",
    color=GREEN,
    fontsize=17,
    fontweight="bold",
    ha="center",
    bbox=dict(boxstyle="round,pad=0.7", facecolor="white", edgecolor=GREEN, linewidth=2.2),
    zorder=7,
)

# --- 軸線與標題 ---
ax.set_xlabel("實驗時序 / Experiment timeline", fontsize=14, labelpad=10)
ax.set_ylabel("0.8 px 位移穩定度 step std  (越小越好)", fontsize=14, labelpad=10)
ax.set_title(
    "0.8 px 主戰場位移穩定度演進 / 0.8 px step std evolution\n2026-02-11 → 2026-04-15",
    fontsize=17,
    fontweight="bold",
    pad=15,
)

ax.set_xticks([])
ax.set_xlim(0, 15.5)
ax.set_ylim(0.08, 0.43)
ax.tick_params(axis="y", labelsize=12)
ax.grid(True, alpha=0.25, axis="y", linestyle="--")

# --- 圖例 ---
from matplotlib.lines import Line2D

legend_elements = [
    Line2D(
        [0],
        [0],
        marker="o",
        color=BLUE,
        markerfacecolor=BLUE,
        markersize=13,
        linewidth=3,
        label="Baseline 演進 / baseline progression",
    ),
    Line2D(
        [0],
        [0],
        marker="o",
        color="w",
        markerfacecolor=GREEN,
        markersize=15,
        label="當前正式 baseline / current formal",
    ),
    Line2D(
        [0],
        [0],
        marker="D",
        color="w",
        markerfacecolor=ORANGE,
        markersize=12,
        label="核准替代方案 / approved alternate",
    ),
    Line2D(
        [0],
        [0],
        marker="x",
        color=RED,
        markersize=13,
        linewidth=0,
        markeredgewidth=3,
        label="失敗/退步回合 / failed round",
    ),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=12, framealpha=0.95)

# --- 附註 ---
ax.text(
    0.5,
    -0.11,
    "備註:R34 / R35 / R37 / R33c 等其他失敗回合未列入圖中。數字為外部 GMF 新量測方法下的 raw step std。",
    transform=ax.transAxes,
    ha="center",
    va="top",
    fontsize=11,
    style="italic",
    color="gray",
)

plt.tight_layout()

output = r"d:\GMM_2_Final\docs\presentations_assets\2026_Q2\step_std_evolution.png"
plt.savefig(output, dpi=200, bbox_inches="tight", facecolor="white")
plt.close()
print(f"Saved: {output}")
