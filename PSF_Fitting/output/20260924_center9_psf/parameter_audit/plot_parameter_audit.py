"""Create fixed-scale scientific figures for the parameter audit."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)


def main():
    tuned = {r["case"]: r for r in json.loads((ROOT / "parameter_probe_summary.json").read_text(encoding="utf-8"))}
    confirmed = {r["model"]: r for r in json.loads((ROOT / "confirmation_summary.json").read_text(encoding="utf-8"))}
    labels = ["Original BADS", "Gain-profiled\n0.1 weight", "Intensity-only", "BADS restarts", "Gaussian"]
    tuned_keys = ["original", "profile_gain_0p1", "weight_0", "bads_restarts", None]
    confirmed_keys = ["confirm_original", "confirm_profile_gain_0p1", "confirm_weight_0", "confirm_bads_restarts", "gaussian"]
    gaussian_tuned = json.loads((RUN / "sem_shape_forward_validation" / "summary.json").read_text(encoding="utf-8"))["headline"]["gaussian_tuned_on_train6"]["mean_heldout3_mse"]
    left = [tuned[k]["mean_heldout_mse"] if k else gaussian_tuned for k in tuned_keys]
    right = [confirmed[k]["mean_heldout_mse"] for k in confirmed_keys]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, values, title in zip(axes, [left, right],
                                 ["Tuning: 3 frames, held-out SEM 36/29/22", "Confirmation: 5 new frames, SEM 34/30/23"]):
        colors = ["#708090", "#168a78", "#80b5a7", "#b58d61", "#885ead"]
        ax.bar(x, values, color=colors)
        ax.set_xticks(x, labels, rotation=20, ha="right", fontsize=8)
        ax.set_ylim(0, max(values) * 1.17)
        ax.set_ylabel("Mean held-out pixel MSE (lower is better)")
        ax.set_title(title, fontsize=10)
        for i, v in enumerate(values):
            ax.text(i, v + max(values) * .015, f"{v:.4f}", ha="center", va="bottom", fontsize=8)
        ax.grid(axis="y", alpha=.2)
    fig.savefig(OUT / "01_heldout_fit_comparison.png", dpi=180)
    plt.close(fig)

    accepted = loadmat(RUN / "PSF_20260924_center9_25_normalized.mat")["psf_grid"].reshape(101,101,25)
    candidate = loadmat(ROOT / "PSF_20260924_profile_gain_0p1_RESEARCH.mat")["psf_grid"].reshape(101,101,25)
    yy, xx = np.mgrid[:101,:101]
    offsets = {}
    for name, bank in (("Accepted PSF",accepted),("Research candidate",candidate)):
        offsets[name] = np.asarray([[np.sum((xx-50)*bank[:,:,i]),np.sum((yy-50)*bank[:,:,i])]
                                    for i in range(25)])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for name, pts in offsets.items():
        axes[0].plot(np.arange(1,26), pts[:,0], marker=".", label=name)
        axes[1].plot(np.arange(1,26), pts[:,1], marker=".", label=name)
    for ax, label in zip(axes, ["X centroid offset (pixels)", "Y centroid offset (pixels)"]):
        ax.axhline(0, color="black", lw=.8, alpha=.6)
        ax.set_xlabel("Camera view (1–25)")
        ax.set_ylabel(label)
        ax.set_xlim(1,25)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle("PSF energy-center offset: absolute position versus change across views", fontsize=11)
    fig.savefig(OUT / "02_psf_center_tradeoff.png", dpi=180)
    plt.close(fig)
    print(str(OUT))


if __name__=="__main__":main()
