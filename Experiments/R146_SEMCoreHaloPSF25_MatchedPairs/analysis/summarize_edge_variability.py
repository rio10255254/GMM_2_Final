"""Audit whether sharper R146 edges also fluctuate more across full scans."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
R143 = ROOT.parent / "R143_PSF25_MatchedPairs"
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def main() -> None:
    table = pd.read_csv(ROOT / "results/edge_response_r145_r146.csv")
    old = "R145-Center9PSF25-CorrectedPairs"
    new = "R146-SEMCoreHaloPSF25-MatchedPairs"
    arrays = {}
    results = {}
    for model in (old, new):
        group = table[table.model == model]
        values = group.pivot_table(index="run", columns=["index", "pillar_id"],
                                   values="edge_width_px").sort_index().to_numpy()
        assert values.shape == (30, 279)
        arrays[model] = values
        cell_sd = values.std(axis=0, ddof=1)
        results[model] = dict(circles=len(group), median_width_px=float(group.edge_width_px.median()),
                              mean_width_px=float(group.edge_width_px.mean()),
                              repeat_width_rms_px=float(np.sqrt(np.mean(cell_sd**2))),
                              median_cell_width_sd_px=float(np.median(cell_sd)),
                              mean_r50_px=float(group.r50_px.mean()),
                              median_contrast_gray=float(group.edge_contrast_gray.median()))
    old_sd = arrays[old].std(axis=0, ddof=1)
    new_sd = arrays[new].std(axis=0, ddof=1)
    raw_scan = (pd.read_csv(R143 / "results/stability_diagnosis/raw_edge_width.csv")
                .groupby("run_index").edge_width_px.mean().sort_index().to_numpy())
    assert len(raw_scan) == 30
    for model in (old, new):
        output_scan = (table[table.model == model].groupby("run_index")
                       .edge_width_px.mean().sort_index().to_numpy())
        results[model]["correlation_with_raw_scan_edge_width"] = float(np.corrcoef(raw_scan, output_scan)[0, 1])
        results[model]["output_width_change_per_raw_width_px"] = float(np.polyfit(raw_scan, output_scan, 1)[0])
        results[model]["first_five_scan_mean_width_px"] = float(output_scan[:5].mean())
        results[model]["last_five_scan_mean_width_px"] = float(output_scan[-5:].mean())
    scan_mean_shift = (arrays[new]-arrays[old]).mean(axis=1)
    rng = np.random.default_rng(146317)
    draw = rng.integers(0, 30, size=(2000, 30))
    old_boot = np.sqrt(np.mean(arrays[old][draw].var(axis=1, ddof=1), axis=1))
    new_boot = np.sqrt(np.mean(arrays[new][draw].var(axis=1, ddof=1), axis=1))
    result = dict(models=results, raw_first_five_scan_mean_width_px=float(raw_scan[:5].mean()),
                  raw_last_five_scan_mean_width_px=float(raw_scan[-5:].mean()),
                  R146_minus_R145=dict(mean_width_change_px=float(scan_mean_shift.mean()),
                                      width_change_scan_ci95_px=np.quantile(scan_mean_shift[draw].mean(axis=1),
                                                                            [.025, .975]).tolist(),
                                      repeat_width_rms_change_px=float(results[new]["repeat_width_rms_px"]-
                                                                        results[old]["repeat_width_rms_px"]),
                                      repeat_width_rms_scan_ci95_px=np.quantile(new_boot-old_boot,
                                                                                [.025, .975]).tolist(),
                                      fixed_position_pillar_cells_worse=int((new_sd>old_sd).sum()),
                                      fixed_position_pillar_cells=279,
                                      median_cell_sd_ratio=float(np.median(new_sd/old_sd))),
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/edge_variability_audit.json", result)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for model, label, color in ((old, "R145", "#579469"), (new, "R146", "#a33a77")):
        scan = table[table.model == model].groupby("run_index").edge_width_px.mean()
        axes[0].plot(scan.index, scan.to_numpy(), marker="o", ms=3, lw=1.5,
                     color=color, label=label)
    axes[0].set(xlabel="Complete scan", ylabel="Mean edge transition width (px)",
                title="Sharper mean edge")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=.25)
    axes[1].scatter(old_sd, new_sd, s=10, alpha=.55, color="#a33a77")
    extent=max(float(old_sd.max()),float(new_sd.max()))*1.05
    axes[1].plot([0,extent],[0,extent],ls="--",color="#6e7378",lw=1)
    axes[1].set(xlabel="R145 width SD at fixed circle (px)",
                ylabel="R146 width SD at fixed circle (px)",
                xlim=(0,extent),ylim=(0,extent),title="Less stable across 30 scans")
    axes[1].grid(alpha=.25)
    figure=ROOT / "reports/figures/edge_width_repeatability.png"
    figure.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(figure,dpi=180)
    plt.close(fig)
    print(result, flush=True)


if __name__ == "__main__":
    main()
