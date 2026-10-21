"""Compare old and corrected measured PSF spatial extent and transfer magnitude."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "R145_Center9PSF25_CorrectedPairs"
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def main() -> None:
    yy, xx = np.indices((101, 101))
    radius = np.hypot(xx-50, yy-50)
    ordered = np.argsort(radius.ravel())
    radius_sorted = radius.ravel()[ordered]
    radial_grid = np.linspace(0, 30, 301)
    fy = np.fft.fftfreq(400)[:, None]
    fx = np.fft.fftfreq(400)[None, :]
    frequency = np.hypot(fx, fy)
    bins = np.arange(0, .151, .005)
    centers = (bins[:-1]+bins[1:])/2
    curves = {}
    summary = {}
    for label, package in (("R145 disk fit", OLD), ("R146 SEM core-halo", ROOT)):
        bank_path = package / "calibration/measured_psf_bank.npz"
        with np.load(bank_path, allow_pickle=False) as z:
            kernels = z["all_kernels"].astype(np.float64)
        assert kernels.shape == (25, 101, 101)
        r50, r90, energy, mtf = [], [], [], []
        for kernel in kernels:
            cumulative = np.cumsum(kernel.ravel()[ordered])
            r50.append(float(radius_sorted[np.searchsorted(cumulative, .5)]))
            r90.append(float(radius_sorted[np.searchsorted(cumulative, .9)]))
            energy.append(np.interp(radial_grid, radius_sorted, cumulative))
            spectrum = np.abs(np.fft.fft2(kernel, s=(400, 400)))
            mtf.append([float(np.mean(spectrum[(frequency >= a) & (frequency < b)]))
                        for a, b in zip(bins[:-1], bins[1:])])
        curves[label] = dict(energy=np.mean(energy, axis=0), mtf=np.mean(mtf, axis=0))
        summary[label] = dict(bank_sha256=sha(bank_path), median_r50_px=float(np.median(r50)),
                              median_r90_px=float(np.median(r90)),
                              mtf_x_0p05_mean=float(np.mean([abs(np.fft.fft2(k, s=(400,400))[0,20]) for k in kernels])),
                              mtf_x_0p10_mean=float(np.mean([abs(np.fft.fft2(k, s=(400,400))[0,40]) for k in kernels])))
    out = ROOT / "results/deep_diagnosis"
    out.mkdir(parents=True, exist_ok=True)
    save(out / "bank_bandwidth_comparison.json", dict(summary=summary,
                                                      script_sha256=sha(Path(__file__)), completed_utc=now()))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for label, style in (("R145 disk fit", "#bf5b3e"), ("R146 SEM core-halo", "#235789")):
        axes[0].plot(radial_grid, curves[label]["energy"], label=label, lw=2, color=style)
        axes[1].plot(centers, curves[label]["mtf"], label=label, lw=2, color=style)
    axes[0].set(xlabel="Radius from kernel center (native px)", ylabel="Enclosed PSF energy",
                xlim=(0, 25), ylim=(0, 1.02), title="PSF spatial extent")
    axes[1].set(xlabel="Frequency (cycles / native px)", ylabel="Transfer magnitude",
                xlim=(0, .15), ylim=(0, 1.02), title="Image-detail transfer")
    for ax in axes:
        ax.grid(alpha=.25)
        ax.legend(frameon=False)
    figure = ROOT / "reports/figures/psf_bandwidth_comparison.png"
    figure.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure, dpi=180)
    plt.close(fig)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
