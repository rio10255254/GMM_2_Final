"""Create compact scientific figures from completed R143 measurements."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load


def main() -> None:
    assert load(ROOT / "results/final_audit.json")["passed"]
    figures = ROOT / "reports/figures"
    figures.mkdir(exist_ok=True)
    run = ROOT / "runs/formal_8192"
    checkpoints = [0] + list(range(512, 8193, 512))
    losses = []
    for step in checkpoints:
        path = run / ("dev_initial.json" if step == 0 else f"dev_{step:05d}.json")
        losses.append(load(path)["mean_loss"])
    scans = pd.read_csv(ROOT / "results/comparison/scan_statistics.csv")
    scans = scans[scans.kind == "adjacent"]
    old = scans[scans.model == "R140v2-StableUNet"].set_index("run").mae_nm.sort_index()
    new = scans[scans.model == "R143-PSF25-MatchedPairs"].set_index("run").mae_nm.sort_index()
    assert old.index.equals(new.index) and len(new) == 30
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
    axes[0].plot(checkpoints, losses, marker="o", lw=2, color="#235789")
    axes[0].set(xlabel="Training update", ylabel="Mean held-out image loss",
                title="Held-out synthetic reconstruction")
    axes[0].grid(alpha=.25)
    x = np.arange(1, 31)
    axes[1].plot(x, old.to_numpy(), marker="o", ms=3, lw=1.5, label="R140v2")
    axes[1].plot(x, new.to_numpy(), marker="o", ms=3, lw=1.5, label="R143 matched PSF pairs")
    axes[1].set(xlabel="Complete scan", ylabel="Short-step PI MAE (nm)",
                title="Paired real-image comparison")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=.25)
    fig.savefig(figures / "training_and_short_step.png", dpi=170)
    plt.close(fig)
    summary = pd.read_csv(ROOT / "results/comparison/shape_size_summary.csv")
    sem = pd.read_csv(ROOT / "results/comparison/SEM_comparison.csv")
    methods = ["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet", "R143-PSF25-MatchedPairs"]
    shape = summary.set_index("model").loc[methods]
    bias = sem[sem.mapping_candidate == 1].set_index("model").loc[methods]
    labels = ["Raw", "R129", "R137", "R140v2", "R143"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), layout="constrained")
    color = ["#98a1a9", "#6883a4", "#3d75a4", "#284f82", "#bf5b3e"]
    for ax, values, title, unit in (
        (axes[0], shape.diameter_repeat_sd_nm, "Diameter repeatability", "nm"),
        (axes[1], shape.contour_repeat_sd_nm, "Contour repeatability", "nm"),
        (axes[2], bias.mean_diameter_difference_nm, "Mean diameter minus SEM", "nm"),
    ):
        ax.bar(labels, values.to_numpy(), color=color)
        ax.set(title=title, ylabel=unit)
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=.22)
    fig.savefig(figures / "size_contour_tradeoffs.png", dpi=170)
    plt.close(fig)
    print("FIGURES_SAVED", figures)


if __name__ == "__main__":
    main()
