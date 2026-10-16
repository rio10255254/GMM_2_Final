"""Generate trend plots and sigma vs |b| scatter from sigma_b_table.csv.

Outputs:
- results/sigma_trend.png       (sigma_hat across 9 candidates, 3 scales)
- results/b_trend.png           (|b| across 9 candidates, 3 scales)
- results/sigma_vs_b_8px.png    (8px sigma_hat vs |b| scatter)
- results/sigma_vs_b_0p8px.png  (0.8px sigma_hat vs |b| scatter)
- results/sigma_vs_b_panel.png  (3-scale combined)
"""

from __future__ import annotations

import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path("D:/GMM_2_Final")
OUT = ROOT / "Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition/results"

# Candidate display order (chronological + role grouping)
ORDER = ["R30", "R33", "R38v2", "COMBO", "a030", "a025", "R40_a045", "R42_r41best", "R46"]
SCALES = ["8px", "0p8px", "0p08px"]
SCALE_LABELS = {"8px": "8 px", "0p8px": "0.8 px (main)", "0p08px": "0.08 px"}
SCALE_COLORS = {"8px": "#1f77b4", "0p8px": "#d62728", "0p08px": "#2ca02c"}


def load_table():
    rows = []
    with open(OUT / "sigma_b_table.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["status"] != "OK":
                continue
            r["sigma_hat"] = float(r["sigma_hat"])
            r["b"] = float(r["b"])
            r["abs_b"] = abs(r["b"])
            r["lag1"] = float(r["lag1_autocorr_centered"])
            r["n_outliers"] = int(r["n_outliers"])
            rows.append(r)
    return rows


def by_scale(rows, scale):
    return {r["tag"]: r for r in rows if r["scale"] == scale}


def plot_trend(rows, field, ylabel, fname, title):
    fig, ax = plt.subplots(figsize=(11, 4.5))
    x = np.arange(len(ORDER))
    for scale in SCALES:
        s_rows = by_scale(rows, scale)
        ys = [s_rows[tag][field] if tag in s_rows else np.nan for tag in ORDER]
        ax.plot(x, ys, marker="o", linewidth=2,
                color=SCALE_COLORS[scale], label=SCALE_LABELS[scale])
        # mark outlier-affected cells with hollow markers
        for i, tag in enumerate(ORDER):
            if tag in s_rows and s_rows[tag]["n_outliers"] > 0:
                ax.plot(i, ys[i], "o", markersize=12, markerfacecolor="none",
                        markeredgecolor=SCALE_COLORS[scale], markeredgewidth=2)
    ax.set_xticks(x)
    ax.set_xticklabels(ORDER, rotation=15)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", framealpha=0.9)
    # Add a separator between "formal lineage" and "later research candidates"
    ax.axvline(3.5, color="gray", linestyle="--", alpha=0.5)
    ax.text(1.5, ax.get_ylim()[1] * 0.95, "Formal lineage",
            ha="center", va="top", fontsize=9, color="gray")
    ax.text(6.5, ax.get_ylim()[1] * 0.95, "Later research candidates",
            ha="center", va="top", fontsize=9, color="gray")
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=150)
    plt.close(fig)
    print(f"wrote {fname}")


