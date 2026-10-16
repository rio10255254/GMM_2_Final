from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat


ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\tests\artifacts\cd_verification_20260714")
FIT_ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\output\pillar_via_junction_psf_20260713")
ANALYZE_PATH = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data"
    r"\center9_pillar_fit_20x_50x\psf_deconvolution_cd\analyze_cd.py"
)
CROP_ORIGINS = {"20x": (1794, 838), "50x": (874, 586)}
PHYSICAL_IDS = {
    "20x": np.array([7, 4, 1, 8, 5, 2, 9, 6, 3]),
    "50x": np.arange(1, 10),
}

spec = importlib.util.spec_from_file_location("center9_cd", ANALYZE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


case_data: dict[str, dict] = {}
for label in ("20x", "50x"):
    sweep = loadmat(ROOT / f"{label}_deconvolution_sweep.mat")
    with (FIT_ROOT / label / "selected_frame.json").open(encoding="utf-8") as handle:
        meta = json.load(handle)
    crop_x1, crop_y1 = CROP_ORIGINS[label]
    centers = np.asarray(meta["pillar_centers_xy"], dtype=float)
    centers -= np.array([crop_x1 - 1, crop_y1 - 1])
    pitch_px = float(meta["pitch_px"])
    nm_per_px = float(meta["object_pixel_um"]) * 1000.0
    sem_nm = np.asarray(meta["image_oriented_sem_cd_nm"], dtype=float).reshape(-1)
    raw_measurements = [module.measure_cd(sweep["I"], center, pitch_px) for center in centers]
    raw_cd_nm = np.asarray([m.cd_px for m in raw_measurements]) * nm_per_px
    raw_error_nm = raw_cd_nm - sem_nm
    raw_edge_width_px = float(np.mean([m.edge_width_px for m in raw_measurements]))

    nsr_values = np.asarray(sweep["nsr_values"]).reshape(-1)
    candidate_indices = [idx for idx, value in enumerate(nsr_values) if 0.05 <= value <= 0.08]
    candidates: dict[float, dict] = {}
    for idx in candidate_indices:
        nsr = round(float(nsr_values[idx]), 4)
        image = np.asarray(sweep["contrast_wiener"][:, :, idx], dtype=float)
        measurements = [module.measure_cd(image, center, pitch_px) for center in centers]
        candidates[nsr] = {
            "cd_nm": np.asarray([m.cd_px for m in measurements]) * nm_per_px,
            "edge_width_px": float(np.mean([m.edge_width_px for m in measurements])),
        }
    case_data[label] = {
        "sem_nm": sem_nm,
        "raw_cd_nm": raw_cd_nm,
        "raw_error_nm": raw_error_nm,
        "raw_mae_nm": float(np.mean(np.abs(raw_error_nm))),
        "raw_max_abs_error_nm": float(np.max(np.abs(raw_error_nm))),
        "raw_edge_width_px": raw_edge_width_px,
        "candidates": candidates,
    }


common_nsr = sorted(set(case_data["20x"]["candidates"]) & set(case_data["50x"]["candidates"]))


def select_nsr(training_physical_ids: set[int]) -> tuple[float, float]:
    scored: list[tuple[float, float]] = []
    for nsr in common_nsr:
        normalized_errors: list[float] = []
        valid = True
        for label in ("20x", "50x"):
            case = case_data[label]
            if case["candidates"][nsr]["edge_width_px"] >= case["raw_edge_width_px"]:
                valid = False
                break
            mask = np.isin(PHYSICAL_IDS[label], list(training_physical_ids))
            errors = case["candidates"][nsr]["cd_nm"][mask] - case["sem_nm"][mask]
            normalized_errors.extend((np.abs(errors) / case["raw_mae_nm"]).tolist())
        if not valid:
            continue
        # Average error is primary; a modest worst-case term prevents selecting
        # a visually sharp setting that creates one large dimensional outlier.
        score = float(np.mean(normalized_errors) + 0.25 * np.max(normalized_errors))
        scored.append((score, nsr))
    if not scored:
        raise RuntimeError("No common NSR satisfied the edge-width constraint")
    return min(scored)


fold_rows: list[dict] = []
for holdout_id in range(1, 10):
    training_ids = set(range(1, 10)) - {holdout_id}
    score, selected_nsr = select_nsr(training_ids)
    for label in ("20x", "50x"):
        case = case_data[label]
        image_index = int(np.flatnonzero(PHYSICAL_IDS[label] == holdout_id)[0])
        sem = float(case["sem_nm"][image_index])
        raw_cd = float(case["raw_cd_nm"][image_index])
        restored_cd = float(case["candidates"][selected_nsr]["cd_nm"][image_index])
        fold_rows.append(
            {
                "holdout_physical_pillar": holdout_id,
                "magnification": label,
                "selected_nsr": selected_nsr,
                "training_score": score,
                "sem_cd_nm": sem,
                "raw_cd_nm": raw_cd,
                "restored_cd_nm": restored_cd,
                "raw_abs_error_nm": abs(raw_cd - sem),
                "restored_abs_error_nm": abs(restored_cd - sem),
                "improved": abs(restored_cd - sem) < abs(raw_cd - sem),
            }
        )

full_score, full_selected_nsr = select_nsr(set(range(1, 10)))
summary = {
    "selection_method": "common NSR for both magnifications; minimize normalized MAE plus 0.25 worst-case penalty; require edge width lower than raw",
    "full_dataset_selected_nsr": full_selected_nsr,
    "full_dataset_score": full_score,
    "leave_one_physical_pillar_out_selected_nsr": sorted(
        set(float(row["selected_nsr"]) for row in fold_rows)
    ),
    "holdout_raw_mae_nm": float(np.mean([row["raw_abs_error_nm"] for row in fold_rows])),
    "holdout_restored_mae_nm": float(
        np.mean([row["restored_abs_error_nm"] for row in fold_rows])
    ),
    "holdout_improved_count": int(sum(bool(row["improved"]) for row in fold_rows)),
    "holdout_total_count": len(fold_rows),
}

with (ROOT / "common_nsr_leave_one_pillar_out.csv").open(
    "w", encoding="utf-8-sig", newline=""
) as handle:
    writer = csv.DictWriter(handle, fieldnames=list(fold_rows[0]))
    writer.writeheader()
    writer.writerows(fold_rows)
with (ROOT / "common_nsr_validation.json").open("w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, ensure_ascii=False)

print(json.dumps(summary, indent=2, ensure_ascii=False))
