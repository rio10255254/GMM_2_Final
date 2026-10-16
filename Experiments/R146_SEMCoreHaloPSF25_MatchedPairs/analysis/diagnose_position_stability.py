"""Compare per-pillar position response on the fixed thirty real scans."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


MODELS = ["Raw", "R140v2-StableUNet", "R143-PSF25-MatchedPairs",
          "R145-Center9PSF25-CorrectedPairs", "R146-SEMCoreHaloPSF25-MatchedPairs"]


def main() -> None:
    plan = load(ROOT / "evaluation/capture_plan.json")
    axis = np.asarray(load(ROOT / "evaluation/calibration.json")["axis_unit_vector"], dtype=float)
    assert len(plan["runs"]) == 30 and len(plan["frames"]) == 930
    pi_steps = np.empty((30, 30), dtype=float)
    for run_index, run in enumerate(plan["runs"]):
        frames = [f for f in plan["frames"] if f["run"] == run["run"]]
        assert len(frames) == 31
        pi_steps[run_index] = np.diff([f["pi_y_um"] for f in frames]) * 1000

    centers: dict[str, np.ndarray] = {}
    errors_by_model: dict[str, np.ndarray] = {}
    output = {}
    for model in MODELS:
        base = (ROOT / "results/centers" if model == MODELS[-1]
                else ROOT / "evaluation/baseline_centers" / model)
        scans = []
        for run in plan["runs"]:
            df = pd.read_csv(base / (run["run"] + ".csv")).sort_values(["index", "pillar_id"])
            assert len(df) == 279
            scans.append(df[["center_x_px", "center_y_px"]].to_numpy().reshape(31, 9, 2))
        centers[model] = np.stack(scans)
        steps_nm = np.diff(centers[model], axis=1) @ axis * 172.5
        errors = steps_nm - pi_steps[:, :, None]
        errors_by_model[model] = errors
        fixed_step_pillar_sd = errors.std(axis=0, ddof=1)
        output[model] = dict(
            single_pillar_short_step_repeat_sd_mean_nm=float(fixed_step_pillar_sd.mean()),
            single_pillar_short_step_repeat_sd_median_nm=float(np.median(fixed_step_pillar_sd)),
            single_pillar_short_step_mae_nm=float(np.abs(errors).mean()),
        )

    ref = output["R140v2-StableUNet"]["single_pillar_short_step_repeat_sd_mean_nm"]
    for model in MODELS:
        shift = centers[model] - centers["Raw"]
        output[model]["mean_center_shift_from_raw_px"] = shift.mean(axis=(0, 1, 2)).tolist()
        output[model]["mean_single_pillar_repeat_sd_change_vs_r140_nm"] = (
            output[model]["single_pillar_short_step_repeat_sd_mean_nm"] - ref)

    # Check the new model's per-pillar variability directly against both predecessors.
    def cell_sd(model: str) -> np.ndarray:
        steps = np.diff(centers[model], axis=1) @ axis * 172.5
        return (steps - pi_steps[:, :, None]).std(axis=0, ddof=1)

    new_sd = cell_sd(MODELS[-1])
    for model in MODELS[:-1]:
        output[MODELS[-1]]["worse_fixed_step_pillar_cells_than_" + model] = int(
            (new_sd > cell_sd(model)).sum())

    rng = np.random.default_rng(145136)
    draw = rng.integers(0, 30, size=(2000, 30))
    def resampled_mean_sd(model: str) -> np.ndarray:
        return errors_by_model[model][draw].std(axis=1, ddof=1).mean(axis=(1, 2))
    new_boot = resampled_mean_sd(MODELS[-1])
    paired = {}
    for model in ("R140v2-StableUNet", "R143-PSF25-MatchedPairs", "R145-Center9PSF25-CorrectedPairs"):
        delta = new_boot - resampled_mean_sd(model)
        paired[model] = dict(mean_difference_nm=float(output[MODELS[-1]]["single_pillar_short_step_repeat_sd_mean_nm"]
                                                       - output[model]["single_pillar_short_step_repeat_sd_mean_nm"]),
                             ci95_nm=np.quantile(delta, [.025, .975]).tolist())

    save(ROOT / "results/position_stability_followup.json", dict(
        models=output, fixed_step_pillar_cells=270, scans=30, positions=31,
        paired_whole_scan_bootstrap=paired,
        center_measurement_scope="same thirty scans and nine pillars; no new captures",
        script_sha256=sha(Path(__file__)), completed_utc=now()))
    for model in MODELS:
        print(model, output[model], flush=True)


if __name__ == "__main__":
    main()