def plot_sigma_vs_b(rows, scale, fname):
    s_rows = by_scale(rows, scale)
    fig, ax = plt.subplots(figsize=(7, 6))

    # color by candidate group
    formal_lineage = {"R30", "R33", "R38v2", "COMBO"}
    later = set(ORDER) - formal_lineage
    for tag in ORDER:
        if tag not in s_rows:
            continue
        r = s_rows[tag]
        is_formal = tag in formal_lineage
        color = "#d62728" if tag == "COMBO" else ("#1f77b4" if is_formal else "#7f7f7f")
        size = 200 if tag == "COMBO" else 130
        marker = "o" if is_formal else "s"
        ax.scatter(r["sigma_hat"], r["abs_b"], s=size, c=color, marker=marker,
                   edgecolors="black", linewidths=1.5, zorder=3, alpha=0.85)
        # label
        ax.annotate(tag, (r["sigma_hat"], r["abs_b"]),
                    xytext=(7, 5), textcoords="offset points",
                    fontsize=10, fontweight="bold" if tag == "COMBO" else "normal")

    # Draw arrows along formal lineage
    formal_path = [(s_rows[t]["sigma_hat"], s_rows[t]["abs_b"]) for t in ["R30", "R33", "R38v2", "COMBO"] if t in s_rows]
    for i in range(len(formal_path) - 1):
        x0, y0 = formal_path[i]
        x1, y1 = formal_path[i + 1]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", color="#1f77b4", alpha=0.6, lw=1.5))

    ax.set_xlabel(r"$\hat{\sigma}$  (random component, lower is better)")
    ax.set_ylabel(r"$|b|$  (systematic offset, lower is better)")
    ax.set_title(f"σ̂ vs |b| at {SCALE_LABELS[scale]}\n"
                 f"Formal lineage (●): R30 → R33 → R38v2 → COMBO; Later candidates (■)")
    ax.grid(True, alpha=0.3)
    # ideal corner annotation
    ax.text(0.02, 0.97, "Ideal corner\n(both low)",
            transform=ax.transAxes, ha="left", va="top",
            fontsize=9, style="italic", color="green",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.7))
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=150)
    plt.close(fig)
    print(f"wrote {fname}")


def plot_panel(rows):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    formal_lineage = {"R30", "R33", "R38v2", "COMBO"}
    for ax, scale in zip(axes, SCALES):
        s_rows = by_scale(rows, scale)
        for tag in ORDER:
            if tag not in s_rows:
                continue
            r = s_rows[tag]
            is_formal = tag in formal_lineage
            color = "#d62728" if tag == "COMBO" else ("#1f77b4" if is_formal else "#7f7f7f")
            size = 180 if tag == "COMBO" else 110
            marker = "o" if is_formal else "s"
            ax.scatter(r["sigma_hat"], r["abs_b"], s=size, c=color, marker=marker,
                       edgecolors="black", linewidths=1.3, zorder=3, alpha=0.85)
            ax.annotate(tag, (r["sigma_hat"], r["abs_b"]),
                        xytext=(6, 4), textcoords="offset points", fontsize=9,
                        fontweight="bold" if tag == "COMBO" else "normal")
        formal_path = [(s_rows[t]["sigma_hat"], s_rows[t]["abs_b"]) for t in ["R30", "R33", "R38v2", "COMBO"] if t in s_rows]
        for i in range(len(formal_path) - 1):
            x0, y0 = formal_path[i]
            x1, y1 = formal_path[i + 1]
            ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                        arrowprops=dict(arrowstyle="->", color="#1f77b4", alpha=0.6, lw=1.3))
        ax.set_xlabel(r"$\hat{\sigma}$")
        ax.set_ylabel(r"$|b|$")
        ax.set_title(SCALE_LABELS[scale])
        ax.grid(True, alpha=0.3)
    fig.suptitle("Error type transformation spectrum: σ̂ (random) vs |b| (systematic) across candidates",
                 fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "sigma_vs_b_panel.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote sigma_vs_b_panel.png")


def main():
    rows = load_table()
    plot_trend(rows, "sigma_hat", r"$\hat{\sigma}$  (step std)",
               "sigma_trend.png",
               "σ̂ across 9 candidates × 3 scales (open marker = z-filtered outliers present)")
    plot_trend(rows, "abs_b", r"$|b|$  (|median step| − expected)",
               "b_trend.png",
               "|b| across 9 candidates × 3 scales")
    plot_sigma_vs_b(rows, "8px", "sigma_vs_b_8px.png")
    plot_sigma_vs_b(rows, "0p8px", "sigma_vs_b_0p8px.png")
    plot_sigma_vs_b(rows, "0p08px", "sigma_vs_b_0p08px.png")
    plot_panel(rows)


if __name__ == "__main__":
    main()
