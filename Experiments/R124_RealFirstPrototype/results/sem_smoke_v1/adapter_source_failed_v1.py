"""Replay the fixed SEM half-contrast readout on untrained engineering outputs.

This is a two-exposure adapter check, not full ACM validation or evidence of learned
efficacy. No registration, thresholds, source masks, or model outputs are adjusted.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

import cv2
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt, map_coordinates


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT.parent
OLD = EXPERIMENTS / "R119_SequenceGeometryValidation" / "analysis" / "R109_comparison_20260907"
OLD_PRIMARY = EXPERIMENTS / "R119_SequenceGeometryValidation" / "results" / "formal_sem" / "results" / "masks" / "acm_primary_masks.mat"
RAW_ROOT = EXPERIMENTS / "R69_ACMContourSEMValidation" / "inputs" / "sem_paired_50x_exposure_stack"
SMOKE = ROOT / "results" / "real_smoke_v1"
OUT = ROOT / "results" / "sem_smoke_v1"
EXPOSURES = (13, 24)
REFERENCES = {"historical": "truth_historical", "global_pitch_matched": "truth_pitch_matched"}
METHODS = ("Raw", "identity_assumption", "gaussian_assumption")
SOURCE_NAMES = {13: "sem_optical_exposure13", 24: "sem_optical_exposure24"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path) -> dict:
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def save(name: str, value) -> None:
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def selected_stat(values: np.ndarray, valid: np.ndarray, operation=np.mean):
    return float(operation(values[valid])) if valid.any() else None


def independent_crossing(profiles: np.ndarray, t: np.ndarray, level: float = 0.5):
    """Scalar reference calculation, independent of archived vectorized interpolation."""
    positions = np.full(len(profiles), np.nan)
    valid = np.zeros(len(profiles), dtype=bool)
    for index, values in enumerate(profiles):
        hits = np.flatnonzero((values[:-1] < level) & (values[1:] >= level))
        if len(hits) == 1 and values[0] < level and values[-1] > level:
            k = int(hits[0])
            if np.isfinite(values[k:k + 2]).all():
                positions[index] = np.interp(level, values[k:k + 2], t[k:k + 2])
                valid[index] = np.isfinite(positions[index])
    return positions, valid


def failure_counts(profiles: np.ndarray, valid: np.ndarray) -> dict:
    hits = ((profiles[:, :-1] < 0.5) & (profiles[:, 1:] >= 0.5)).sum(axis=1)
    finite = np.isfinite(profiles).all(axis=1)
    reasons = np.full(len(profiles), "other_invalid", dtype=object)
    reasons[valid] = "valid"
    remaining = ~valid
    for label, condition in (
        ("nonfinite", ~finite),
        ("no_rising_crossing", hits == 0),
        ("multiple_rising_crossings", hits > 1),
        ("endpoints_do_not_bracket", ~((profiles[:, 0] < 0.5) & (profiles[:, -1] > 0.5))),
    ):
        matched = remaining & condition
        reasons[matched] = label
        remaining[matched] = False
    return {str(label): int((reasons == label).sum()) for label in np.unique(reasons)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    try:
        sources = [Path(__file__), OLD / "profiles.py", OLD / "acm_arrays.mat", OLD_PRIMARY,
                   OLD / "acm_measurements.csv", OLD / "profile_measurements.csv", SMOKE / "summary.json"]
        for exposure in EXPOSURES:
            sources.extend([RAW_ROOT / f"{exposure}.bmp", OLD / "images_v2" / str(exposure) / "Raw.png"])
            for method in METHODS[1:]:
                sources.extend([SMOKE / SOURCE_NAMES[exposure] / method / "output_float.npz",
                                SMOKE / SOURCE_NAMES[exposure] / method / "metadata.json"])
            for reference in REFERENCES:
                sources.extend(OLD / "profile_arrays" / f"{reference}_p{pillar:02d}_e{exposure}.npz" for pillar in range(1, 37))
        protected = [file_record(path) for path in sources]
        save("protected_inputs_before.json", protected)
        save("contract.json", {
            "started_utc": now(), "sources": "Two existing SEM-linked optical exposures and frozen untrained real_smoke_v1 outputs",
            "exposures": list(EXPOSURES), "physical_objects": 36, "references": list(REFERENCES), "methods": list(METHODS),
            "profiles_per_object": 720, "normal_step_px": 0.125, "normal_range_px": [-12, 12],
            "readout": "Unique rising half-contrast crossing, relative to geometry-only calibrated digital SEM reference",
            "alignment": "Existing Raw-derived integer offsets from archived ACM; checked against archived profile offsets",
            "plateaus": "Common Raw medians in the archived SEM inside/outside regions; no output-derived thresholds",
            "population": "Raw AND identity AND assumedGaussian common-valid normals per object; own-valid results also retained",
            "input_domain": "Native raw intensity / 255 and native float model output, no display normalization or uint8 output quantization",
            "no_full_acm_evaluation": True, "no_physical_accuracy_qualification": True,
            "network_untrained": True, "calibration_qualified": False, "uncertainty_calibrated": False,
            "learned_efficacy_evaluated": False, "new_holdout": False,
        })
        smoke_summary = json.loads((SMOKE / "summary.json").read_text(encoding="utf-8"))
        if smoke_summary.get("status") != "untrained_engineering_preview_complete":
            raise ValueError("Smoke outputs are not a complete engineering preview")
        if smoke_summary.get("network_untrained") is not True or smoke_summary.get("calibration_qualified") is not False:
            raise ValueError("Expected explicitly untrained, unqualified smoke outputs")
        specification = importlib.util.spec_from_file_location("r119_fixed_profile_geometry", OLD / "profiles.py")
        archived = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(archived)
        if not np.array_equal(archived.T, np.arange(-12, 12.00001, 0.125)):
            raise ValueError("Archived sampling contract differs")

        geometry = loadmat(OLD_PRIMARY, variable_names=["global_index", "opt_centers"])
        masks = loadmat(OLD / "acm_arrays.mat", variable_names=list(REFERENCES.values()))
        acm = pd.read_csv(OLD / "acm_measurements.csv")
        old_profiles = pd.read_csv(OLD / "profile_measurements.csv")
        acm = acm[(acm.method == "Raw") & acm.exposure.isin(EXPOSURES)].set_index(["reference", "exposure", "pillar"], verify_integrity=True)
        old_profiles = old_profiles[(old_profiles.method == "Raw") & (old_profiles.readout == "half") & old_profiles.exposure.isin(EXPOSURES)]
        old_profiles = old_profiles.set_index(["reference", "exposure", "pillar"], verify_integrity=True)
        if len(acm) != 144 or len(old_profiles) != 144:
            raise ValueError("Expected 144 fixed reference/exposure/object rows")
        images: dict[tuple[int, str], np.ndarray] = {}
        input_checks = []
        for exposure in EXPOSURES:
            raw_u8 = cv2.imread(str(RAW_ROOT / f"{exposure}.bmp"), cv2.IMREAD_GRAYSCALE)
            previous_raw = cv2.imread(str(OLD / "images_v2" / str(exposure) / "Raw.png"), cv2.IMREAD_GRAYSCALE)
            if raw_u8 is None or not np.array_equal(raw_u8, previous_raw):
                raise ValueError(f"Raw pixels differ from archived input at exposure {exposure}")
            images[exposure, "Raw"] = raw_u8.astype(float) / 255.0
            for method in METHODS[1:]:
                case = SMOKE / SOURCE_NAMES[exposure] / method
                metadata = json.loads((case / "metadata.json").read_text(encoding="utf-8"))
                if metadata.get("network_untrained") is not True or metadata.get("calibration_qualified") is not False or metadata.get("uncertainty_calibrated") is not False:
                    raise ValueError(f"Unexpected training/calibration flags in {case}")
                if metadata["source"]["sha256"] != sha256(RAW_ROOT / f"{exposure}.bmp"):
                    raise ValueError(f"Smoke source hash mismatch: {case}")
                with np.load(case / "output_float.npz") as saved:
                    output = saved["output"].astype(float)
                if output.shape != raw_u8.shape or not np.isfinite(output).all():
                    raise ValueError(f"Malformed smoke output: {case}")
                images[exposure, method] = output
            input_checks.append({"exposure": exposure, "raw_pixels_match_archived": True, "shape": list(raw_u8.shape)})

        centers = {}
        for row in range(6):
            for column in range(6):
                pillar = int(geometry["global_index"][row, column])
                cx, cy = np.floor(geometry["opt_centers"][row * 6 + column] + 0.5).astype(int) - 1
                centers[pillar] = (int(cx), int(cy))
        yy, xx = np.mgrid[:104, :104]
        radius = np.hypot(xx - 51.5, yy - 51.5)
        rows, parity_rows, geometry_rows = [], [], []
        array_directory = OUT / "profile_arrays"
        array_directory.mkdir()
        independent_max_error = 0.0
        for reference, variable in REFERENCES.items():
            for pillar in range(1, 37):
                mask = masks[variable][:, :, pillar - 1].astype(bool)
                coords, geometry_reference = archived.geometry_profiles(mask)
                target, target_valid = geometry_reference["half"]
                inside = distance_transform_edt(mask) > 8
                outside = (distance_transform_edt(~mask) > 8) & (radius < 50)
                geometry_rows.append({"reference": reference, "pillar": pillar, "valid_profiles": int(target_valid.sum()),
                                      "max_half_calibration_error_px": float(np.max(np.abs(target[target_valid])))})
                for exposure in EXPOSURES:
                    key = (reference, exposure, pillar)
                    acm_row, old_row = acm.loc[key], old_profiles.loc[key]
                    offset = np.array([int(acm_row.raw_offset_y), int(acm_row.raw_offset_x)])
                    if not np.array_equal(offset, [int(old_row.raw_offset_y), int(old_row.raw_offset_x)]):
                        raise ValueError(f"Archived ACM/profile alignment disagrees: {key}")
                    shifted = coords + (offset + 12)[:, None, None]
                    cx, cy = centers[pillar]
                    crops = {method: images[exposure, method][cy - 64:cy + 64, cx - 64:cx + 64] for method in METHODS}
                    if any(crop.shape != (128, 128) for crop in crops.values()):
                        raise ValueError(f"Expected 128x128 intensity crops: {key}")
                    raw104 = crops["Raw"][12:-12, 12:-12]
                    lo, hi = float(np.median(raw104[inside])), float(np.median(raw104[outside]))
                    if not hi > lo:
                        raise ValueError(f"Historical dark-object Raw plateau contract fails: {key}")
                    arrays = {"target_half": target, "target_valid": target_valid, "normal_t": archived.T,
                              "sample_coordinates_yx": shifted, "plateaus_inside_outside": np.array([lo, hi])}
                    results, failures = {}, {}
                    for method in METHODS:
                        profile = map_coordinates(crops[method], shifted, order=1, mode="nearest")
                        normalized = (profile - lo) / (hi - lo)
                        position, measured_valid = archived.crossing(normalized)
                        independently_measured, independently_valid = independent_crossing(normalized, archived.T)
                        if not np.array_equal(measured_valid, independently_valid):
                            raise ValueError(f"Independent crossing validity differs: {key}/{method}")
                        if measured_valid.any():
                            difference = float(np.max(np.abs(position[measured_valid] - independently_measured[measured_valid])))
                            independent_max_error = max(independent_max_error, difference)
                            if difference > 1e-10:
                                raise ValueError(f"Independent crossing mismatch: {key}/{method}, {difference}")
                        valid = measured_valid & target_valid
                        error = position - target
                        results[method] = (error, valid)
                        failures[method] = failure_counts(normalized, measured_valid)
                        arrays[f"{method}_profile"] = profile
                        arrays[f"{method}_half_error"] = error
                        arrays[f"{method}_half_valid"] = valid
                    raw_error, raw_valid = results["Raw"]
                    with np.load(OLD / "profile_arrays" / f"{reference}_p{pillar:02d}_e{exposure}.npz") as previous:
                        saved_error, saved_valid = previous["Raw_half_error"], previous["Raw_half_valid"]
                    valid_parity = bool(np.array_equal(saved_valid, raw_valid))
                    position_parity = float(np.max(np.abs(saved_error[raw_valid] - raw_error[raw_valid]))) if raw_valid.any() else 0.0
                    mae_parity = abs(float(np.mean(np.abs(raw_error[raw_valid]))) - float(old_row.mean_absolute_error_px)) if raw_valid.any() else 0.0
                    bias_parity = abs(float(np.median(raw_error[raw_valid])) - float(old_row.median_signed_error_px)) if raw_valid.any() else 0.0
                    if not valid_parity or max(position_parity, mae_parity, bias_parity) > 1e-10:
                        raise ValueError(f"Historical Raw parity failed: {key}")
                    parity_rows.append({"reference": reference, "exposure": exposure, "pillar": pillar,
                                        "validity_equal": valid_parity, "max_normal_error_difference_px": position_parity,
                                        "mae_table_difference_px": mae_parity, "bias_table_difference_px": bias_parity,
                                        "raw_offset_y": int(offset[0]), "raw_offset_x": int(offset[1])})
                    common = np.logical_and.reduce([results[method][1] for method in METHODS])
                    arrays["common_valid"] = common
                    np.savez_compressed(array_directory / f"{reference}_p{pillar:02d}_e{exposure}.npz", **arrays)
                    for method in METHODS:
                        error, valid = results[method]
                        row = {"reference": reference, "exposure": exposure, "pillar": pillar, "method": method,
                               "total_profiles": 720, "valid_profiles": int(valid.sum()), "invalid_profiles": int((~valid).sum()),
                               "common_profiles": int(common.sum()), "common_coverage": float(common.mean()),
                               "own_mean_absolute_error_px": selected_stat(np.abs(error), valid),
                               "own_median_signed_error_px": selected_stat(error, valid, np.median),
                               "common_mean_absolute_error_px": selected_stat(np.abs(error), common),
                               "common_median_signed_error_px": selected_stat(error, common, np.median),
                               "common_p95_absolute_error_px": selected_stat(np.abs(error), common, lambda x: np.percentile(x, 95)),
                               "common_max_absolute_error_px": selected_stat(np.abs(error), common, np.max),
                               "common_mean_absolute_difference_from_Raw_error_px": selected_stat(np.abs(error) - np.abs(raw_error), common),
                               "common_median_signed_change_from_Raw_px": selected_stat(error - raw_error, common, np.median),
                               "raw_inside_level": lo, "raw_outside_level": hi, "raw_offset_y": int(offset[0]), "raw_offset_x": int(offset[1]),
                               "network_untrained": True, "calibration_qualified": False}
                        row.update({f"failure_{reason}": count for reason, count in failures[method].items() if reason != "valid"})
                        rows.append(row)
            print(f"Completed fixed half-contrast adapter: {reference}", flush=True)

        table = pd.DataFrame(rows)
        failure_columns = [column for column in table if column.startswith("failure_")]
        table[failure_columns] = table[failure_columns].fillna(0).astype(int)
        table.to_csv(OUT / "per_pillar_measurements.csv", index=False, mode="x")
        pd.DataFrame(parity_rows).to_csv(OUT / "raw_readout_parity.csv", index=False, mode="x")
        aggregates = []
        for (reference, exposure, method), subset in table.groupby(["reference", "exposure", "method"], sort=False):
            aggregates.append({"reference": reference, "exposure": int(exposure), "method": method,
                               "pillars": int(len(subset)), "total_profiles": int(subset.total_profiles.sum()),
                               "valid_profiles": int(subset.valid_profiles.sum()), "invalid_profiles": int(subset.invalid_profiles.sum()),
                               "common_profiles": int(subset.common_profiles.sum()), "minimum_common_profiles_per_pillar": int(subset.common_profiles.min()),
                               "median_common_profiles_per_pillar": float(subset.common_profiles.median()),
                               "pillars_with_at_least90pct_common": int((subset.common_profiles >= 648).sum()),
                               "median_pillar_common_mae_px": float(subset.common_mean_absolute_error_px.median()),
                               "median_pillar_common_signed_error_px": float(subset.common_median_signed_error_px.median()),
                               "worst_pillar_common_mae_px": float(subset.common_mean_absolute_error_px.max()),
                               "worst_common_normal_absolute_error_px": float(subset.common_max_absolute_error_px.max()),
                               "median_pillar_mae_change_vs_Raw_px": float(subset.common_mean_absolute_difference_from_Raw_error_px.median()),
                               "interpretation": "Untrained diagnostic output vs reused digital SEM reference; no qualified physical-accuracy claim"})
        pd.DataFrame(aggregates).to_csv(OUT / "exposure_summary.csv", index=False, mode="x")
        save("geometry_calibration.json", geometry_rows)

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        figure, axes = plt.subplots(2, 2, figsize=(11, 8), sharey=True)
        for row_index, reference in enumerate(REFERENCES):
            for column_index, exposure in enumerate(EXPOSURES):
                axis = axes[row_index, column_index]
                subset = table[(table.reference == reference) & (table.exposure == exposure)]
                values = subset.pivot(index="pillar", columns="method", values="common_mean_absolute_error_px")[list(METHODS)]
                for values_row in values.to_numpy():
                    axis.plot(range(3), values_row, color="0.75", alpha=0.5, linewidth=0.65)
                axis.plot(range(3), values.median().to_numpy(), "o-", color="#1f5b8f", linewidth=2, label="Median of 36 objects")
                axis.set_xticks(range(3), ["Raw", "Identity\nassumption", "Gaussian\nassumption"])
                axis.set_title(f"{reference} / exposure {exposure}")
                axis.set_ylabel("Half-contrast distance to digital SEM (px)")
                axis.grid(axis="y", alpha=0.2)
        figure.suptitle("UNTRAINED SEM-linked readout adapter\nFixed Raw alignment, Raw plateaus, common valid normals; no qualified optics", fontsize=12)
        figure.tight_layout(rect=(0, 0, 1, 0.94))
        figure.savefig(OUT / "untrained_sem_half_readout.png", dpi=160)
        plt.close(figure)

        after = [dict(item, after_sha256=sha256(Path(item["path"]))) for item in protected]
        unchanged = all(item["sha256"] == item["after_sha256"] for item in after)
        save("protected_inputs_after.json", {"unchanged": unchanged, "files": after})
        if not unchanged:
            raise RuntimeError("Protected sources changed during adapter execution")
        save("summary.json", {
            "status": "untrained_sem_readout_adapter_complete", "completed_utc": now(), "elapsed_seconds": time.perf_counter() - started,
            "measurements": len(rows), "raw_parity_cases": len(parity_rows), "raw_validity_exact": all(row["validity_equal"] for row in parity_rows),
            "maximum_Raw_per_normal_parity_difference_px": max(row["max_normal_error_difference_px"] for row in parity_rows),
            "maximum_Raw_table_mae_difference_px": max(row["mae_table_difference_px"] for row in parity_rows),
            "maximum_independent_crossing_difference_px": independent_max_error,
            "source_pixel_checks": input_checks, "protected_inputs_count": len(protected), "protected_inputs_unchanged": unchanged,
            "network_untrained": True, "calibration_qualified": False, "uncertainty_calibrated": False,
            "learned_efficacy_evaluated": False, "full_ACM_evaluated": False, "physical_accuracy_qualified": False,
            "interpretation": "Adapter connects actual untrained native outputs to a reproducible existing real SEM-linked readout; values are diagnostic",
            "exposure_results": aggregates,
        })
        print(f"Saved {len(rows)} measurements with {len(parity_rows)} exact-population Raw parity checks: {OUT}", flush=True)
    except BaseException as error:
        save("failure.json", {"status": "failed", "utc": now(), "error": str(error), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    main()
