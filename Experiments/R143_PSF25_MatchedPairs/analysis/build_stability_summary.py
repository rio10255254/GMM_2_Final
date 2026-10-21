"""Assemble the R143 stability diagnosis from frozen outputs and probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/stability_diagnosis"
sys.path.insert(0, str(ROOT))
from utils import now, save, sha


def read(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def boot_mean(values: np.ndarray, seed: int, draws: int = 10000) -> list[float]:
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(values), size=(draws, len(values)))
    return [float(x) for x in np.quantile(values[pick].mean(1), [.025, .975])]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    figdir = ROOT / "reports/figures"
    figdir.mkdir(exist_ok=True)
    d = pd.read_csv(ROOT / "results/comparison/all_displacements.csv")
    c = pd.read_csv(ROOT / "results/comparison/all_circles.csv")
    adjacent = d[d.kind == "adjacent"].pivot(index=["run", "j"], columns="model", values="error_nm").sort_index()
    old_error = adjacent["R140v2-StableUNet"]
    new_error = adjacent["R143-PSF25-MatchedPairs"]
    by_step = pd.DataFrame(dict(old_sd=old_error.groupby(level="j").std(ddof=1),
                                new_sd=new_error.groupby(level="j").std(ddof=1)))
    scan_penalty = (new_error.abs()-old_error.abs()).groupby(level="run").mean()
    old = c[c.model == "R140v2-StableUNet"].set_index(["run", "index", "pillar_id"]).sort_index()
    new = c[c.model == "R143-PSF25-MatchedPairs"].set_index(["run", "index", "pillar_id"]).sort_index()
    raw = c[c.model == "Raw"].set_index(["run", "index", "pillar_id"]).sort_index()
    assert len(old) == len(new) == len(raw) == 8370
    axis = np.asarray([-0.9998766245119538, .015707824629190823])
    dxdy_raw = new[["center_x_px", "center_y_px"]]-raw[["center_x_px", "center_y_px"]]
    dxdy_old = old[["center_x_px", "center_y_px"]]-raw[["center_x_px", "center_y_px"]]
    by_run_shift = dxdy_raw.groupby(level="run").mean()
    shift_ci = [boot_mean(by_run_shift[col].to_numpy(), 143365+i) for i, col in enumerate(by_run_shift)]
    with np.load(ROOT / "calibration/measured_psf_bank.npz", allow_pickle=False) as z:
        kernels = z["all_kernels"].astype(np.float64)
    kernels /= kernels.sum((1,2), keepdims=True)
    yy, xx = np.mgrid[:101,:101]
    psf_centroid = [float(((kernels*xx).sum((1,2))-50).mean()),
                    float(((kernels*yy).sum((1,2))-50).mean())]
    along_shift = ((new[["center_x_px", "center_y_px"]]-old[["center_x_px", "center_y_px"]]).to_numpy()@axis)*172.5
    run_center_shift = pd.Series(along_shift, index=old.index).groupby(level="run").mean()
    diameter_shift = new.diameter_nm-old.diameter_nm
    run_diameter_shift = diameter_shift.groupby(level="run").mean()
    raw_edge = pd.read_csv(OUT / "raw_edge_width.csv").set_index(["run", "index", "pillar_id"]).sort_index()
    old_edge = pd.read_csv(OUT / "output_edge_width_r140.csv").set_index(["run", "index", "pillar_id"]).sort_index()
    new_edge = pd.read_csv(OUT / "output_edge_width_r143.csv").set_index(["run", "index", "pillar_id"]).sort_index()
    raw_photometry = pd.read_csv(OUT / "raw_photometry.csv").set_index(["run", "index"]).sort_index()
    old_width_sd = old_edge.groupby(level=["index", "pillar_id"]).edge_width_px.std(ddof=1)
    new_width_sd = new_edge.groupby(level=["index", "pillar_id"]).edge_width_px.std(ddof=1)
    old_r50_sd = old_edge.groupby(level=["index", "pillar_id"]).r50_px.std(ddof=1)
    new_r50_sd = new_edge.groupby(level=["index", "pillar_id"]).r50_px.std(ddof=1)
    run_raw_width = raw_edge.groupby(level="run").edge_width_px.mean()
    run_raw_contrast = raw_photometry.groupby(level="run").contrast_gray.mean()
    npair = {}
    a = read("noise_probe_broad_r140.json")["pairs"]
    b = read("noise_probe_broad_r143.json")["pairs"]
    noise_old = np.array([v["noise_induced_sd_nm"] for v in a])
    noise_new = np.array([v["noise_induced_sd_nm"] for v in b])
    noise_frame = pd.DataFrame(dict(run=[v["run"] for v in a], delta=noise_new-noise_old))
    noise_run = noise_frame.groupby("run").delta.mean().to_numpy()
    npair.update(pairs=len(a), old_mean_nm=float(noise_old.mean()),
                 new_mean_nm=float(noise_new.mean()),
                 worse_pairs=int((noise_new>noise_old).sum()),
                 run_cluster_mean_difference_nm=float(noise_run.mean()),
                 run_cluster_ci95_nm=boot_mean(noise_run,143999))
    subpixel = {}
    aa = pd.DataFrame(read("subpixel_fourier_broad_r140.json")["rows"])
    bb = pd.DataFrame(read("subpixel_fourier_broad_r143.json")["rows"])
    aa = aa[aa.shift_x_px.isin([.25,.5,.75])]
    bb = bb[bb.shift_x_px.isin([.25,.5,.75])]
    frame_rms = []
    for frame in sorted(aa.frame_no.unique()):
        va = aa[aa.frame_no == frame]
        vb = bb[bb.frame_no == frame]
        frame_rms.append(dict(frame=int(frame), run=va.run.iloc[0],
                              old=float(np.sqrt(np.mean(va.model_shift_error_nm**2))),
                              new=float(np.sqrt(np.mean(vb.model_shift_error_nm**2)))))
    frame_table = pd.DataFrame(frame_rms)
    run_phase_delta = frame_table.assign(delta=frame_table.new-frame_table.old).groupby("run").delta.mean().to_numpy()
    cubic_old = pd.DataFrame(read("subpixel_cubic_r140.json")["rows"])
    cubic_new = pd.DataFrame(read("subpixel_cubic_r143.json")["rows"])
    cubic_old = cubic_old[cubic_old.shift_x_px.isin([.2,.4,.6,.8])]
    cubic_new = cubic_new[cubic_new.shift_x_px.isin([.2,.4,.6,.8])]
    subpixel.update(frames=len(frame_table), fractional_shifts=len(aa),
                    fourier_rms_old_nm=float(np.sqrt(np.mean(aa.model_shift_error_nm**2))),
                    fourier_rms_new_nm=float(np.sqrt(np.mean(bb.model_shift_error_nm**2))),
                    fourier_worse_frames=int((frame_table.new>frame_table.old).sum()),
                    fourier_run_cluster_mean_rms_penalty_nm=float(run_phase_delta.mean()),
                    fourier_run_cluster_ci95_nm=boot_mean(run_phase_delta,143998),
                    cubic_three_frame_rms_old_nm=float(np.sqrt(np.mean(cubic_old.model_shift_error_nm**2))),
                    cubic_three_frame_rms_new_nm=float(np.sqrt(np.mean(cubic_new.model_shift_error_nm**2))),
                    warning="subpixel diagnostic ranking changes under cubic interpolation")
    blur_old = pd.DataFrame(read("blur_edge_probe_r140.json")["rows"])
    blur_new = pd.DataFrame(read("blur_edge_probe_r143.json")["rows"])
    blur_results = []
    for first in (0,12):
        x = blur_old[blur_old.frame_pair.apply(lambda q:q[0] == first)].sort_values("level")
        y = blur_new[blur_new.frame_pair.apply(lambda q:q[0] == first)].sort_values("level")
        blur_results.append(dict(frame_pair_start=first,
                                 raw_width_change_px=float(x.raw_edge_width_px.iloc[-1]-x.raw_edge_width_px.iloc[0]),
                                 old_output_width_change_px=float(x.output_edge_width_px.iloc[-1]-x.output_edge_width_px.iloc[0]),
                                 new_output_width_change_px=float(y.output_edge_width_px.iloc[-1]-y.output_edge_width_px.iloc[0]),
                                 old_diameter_change_nm=float(x.diameter_mean_nm.iloc[-1]-x.diameter_mean_nm.iloc[0]),
                                 new_diameter_change_nm=float(y.diameter_mean_nm.iloc[-1]-y.diameter_mean_nm.iloc[0])))
    sem = pd.read_csv(ROOT / "results/comparison/SEM_comparison.csv")
    sem = sem[sem.mapping_candidate == 1].set_index("model")
    gap_raw = float(sem.loc["Raw", "mean_diameter_difference_nm"])
    gap_new = float(sem.loc["R143-PSF25-MatchedPairs", "mean_diameter_difference_nm"])
    size_shift = json.loads((ROOT / "results/diameter_shift_paired.json").read_text(encoding="utf-8"))["Raw"]
    mapping = json.loads((ROOT / "evaluation/sem_mapping_candidates.json").read_text(encoding="utf-8"))
    scale = json.loads((ROOT / "evaluation/sem_scale.json").read_text(encoding="utf-8"))["scale_nm_per_px"]
    sem_truth = {}
    with np.load(ROOT / "evaluation/sem_points.npz", allow_pickle=False) as z:
        for pid in sorted(set(mapping[0]["sem_ids_by_new_nine"])):
            points = z[f"SEM_{pid}"]
            centered = points-points.mean(0)
            def residual(center):
                radius = np.linalg.norm(centered-center, axis=1)
                return radius-radius.mean()
            center = least_squares(residual, [0,0], xtol=1e-12, ftol=1e-12, gtol=1e-12).x
            sem_truth[pid] = float(2*np.linalg.norm(centered-center,axis=1).mean()*scale)
    optical_by_pillar = {name: c[c.model == name].groupby("pillar_id").diameter_nm.mean().sort_index().to_numpy()
                         for name in ("Raw", "R140v2-StableUNet", "R143-PSF25-MatchedPairs")}
    sem_rows = []
    sem_closer_counts = {}
    for i, candidate in enumerate(mapping,1):
        truth = np.array([sem_truth[pid] for pid in candidate["sem_ids_by_new_nine"]])
        raw_err = optical_by_pillar["Raw"]-truth
        old_err = optical_by_pillar["R140v2-StableUNet"]-truth
        new_err = optical_by_pillar["R143-PSF25-MatchedPairs"]-truth
        sem_closer_counts[str(i)] = dict(vs_raw=int((np.abs(new_err)<np.abs(raw_err)).sum()),
                                         vs_r140=int((np.abs(new_err)<np.abs(old_err)).sum()),
                                         all_r143_still_oversize=bool((new_err>0).all()))
        for pillar, pid in enumerate(candidate["sem_ids_by_new_nine"],1):
            sem_rows.append(dict(mapping_candidate=i,pillar_id=pillar,sem_id=pid,sem_diameter_nm=truth[pillar-1],
                                 raw_diameter_nm=optical_by_pillar["Raw"][pillar-1],
                                 r140_diameter_nm=optical_by_pillar["R140v2-StableUNet"][pillar-1],
                                 r143_diameter_nm=optical_by_pillar["R143-PSF25-MatchedPairs"][pillar-1],
                                 raw_error_nm=raw_err[pillar-1],r140_error_nm=old_err[pillar-1],
                                 r143_error_nm=new_err[pillar-1]))
    pd.DataFrame(sem_rows).to_csv(OUT / "sem_pillar_comparison.csv",index=False)
    branch = json.loads((ROOT / "results/real_psf_effect.json").read_text(encoding="utf-8"))["frames"]
    summary = dict(
        created_utc=now(),
        sources=dict(bank_sha256=sha(ROOT / "calibration/measured_psf_bank.npz"),
                     checkpoint_sha256=sha(ROOT / "runs/formal_8192/checkpoints/step08192.pth")),
        displacement=dict(old_adjacent_mae_nm=float(old_error.abs().mean()),
                          new_adjacent_mae_nm=float(new_error.abs().mean()),
                          old_repeatability_nm=float(by_step.old_sd.mean()),
                          new_repeatability_nm=float(by_step.new_sd.mean()),
                          positions_worse_sd=int((by_step.new_sd>by_step.old_sd).sum()),
                          scans_worse_mae=int((scan_penalty>0).sum()),
                          extra_error_mean_nm=float((new_error-old_error).mean()),
                          extra_error_sd_nm=float((new_error-old_error).std(ddof=1))),
        psf_center=dict(mean_xy_px=psf_centroid,
                        expected_inverse_xy_px=[-q for q in psf_centroid],
                        r143_minus_raw_mean_xy_px=[float(v) for v in by_run_shift.mean()],
                        r143_minus_raw_ci95_xy_px=shift_ci,
                        r140_minus_raw_mean_xy_px=[float(v) for v in dxdy_old.mean()],
                        inference="alignment supports learning the inverse offset but constant offset cancels in adjacent displacement"),
        edge=dict(raw_mean_width_px=float(raw_edge.edge_width_px.mean()),
                  old_mean_width_px=float(old_edge.edge_width_px.mean()),
                  new_mean_width_px=float(new_edge.edge_width_px.mean()),
                  old_width_repeat_sd_px=float(old_width_sd.mean()),
                  new_width_repeat_sd_px=float(new_width_sd.mean()),
                  width_groups_worse=int((new_width_sd>old_width_sd).sum()),
                  old_r50_repeat_sd_px=float(old_r50_sd.mean()),
                  new_r50_repeat_sd_px=float(new_r50_sd.mean()),
                  r50_groups_worse=int((new_r50_sd>old_r50_sd).sum()),
                  run_raw_width_center_shift_corr=float(run_raw_width.corr(run_center_shift)),
                  run_raw_width_diameter_shift_corr=float(run_raw_width.corr(run_diameter_shift)),
                  run_contrast_diameter_shift_corr=float(run_raw_contrast.corr(run_diameter_shift)),
                  controlled_broad_blur=blur_results),
        sensor_noise=npair,
        subpixel=subpixel,
        optical_branch=dict(real_frames=len(branch),
                            max_on_off_center_rms_nm=float(max(x["on_off_center_rms_nm"] for x in branch)),
                            max_candidate_0_vs_24_center_rms_nm=float(max(x["psf0_psf24_center_rms_nm"] for x in branch))),
        sem_comparison=dict(raw_gap_nm=gap_raw, r143_gap_nm=gap_new,
                            reduction_nm=gap_raw-gap_new,
                            reduction_percent=100*(gap_raw-gap_new)/gap_raw,
                            r143_minus_raw_diameter_mean_nm=size_shift["mean_nm"],
                            r143_minus_raw_scan_ci95_nm=size_shift["ci95_nm"],
                            r143_smaller_scans=size_shift["lower_count"],
                            per_pillar_closer_counts=sem_closer_counts,
                            independence_unproven=True),
    )
    save(OUT / "summary.json", summary)
    by_step.reset_index().to_csv(OUT / "repeatability_by_step.csv", index=False)
    frame_table.to_csv(OUT / "subpixel_fourier_by_frame.csv", index=False)
    fig, axs = plt.subplots(1,3,figsize=(13,4),layout="constrained")
    axs[0].scatter(by_run_shift.center_x_px,by_run_shift.center_y_px,c=np.arange(1,31),cmap="viridis",s=35)
    axs[0].scatter([-psf_centroid[0]],[-psf_centroid[1]],marker="x",s=110,color="red",label="Inverse bank center")
    axs[0].scatter([0],[0],marker="+",s=100,color="black",label="Raw")
    axs[0].set(xlabel="R143 - Raw center X (px)",ylabel="R143 - Raw center Y (px)",title="Systematic center shift")
    axs[0].legend(fontsize=8,frameon=False);axs[0].grid(alpha=.2)
    axs[1].plot(by_step.index,by_step.old_sd,label="R140v2",marker="o",ms=3)
    axs[1].plot(by_step.index,by_step.new_sd,label="R143",marker="o",ms=3)
    axs[1].set(xlabel="Step position",ylabel="Across-scan SD (nm)",title="Short-step repeatability")
    axs[1].legend(frameon=False);axs[1].grid(alpha=.2)
    axs[2].scatter(frame_table.old,frame_table.new,s=38)
    bound=max(frame_table.old.max(),frame_table.new.max())+.2
    axs[2].plot([0,bound],[0,bound],ls="--",color="gray")
    axs[2].set(xlabel="R140v2 shift-test RMS (nm)",ylabel="R143 shift-test RMS (nm)",
               title="Fourier subpixel diagnostic")
    axs[2].grid(alpha=.2)
    fig.savefig(figdir / "R143_stability_mechanisms.png",dpi=180)
    plt.close(fig)
    byrun = pd.DataFrame(dict(raw_edge_width_px=run_raw_width,
                              old_output_edge_width_px=old_edge.groupby(level="run").edge_width_px.mean(),
                              new_output_edge_width_px=new_edge.groupby(level="run").edge_width_px.mean(),
                              diameter_shift_nm=run_diameter_shift)).reset_index()
    byrun["run_index"] = np.arange(1,31)
    byrun.to_csv(OUT / "run_edge_drift.csv",index=False)
    fig, axs = plt.subplots(1,2,figsize=(10,4),layout="constrained")
    axs[0].plot(byrun.run_index,byrun.raw_edge_width_px,label="Raw",lw=2)
    axs[0].plot(byrun.run_index,byrun.old_output_edge_width_px,label="R140v2",lw=2)
    axs[0].plot(byrun.run_index,byrun.new_output_edge_width_px,label="R143",lw=2)
    axs[0].set(xlabel="Complete scan",ylabel="20-80% edge width (px)",title="Edge response across scans")
    axs[0].legend(frameon=False);axs[0].grid(alpha=.2)
    axs[1].plot(byrun.run_index,byrun.diameter_shift_nm,color="#b64f3f",marker="o",ms=3)
    axs[1].set(xlabel="Complete scan",ylabel="R143 - R140v2 diameter (nm)",title="Diameter shift across scans")
    axs[1].grid(alpha=.2)
    fig.savefig(figdir / "R143_edge_drift.png",dpi=180)
    plt.close(fig)
    print("STABILITY_SUMMARY_SAVED", OUT / "summary.json")


if __name__ == "__main__":
    main()
