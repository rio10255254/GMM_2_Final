"""Recalculate one 30-step SD per scan for all compatible completed models."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
EXP = Path(r"D:\GMM_2_Final\Experiments")
R152 = EXP / "R152_R148v2_SafeAdaptivePSF"
R150 = EXP / "R150_MatchedGeometryMeanPSF"
R136 = EXP / "R136_PIRepeatability"
SRC152 = R152 / "results/comparison/all_displacements.csv"
SRC150 = R150 / "results/comparison/all_displacements.csv"
SRC128 = R136 / "results/sem_corner9/Raw_R128_comparison/all_displacements_3600.csv"
READOUTS = R136 / "results/sem_corner9/readouts"

DISPLAY = {
    "Raw": "RAW", "R61": "R61", "R128": "R128", "R129": "R129",
    "R130-Clean": "R130", "R137-WeakPSF": "R137", "R138-V42PSF8": "R138",
    "R139-UNetRecurrent": "R139", "R140v2-StableUNet": "R140v2",
    "R143-PSF25-MatchedPairs": "R143", "R145-Center9PSF25-CorrectedPairs": "R145",
    "R146-SEMCoreHaloPSF25-MatchedPairs": "R146",
    "R147-FullResPSFConsistency": "R147",
    "R148v2-HybridContextNativePSF": "R148v2",
    "R150-MatchedGeometryMeanPSF": "R150",
    "R152-R148v2-SafeAdaptivePSF": "R152",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_data():
    a = pd.read_csv(SRC152)
    b = pd.read_csv(SRC150)
    c = pd.read_csv(SRC128)
    assert load_json(R152 / "results/final_audit.json")["passed"]
    assert load_json(R150 / "results/final_audit.json")["passed"]
    fa = load_json(R152 / "evaluation/capture_plan.json")["frames"]
    fb = load_json(R150 / "evaluation/capture_plan.json")["frames"]
    identity = lambda frames: [(f["run"], f["index"], f["source"]["sha256"]) for f in frames]
    assert len(fa) == len(fb) == 930 and identity(fa) == identity(fb)
    keys = ["run", "kind", "i", "j"]
    numbers = ["pi_displacement_um", "image_displacement_um", "error_nm", "dx_px", "dy_px", "transverse_nm"]
    common = set(a.model) & set(b.model)
    assert len(common) == 12
    for model in common:
        x = a[a.model == model].sort_values(keys).reset_index(drop=True)
        y = b[b.model == model].sort_values(keys).reset_index(drop=True)
        assert len(x) == len(y) == 1800 and x[keys].equals(y[keys])
        assert np.max(np.abs(x[numbers].to_numpy() - y[numbers].to_numpy())) == 0
    raw = a[a.model == "Raw"].sort_values(keys).reset_index(drop=True)
    c_raw = c[c.model == "Raw"].sort_values(keys).reset_index(drop=True)
    assert len(c_raw) == len(raw) == 1800 and c_raw[keys].equals(raw[keys])
    r128_raw_diff = float(np.max(np.abs(c_raw.image_along_um - raw.image_displacement_um)))
    assert r128_raw_diff < 1e-8

    calibration = load_json(R152 / "evaluation/calibration.json")
    axis = np.asarray(calibration["axis_unit_vector"], dtype=np.float64)
    readouts = {}
    for model in ("Raw", "R61"):
        files = sorted((READOUTS / model).glob("*_XY_0.csv"))
        assert len(files) == 30
        frame = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
        assert len(frame) == 1800 and frame.run.nunique() == 30 and frame.status.eq("ok").all()
        frame["image_displacement_um"] = frame[["dx_px", "dy_px"]].to_numpy() @ axis * 0.1725
        readouts[model] = frame
    readout_raw = readouts["Raw"].sort_values(keys).reset_index(drop=True)
    assert readout_raw[keys].equals(raw[keys])
    r61_raw_diff = float(np.max(np.abs(readout_raw.image_displacement_um - raw.image_displacement_um)))
    pi_diff = float(np.max(np.abs(readout_raw.pi_dy_um - raw.pi_displacement_um)))
    assert r61_raw_diff < 1e-12 and pi_diff == 0

    add150 = b[b.model == "R150-MatchedGeometryMeanPSF"].copy()
    add128 = c[c.model == "R128"].copy()
    assert len(add128) == 1800 and add128.view.eq("nominal_all30").all()
    add128["image_displacement_um"] = add128.image_along_um
    add128["pi_displacement_um"] = add128.pi_dy_um
    add61 = readouts["R61"].copy()
    add61["model"] = "R61"
    add61["pi_displacement_um"] = add61.pi_dy_um
    columns = ["model", "run", "run_index", "kind", "i", "j", "image_displacement_um", "pi_displacement_um"]
    all_models = pd.concat([a[columns], add150[columns], add128[columns], add61[columns]], ignore_index=True)
    assert len(all_models) == 16 * 1800 and set(all_models.model) == set(DISPLAY)
    checks = {
        "R150_same_930_capture_sha256": True,
        "R150_exact_common_method_count": len(common),
        "R128_RAW_max_export_difference_um": r128_raw_diff,
        "R61_RAW_max_replay_difference_um": r61_raw_diff,
        "R61_PI_max_difference_um": pi_diff,
        "R61_readout_run_count": 30,
        "calibration_raw_scans": calibration["raw_calibration_runs"],
        "later_evaluation_scans": calibration["evaluation_runs"],
        "source_sha256": {str(p): sha256(p) for p in (SRC152, SRC150, SRC128)},
    }
    return all_models, checks


def analyze(all_models: pd.DataFrame, checks: dict):
    steps = all_models[all_models.kind == "adjacent"].copy()
    assert len(steps) == 16 * 30 * 30
    assert (steps.j == steps.i + 1).all() and not steps.duplicated(["model", "run", "j"]).any()
    steps["observed_nm"] = steps.image_displacement_um * 1000
    steps["PI_corrected_nm"] = (steps.image_displacement_um - steps.pi_displacement_um) * 1000
    per_scan = []
    for (model, run), group in steps.groupby(["model", "run"]):
        group = group.sort_values("j")
        assert len(group) == 30 and np.array_equal(group.j.to_numpy(), np.arange(1, 31))
        per_scan.append({
            "model": model, "display": DISPLAY[model], "run": run,
            "run_index": int(group.run_index.iloc[0]), "n_steps": 30,
            "mean_step_nm": float(group.observed_nm.mean()),
            "observed_step_sd_nm": float(group.observed_nm.std(ddof=1)),
            "PI_corrected_step_sd_nm": float(group.PI_corrected_nm.std(ddof=1)),
        })
    table = pd.DataFrame(per_scan)
    assert len(table) == 16 * 30
    run_order = table[table.model == "Raw"].sort_values("run_index").run.tolist()
    assert len(run_order) == len(set(run_order)) == 30
    observed = table.pivot(index="run", columns="model", values="observed_step_sd_nm").loc[run_order]
    corrected = table.pivot(index="run", columns="model", values="PI_corrected_step_sd_nm").loc[run_order]
    assert observed.notna().all().all() and corrected.notna().all().all()
    for model in DISPLAY:
        sum_sq = sum(float(np.square(g.observed_nm - g.observed_nm.mean()).sum())
                     for _, g in steps[steps.model == model].groupby("run"))
        direct = np.sqrt(sum_sq / (30 * 29))
        from_scans = np.sqrt(np.mean(np.square(observed[model].to_numpy())))
        assert abs(direct - from_scans) < 1e-10
    checks["pooled_formula_independently_reproduced"] = True

    raw = observed["Raw"].to_numpy()
    raw_pooled = float(np.sqrt(np.mean(raw**2)))
    rng = np.random.default_rng(20260930)
    draws = rng.integers(0, 30, size=(20_000, 30))
    boot_raw = np.sqrt(np.mean(raw[draws]**2, axis=1))
    old = pd.read_csv(R152 / "results/comparison/displacement_summary.csv")
    old150 = pd.read_csv(R150 / "results/comparison/displacement_summary.csv")
    old = pd.concat([old, old150[old150.model == "R150-MatchedGeometryMeanPSF"]])
    summary = []
    for model in DISPLAY:
        values = observed[model].to_numpy()
        pooled = float(np.sqrt(np.mean(values**2)))
        gain_each = 100 * (1 - values / raw)
        boot_model = np.sqrt(np.mean(values[draws]**2, axis=1))
        ci = np.quantile(100 * (1 - boot_model / boot_raw), [.025, .975])
        older = old[(old.model == model) & (old.kind == "adjacent")]
        summary.append({
            "model": model, "display": DISPLAY[model],
            "mean_scan_sd_nm": float(values.mean()),
            "median_scan_sd_nm": float(np.median(values)),
            "pooled_within_scan_sd_nm": pooled,
            "per_scan_sd_min_nm": float(values.min()),
            "per_scan_sd_max_nm": float(values.max()),
            "between_scan_sd_of_scan_sds_nm": float(values.std(ddof=1)),
            "pooled_PI_corrected_sd_nm": float(np.sqrt(np.mean(np.square(corrected[model].to_numpy())))),
            "raw_reduction_pooled_percent": float(100 * (1 - pooled / raw_pooled)),
            "raw_reduction_CI95_percent": [float(ci[0]), float(ci[1])],
            "raw_reduction_per_scan_min_percent": float(gain_each.min()),
            "raw_reduction_per_scan_max_percent": float(gain_each.max()),
            "improved_scans_vs_raw": int((values < raw).sum()),
            "first6_pooled_sd_nm": float(np.sqrt(np.mean(values[:6]**2))),
            "later24_pooled_sd_nm": float(np.sqrt(np.mean(values[6:]**2))),
            "old_across_scan_same_step_mean_sd_nm": float(older.repeatability_nm.iloc[0]) if len(older) == 1 else None,
        })
    summary.sort(key=lambda row: row["pooled_within_scan_sd_nm"])
    for index, row in enumerate(summary, 1):
        row["point_rank"] = index

    pairs = [
        ("R140v2-StableUNet", "R128"),
        ("R140v2-StableUNet", "R150-MatchedGeometryMeanPSF"),
        ("R128", "R150-MatchedGeometryMeanPSF"),
        ("R128", "R148v2-HybridContextNativePSF"),
        ("R150-MatchedGeometryMeanPSF", "R148v2-HybridContextNativePSF"),
        ("R145-Center9PSF25-CorrectedPairs", "R150-MatchedGeometryMeanPSF"),
        ("R148v2-HybridContextNativePSF", "R152-R148v2-SafeAdaptivePSF"),
    ]
    comparisons = []
    for first, second in pairs:
        x, y = observed[first].to_numpy(), observed[second].to_numpy()
        boot = np.sqrt(np.mean(y[draws]**2, axis=1)) - np.sqrt(np.mean(x[draws]**2, axis=1))
        low, high = np.quantile(boot, [.025, .975])
        comparisons.append({
            "first": first, "second": second,
            "second_minus_first_pooled_nm": float(np.sqrt(np.mean(y**2)) - np.sqrt(np.mean(x**2))),
            "CI95_nm": [float(low), float(high)],
            "first_lower_scans": int((x < y).sum()),
            "second_lower_scans": int((y < x).sum()),
        })
    return {
        "definition": "Within each complete scan, sample SD of 30 observed adjacent steps",
        "models": 16, "scans": 30, "steps_per_scan": 30,
        "adjacent_rows": len(steps),
        "bootstrap": {"resampling_unit": "whole scan", "draws": 20_000, "seed": 20260930},
        "source_checks": checks,
        "ranked_summary": summary,
        "paired_model_comparisons": comparisons,
        "per_scan": sorted(per_scan, key=lambda row: (row["run_index"], row["display"])),
    }


def main():
    combined, checks = source_data()
    result = analyze(combined, checks)
    path = OUT / "summary.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "passed", "models": result["models"], "scans": result["scans"],
        "adjacent_rows": result["adjacent_rows"], "best_point_estimate": result["ranked_summary"][0]["display"],
        "output": str(path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
