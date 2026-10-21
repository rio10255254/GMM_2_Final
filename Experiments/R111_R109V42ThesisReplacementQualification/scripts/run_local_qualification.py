"""Run R109 E48 through the frozen V42 thesis measurement contract."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "qualification.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
RESULTS = ROOT / "results"

EVIDENCE = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence")
R109_ROOT = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")
R109_INFERENCE = R109_ROOT / "inference" / "run_folder.py"
R109_CHECKPOINT = Path(CONFIG["models"]["r109_e48"]["checkpoint"])
V42_CHECKPOINT = Path(CONFIG["models"]["v42_e120"]["checkpoint"])
THESIS_CENTER9 = EVIDENCE / "Final_Data_Figures" / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
THESIS_RESULTS = EVIDENCE / "Final_Data_Figures" / "04_V42_NEURAL_NETWORK_RESULTS"
V42_SOURCE = EVIDENCE / "Final_Data_Figures" / "02_V42_E120_SOURCE_MATERIAL"

RAW_STATIC = EVIDENCE / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
V42_STATIC = V42_SOURCE / "reconstructions" / "100mg_static" / RAW_STATIC.name
R109_STATIC_DIR = RESULTS / "reconstructions" / "100mg_static"
R109_STATIC = R109_STATIC_DIR / RAW_STATIC.name

THESIS_SEQUENCE_CONFIG = Path(CONFIG["frozen_contract"]["sequence_config"])
TOP30_SELECTION = Path(CONFIG["frozen_contract"]["top30_selection"])
THESIS_RAW_LOCK = Path(CONFIG["frozen_contract"]["raw_lock"])
THESIS_AUDIT = THESIS_CENTER9 / "diagnostics" / "unified_displacement_step_audit"
THESIS_ALL_PAIRS = THESIS_AUDIT / "tables" / "all_adjacent_pairs_audit.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def truthy(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    return values.astype(str).str.lower().isin({"true", "1", "yes"})


def validate_frozen_inputs() -> dict[str, object]:
    records: dict[str, object] = {}
    checks = {
        "r109_checkpoint": (R109_CHECKPOINT, CONFIG["models"]["r109_e48"]["sha256"]),
        "v42_checkpoint": (V42_CHECKPOINT, CONFIG["models"]["v42_e120"]["sha256"]),
        "sequence_config": (THESIS_SEQUENCE_CONFIG, CONFIG["frozen_contract"]["sequence_config_sha256"]),
        "top30_selection": (TOP30_SELECTION, CONFIG["frozen_contract"]["top30_selection_sha256"]),
        "raw_lock": (THESIS_RAW_LOCK, CONFIG["frozen_contract"]["raw_lock_sha256"]),
    }
    for name, (path, expected) in checks.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Frozen input hash mismatch for {name}: {actual}")
        records[name] = {"path": str(path), "sha256": actual, "bytes": path.stat().st_size}

    selection = pd.read_csv(TOP30_SELECTION)
    selected = selection.loc[truthy(selection["top30_raw_motion_selected"])].copy()
    counts = selected.groupby("sequence").size().to_dict()
    expected_counts = {"50x_x_0p5um": 30, "50x_x_1um": 30, "20x_0p5um": 30, "20x_1um": 30}
    if counts != expected_counts:
        raise RuntimeError(f"Frozen top-30 population changed: {counts}")
    records["selected_step_counts"] = counts

    sequence_config = json.loads(THESIS_SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    for sequence, directory in CONFIG["r109_reconstructions"].items():
        expected = int(sequence_config["sequences"][sequence]["frame_count"])
        folder = Path(directory)
        names = sorted(path.name for path in folder.glob("frame_*.bmp"))
        expected_names = [f"frame_{index:04d}.bmp" for index in range(expected)]
        if names != expected_names:
            raise RuntimeError(f"R109 reconstruction set mismatch for {sequence}")
        records[f"r109_{sequence}"] = {"path": str(folder), "frames": len(names)}
    return records


def ensure_static_reconstruction() -> dict[str, object]:
    R109_STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if not R109_STATIC.is_file():
        command = [
            sys.executable,
            str(R109_INFERENCE),
            "--checkpoint",
            str(R109_CHECKPOINT),
            "--input",
            str(RAW_STATIC),
            "--output",
            str(R109_STATIC_DIR),
            "--device",
            "cuda:0",
            "--core",
            "1024",
            "--halo",
            "192",
        ]
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
        (ROOT / "logs" / "static_inference_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (ROOT / "logs" / "static_inference_stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"R109 static inference failed with code {completed.returncode}")
    if not R109_STATIC.is_file():
        raise FileNotFoundError(R109_STATIC)
    import cv2

    raw = cv2.imread(str(RAW_STATIC), cv2.IMREAD_GRAYSCALE)
    output = cv2.imread(str(R109_STATIC), cv2.IMREAD_GRAYSCALE)
    if raw is None or output is None or raw.shape != output.shape:
        raise RuntimeError("Static reconstruction shape/read check failed")
    return {
        "raw": str(RAW_STATIC),
        "r109": str(R109_STATIC),
        "shape": list(output.shape),
        "raw_sha256": sha256(RAW_STATIC),
        "r109_sha256": sha256(R109_STATIC),
        "mean_abs_change_gray": float(np.mean(np.abs(output.astype(np.float32) - raw.astype(np.float32)))),
    }


def build_r109_sequence_config() -> Path:
    config = json.loads(THESIS_SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    config["candidate_model"] = "R109 E48"
    config["source_contract_sha256"] = sha256(THESIS_SEQUENCE_CONFIG)
    for sequence, directory in CONFIG["r109_reconstructions"].items():
        config["sequences"][sequence]["v42_dir"] = str(Path(directory)).replace("\\", "/")
    output = ROOT / "config" / "r109_thesis_sequence_config.json"
    output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def run_displacement_audit() -> tuple[Path, dict[str, object]]:
    scripts = THESIS_CENTER9 / "scripts"
    sys.path.insert(0, str(scripts))
    audit = load_module(scripts / "audit_all_displacement_sequences.py", "r111_displacement_audit")
    output = RESULTS / "thesis_displacement_r109"
    config_path = build_r109_sequence_config()
    paths = audit.run_unified_audit(output_root=output, candidate_root=output / "candidate", config_path=config_path)
    new_raw_lock = Path(paths["raw_lock"])
    new_hash = sha256(new_raw_lock)
    expected_hash = sha256(THESIS_RAW_LOCK)
    if new_hash != expected_hash:
        raise RuntimeError(f"Raw lock changed under R109 audit: {new_hash} != {expected_hash}")
    return output, {
        "raw_lock_sha256": new_hash,
        "matches_thesis_raw_lock": True,
        "audit_pairs": str(paths["pairs"]),
        "candidate_table": str(paths["candidate_table"]),
    }


def summarize_displacement(r109_audit_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    selection = pd.read_csv(TOP30_SELECTION)
    selection = selection.loc[truthy(selection["top30_raw_motion_selected"])].copy()
    keys = ["sequence", "end_frame_index"]
    v42 = pd.read_csv(THESIS_ALL_PAIRS)
    r109 = pd.read_csv(r109_audit_root / "tables" / "all_adjacent_pairs_audit.csv")

    v42_fields = keys + [
        "magnification", "nominal_step_um", "raw_boundary_dx_um", "raw_within_grid_nm",
        "raw_boundary_valid_pillars", "v42_evaluable", "v42_boundary_dx_um",
        "v42_within_grid_nm", "v42_boundary_valid_pillars",
    ]
    r109_fields = keys + [
        "raw_boundary_dx_um", "raw_within_grid_nm", "v42_evaluable",
        "v42_failure_reason", "v42_boundary_dx_um", "v42_within_grid_nm",
        "v42_boundary_valid_pillars",
    ]
    table = selection[keys + ["raw_motion_quality_rank"]].merge(
        v42[v42_fields], on=keys, how="left", validate="one_to_one"
    )
    r109_part = r109[r109_fields].rename(
        columns={
            "raw_boundary_dx_um": "r109_audit_raw_boundary_dx_um",
            "raw_within_grid_nm": "r109_audit_raw_within_grid_nm",
            "v42_evaluable": "r109_evaluable",
            "v42_failure_reason": "r109_failure_reason",
            "v42_boundary_dx_um": "r109_boundary_dx_um",
            "v42_within_grid_nm": "r109_within_grid_nm",
            "v42_boundary_valid_pillars": "r109_boundary_valid_pillars",
        }
    )
    table = table.merge(r109_part, on=keys, how="left", validate="one_to_one")
    if len(table) != 120:
        raise RuntimeError(f"Expected 120 frozen steps, found {len(table)}")
    raw_dx_difference = np.max(np.abs(table["raw_boundary_dx_um"] - table["r109_audit_raw_boundary_dx_um"]))
    raw_grid_difference = np.max(np.abs(table["raw_within_grid_nm"] - table["r109_audit_raw_within_grid_nm"]))
    if raw_dx_difference > 1e-12 or raw_grid_difference > 1e-9:
        raise RuntimeError("Raw measurements differ between V42 and R109 audits")
    if not truthy(table["v42_evaluable"]).all():
        raise RuntimeError("A frozen V42 step is not evaluable")

    summary_rows: list[dict[str, object]] = []
    groups = [(name, group) for name, group in table.groupby("sequence", sort=False)]
    groups.append(("All paired steps", table))
    for name, group in groups:
        row: dict[str, object] = {"population": name, "step_count": int(len(group))}
        nominal = group["nominal_step_um"].to_numpy(dtype=float)
        for method, dx_column, within_column, evaluable in (
            ("raw", "raw_boundary_dx_um", "raw_within_grid_nm", np.ones(len(group), dtype=bool)),
            ("v42", "v42_boundary_dx_um", "v42_within_grid_nm", truthy(group["v42_evaluable"]).to_numpy()),
            ("r109", "r109_boundary_dx_um", "r109_within_grid_nm", truthy(group["r109_evaluable"]).to_numpy()),
        ):
            magnitude = np.abs(group[dx_column].to_numpy(dtype=float))
            within = group[within_column].to_numpy(dtype=float)
            valid = evaluable & np.isfinite(magnitude) & np.isfinite(within)
            row[f"{method}_evaluable_count"] = int(valid.sum())
            row[f"{method}_mean_magnitude_um"] = float(np.mean(magnitude[valid])) if valid.any() else np.nan
            row[f"{method}_step_sd_nm"] = float(np.std(magnitude[valid] - nominal[valid], ddof=1) * 1000.0) if valid.sum() > 1 else np.nan
            row[f"{method}_command_mae_nm"] = float(np.mean(np.abs(magnitude[valid] - nominal[valid])) * 1000.0) if valid.any() else np.nan
            row[f"{method}_within_mean_nm"] = float(np.mean(within[valid])) if valid.any() else np.nan
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)

    paired = table.copy()
    for method, dx_column, within_column in (
        ("raw", "raw_boundary_dx_um", "raw_within_grid_nm"),
        ("v42", "v42_boundary_dx_um", "v42_within_grid_nm"),
        ("r109", "r109_boundary_dx_um", "r109_within_grid_nm"),
    ):
        paired[f"{method}_magnitude_um"] = paired[dx_column].abs()
        paired[f"{method}_command_abs_error_nm"] = (
            paired[f"{method}_magnitude_um"] - paired["nominal_step_um"]
        ).abs() * 1000.0
        paired[f"{method}_within_nm"] = paired[within_column]
    paired["r109_better_command_than_v42"] = paired["r109_command_abs_error_nm"] < paired["v42_command_abs_error_nm"]
    paired["r109_better_within_than_v42"] = paired["r109_within_nm"] < paired["v42_within_nm"]

    all_row = summary.loc[summary["population"] == "All paired steps"].iloc[0]
    qa = {
        "frozen_steps": 120,
        "r109_evaluable_steps": int(truthy(table["r109_evaluable"]).sum()),
        "r109_failure_reasons": table.loc[~truthy(table["r109_evaluable"]), "r109_failure_reason"].value_counts().to_dict(),
        "raw_recomputed_max_dx_difference_um": float(raw_dx_difference),
        "raw_recomputed_max_within_difference_nm": float(raw_grid_difference),
        "r109_better_command_than_v42_count": int(paired["r109_better_command_than_v42"].sum()),
        "r109_better_within_than_v42_count": int(paired["r109_better_within_than_v42"].sum()),
        "v42_command_mae_nm": float(all_row["v42_command_mae_nm"]),
        "r109_command_mae_nm": float(all_row["r109_command_mae_nm"]),
        "v42_within_mean_nm": float(all_row["v42_within_mean_nm"]),
        "r109_within_mean_nm": float(all_row["r109_within_mean_nm"]),
    }
    output = RESULTS / "thesis_displacement_comparison"
    output.mkdir(parents=True, exist_ok=True)
    paired.to_csv(output / "frozen_120_steps.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output / "summary.csv", index=False, encoding="utf-8-sig")
    (output / "qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return paired, summary, qa


def build_cd_tables() -> dict[str, object]:
    analysis_script = THESIS_RESULTS / "scripts" / "analyze_wiener_three_way_results.py"
    module = load_module(analysis_script, "r111_cd_methods")
    source = pd.read_csv(THESIS_CENTER9 / "cd" / "tables" / "center9_cd_per_pillar.csv")
    case_paths = {"raw": RAW_STATIC, "v42_e120": V42_STATIC, "r109_e48": R109_STATIC}
    labels = {"raw": "Raw", "v42_e120": "V42 epoch 120", "r109_e48": "R109 epoch 48"}
    images = {case: module._read_gray(path) for case, path in case_paths.items()}
    output = source[
        [
            "center9_position", "sem_index", "sem_excel_cell", "optical_grid_row",
            "optical_grid_col", "capture_transform", "sem_radius_nm", "sem_diameter_um",
            "raw_x_px", "raw_y_px", "reference_radius_px",
        ]
    ].copy()

    for case, image in images.items():
        results = [
            module._measure_half_height_width(
                image, float(row.raw_x_px), float(row.raw_y_px), float(row.reference_radius_px), 0.5
            )
            for row in source.itertuples(index=False)
        ]
        output[f"{case}_status"] = [str(item["status"]) for item in results]
        output[f"{case}_left_edge_px"] = [float(item.get("left_edge_px", np.nan)) for item in results]
        output[f"{case}_right_edge_px"] = [float(item.get("right_edge_px", np.nan)) for item in results]
        output[f"{case}_diameter_um"] = np.asarray([float(item.get("width_px", np.nan)) for item in results]) * 0.069
        output[f"{case}_signed_error_nm"] = (output[f"{case}_diameter_um"] - output["sem_diameter_um"]) * 1000.0
        output[f"{case}_abs_error_nm"] = output[f"{case}_signed_error_nm"].abs()
    if not all((output[f"{case}_status"] == "ok").all() for case in case_paths):
        raise RuntimeError("At least one R111 center-nine 50% crossing failed")
    raw_difference = float(np.max(np.abs(output["raw_diameter_um"] - source["raw_diameter_um"])))
    v42_difference = float(np.max(np.abs(output["v42_e120_diameter_um"] - source["v42_e120_diameter_um"])))
    if raw_difference > 1e-6 or v42_difference > 1e-6:
        raise RuntimeError(f"CD method reproduction mismatch: Raw={raw_difference}, V42={v42_difference}")

    records: list[dict[str, object]] = []
    raw_mae = float(output["raw_abs_error_nm"].mean())
    for case, label in labels.items():
        signed = output[f"{case}_signed_error_nm"].to_numpy(dtype=float)
        absolute = np.abs(signed)
        mae = float(np.mean(absolute))
        records.append(
            {
                "case": case,
                "case_label": label,
                "pillar_count": len(output),
                "mean_diameter_um": float(output[f"{case}_diameter_um"].mean()),
                "mean_abs_error_nm": mae,
                "median_abs_error_nm": float(np.median(absolute)),
                "rmse_nm": float(np.sqrt(np.mean(signed**2))),
                "mean_signed_bias_nm": float(np.mean(signed)),
                "max_abs_error_nm": float(np.max(absolute)),
                "improved_vs_raw_count": int((absolute < output["raw_abs_error_nm"].to_numpy(dtype=float)).sum()) if case != "raw" else 0,
                "mean_abs_improvement_nm": raw_mae - mae,
                "mean_abs_improvement_pct": (raw_mae - mae) / raw_mae * 100.0,
            }
        )
    nominal_summary = pd.DataFrame(records)

    sensitivity_rows: list[dict[str, object]] = []
    thresholds = np.round(np.arange(0.35, 0.651, 0.05), 2)
    modes = {"horizontal_strip": module._measure_half_height_width, "radial_mean": module._measure_radial_width}
    for mode, measure in modes.items():
        for threshold in thresholds:
            for case, image in images.items():
                for row in source.itertuples(index=False):
                    result = measure(image, float(row.raw_x_px), float(row.raw_y_px), float(row.reference_radius_px), float(threshold))
                    diameter = float(result.get("width_px", np.nan)) * 0.069
                    signed = (diameter - float(row.sem_diameter_um)) * 1000.0
                    sensitivity_rows.append(
                        {
                            "measurement_mode": mode,
                            "threshold_fraction": float(threshold),
                            "case": case,
                            "case_label": labels[case],
                            "center9_position": int(row.center9_position),
                            "sem_index": int(row.sem_index),
                            "sem_diameter_um": float(row.sem_diameter_um),
                            "diameter_um": diameter,
                            "signed_error_nm": signed,
                            "abs_error_nm": abs(signed),
                            "status": str(result["status"]),
                        }
                    )
    sensitivity = pd.DataFrame(sensitivity_rows)
    if len(sensitivity) != 3 * 2 * 7 * 9 or not (sensitivity["status"] == "ok").all():
        raise RuntimeError("Threshold-robust CD table is incomplete")

    sensitivity_summary = (
        sensitivity.groupby(["measurement_mode", "threshold_fraction", "case", "case_label"], as_index=False)
        .agg(
            pillar_count=("sem_index", "count"),
            mean_abs_error_nm=("abs_error_nm", "mean"),
            median_abs_error_nm=("abs_error_nm", "median"),
            rmse_nm=("signed_error_nm", lambda values: float(np.sqrt(np.mean(np.square(values))))),
            mean_signed_bias_nm=("signed_error_nm", "mean"),
            max_abs_error_nm=("abs_error_nm", "max"),
        )
    )
    per_pillar = (
        sensitivity.groupby(["case", "case_label", "center9_position", "sem_index"], as_index=False)
        .agg(
            sensitivity_check_count=("abs_error_nm", "count"),
            median_abs_error_nm=("abs_error_nm", "median"),
            mean_abs_error_nm=("abs_error_nm", "mean"),
            max_abs_error_nm=("abs_error_nm", "max"),
        )
    )
    robust_rows: list[dict[str, object]] = []
    raw_median = float(sensitivity.loc[sensitivity["case"] == "raw", "abs_error_nm"].median())
    for (case, label), group in sensitivity.groupby(["case", "case_label"], sort=False):
        signed = group["signed_error_nm"].to_numpy(dtype=float)
        absolute = np.abs(signed)
        pillar_medians = group.groupby("sem_index")["abs_error_nm"].median()
        pooled_median = float(np.median(absolute))
        robust_rows.append(
            {
                "case": case,
                "case_label": label,
                "measurement_mode_count": 2,
                "threshold_count": 7,
                "pillar_count": 9,
                "sensitivity_observation_count": len(group),
                "pooled_median_abs_error_nm": pooled_median,
                "pooled_mean_abs_error_nm": float(np.mean(absolute)),
                "mean_of_pillar_median_abs_error_nm": float(pillar_medians.mean()),
                "pooled_rmse_nm": float(np.sqrt(np.mean(signed**2))),
                "pooled_mean_signed_bias_nm": float(np.mean(signed)),
                "median_abs_improvement_vs_raw_nm": raw_median - pooled_median,
                "median_abs_improvement_vs_raw_pct": (raw_median - pooled_median) / raw_median * 100.0,
            }
        )
    robust_summary = pd.DataFrame(robust_rows)

    thesis_nominal = pd.read_csv(THESIS_RESULTS / "tables" / "cd_50pct_nominal_summary.csv")
    thesis_robust = pd.read_csv(THESIS_RESULTS / "tables" / "cd_threshold_robust_summary.csv")
    for case in ("raw", "v42_e120"):
        ours = nominal_summary.loc[nominal_summary["case"] == case, "mean_abs_error_nm"].iloc[0]
        theirs = thesis_nominal.loc[thesis_nominal["case"] == case, "mean_abs_error_nm"].iloc[0]
        if abs(float(ours) - float(theirs)) > 1e-6:
            raise RuntimeError(f"Nominal CD mismatch for {case}")
        ours_robust = robust_summary.loc[robust_summary["case"] == case, "pooled_median_abs_error_nm"].iloc[0]
        theirs_robust = thesis_robust.loc[thesis_robust["case"] == case, "pooled_median_abs_error_nm"].iloc[0]
        if abs(float(ours_robust) - float(theirs_robust)) > 1e-6:
            raise RuntimeError(f"Robust CD mismatch for {case}")

    destination = RESULTS / "thesis_cd_comparison"
    destination.mkdir(parents=True, exist_ok=True)
    output.to_csv(destination / "cd_50pct_per_pillar.csv", index=False, encoding="utf-8-sig")
    nominal_summary.to_csv(destination / "cd_50pct_summary.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(destination / "cd_threshold_measurements.csv", index=False, encoding="utf-8-sig")
    sensitivity_summary.to_csv(destination / "cd_threshold_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    per_pillar.to_csv(destination / "cd_threshold_robust_per_pillar.csv", index=False, encoding="utf-8-sig")
    robust_summary.to_csv(destination / "cd_threshold_robust_summary.csv", index=False, encoding="utf-8-sig")
    return {
        "raw_reproduction_max_difference_um": raw_difference,
        "v42_reproduction_max_difference_um": v42_difference,
        "nominal_summary": nominal_summary.to_dict(orient="records"),
        "robust_summary": robust_summary.to_dict(orient="records"),
    }


def run_circular_edge_validation() -> dict[str, object]:
    source_root = THESIS_RESULTS / "modern_baseline_three_morphology_20260719"
    source_script = source_root / "source_scripts" / "analyze_circular_cd_sharpness.py"
    source_manifest = json.loads((source_root / "source_manifest.json").read_text(encoding="utf-8"))
    source_manifest["methods"] = {
        "Raw": {"kind": "measurement", "sequence_root": ""},
        "V42 E120": {"kind": "thesis_results_model", "sequence_root": str(V42_SOURCE / "reconstructions").replace("\\", "/")},
        "R109 E48": {"kind": "replacement_candidate", "sequence_root": str(R109_ROOT / "results" / "posttraining_motion" / "E048" / "reconstructions").replace("\\", "/")},
    }
    source_manifest["sequence_name_map"] = {
        "50x_x_0p5um": {"Raw": "50x_x_0p5um", "V42 E120": "50x_0p5um", "R109 E48": "50x_0p5um"},
        "50x_x_1um": {"Raw": "50x_x_1um", "V42 E120": "50x_1um", "R109 E48": "50x_1um"},
        "20x_0p5um": {"Raw": "20x_0p5um", "V42 E120": "20x_0p5um", "R109 E48": "20x_0p5um"},
        "20x_1um": {"Raw": "20x_1um", "V42 E120": "20x_1um", "R109 E48": "20x_1um"},
    }
    manifest_path = ROOT / "config" / "circular_edge_manifest.json"
    manifest_path.write_text(json.dumps(source_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    module = load_module(source_script, "r111_circular_edge")
    module.MANIFEST_PATH = manifest_path
    output = RESULTS / "circular_edge_comparison"
    module.main(output, allow_missing=False)
    detailed = pd.read_csv(output / "circular_feature_threshold_measurements.csv")
    summary = pd.read_csv(output / "circular_feature_method_summary.csv")
    expected = 2 * 2 * 3 * 9 * 7
    if len(detailed) != expected:
        raise RuntimeError(f"Circular validation expected {expected} rows, got {len(detailed)}")
    return {"rows": len(detailed), "summary": summary.to_dict(orient="records")}


def run_line_validation() -> dict[str, object]:
    source_script = (
        THESIS_RESULTS
        / "source_validation"
        / "100mg_linewidth_generalization_20260719"
        / "scripts"
        / "analyze_100mg_linewidth_generalization.py"
    )
    module = load_module(source_script, "r111_line_validation")
    output = RESULTS / "line_pattern_comparison"
    module.OUTPUT = output
    module.TABLES = output / "tables"
    module.CROPS = output / "images"
    module.METHODS = ("Raw", "Base U-Net", "MOSR")
    r109_sequence_root = R109_ROOT / "results" / "posttraining_motion" / "E048" / "reconstructions"
    module.SEQUENCES = {
        "50x_x_0p5um": {
            "nominal_step_um": 0.5,
            "raw": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp"),
            "base": V42_SOURCE / "reconstructions" / "50x_0p5um",
            "mosr": r109_sequence_root / "50x_0p5um",
        },
        "50x_x_1um": {
            "nominal_step_um": 1.0,
            "raw": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_1um\bmp"),
            "base": V42_SOURCE / "reconstructions" / "50x_1um",
            "mosr": r109_sequence_root / "50x_1um",
        },
    }
    module.main()
    label_map = {"Base U-Net": "V42 E120", "MOSR": "R109 E48"}
    for csv_path in (output / "tables").glob("*.csv"):
        table = pd.read_csv(csv_path, encoding="utf-8-sig")
        for column in ("method", "reference_method", "target_method"):
            if column in table.columns:
                table[column] = table[column].replace(label_map)
        table.to_csv(csv_path, index=False, encoding="utf-8-sig")
    generated_manifest = output / "manifest.json"
    internal_manifest = output / "internal_execution_manifest.json"
    if generated_manifest.is_file():
        shutil.move(str(generated_manifest), str(internal_manifest))
    comparison_manifest = {
        "purpose": "Exact thesis line-pattern methods with V42 E120 and R109 E48 on the same Raw-locked 60 steps",
        "methods": ["Raw", "V42 E120", "R109 E48"],
        "label_mapping_during_reused_execution": {"Base U-Net": "V42 E120", "MOSR": "R109 E48"},
        "selection": str(TOP30_SELECTION),
        "selection_sha256": sha256(TOP30_SELECTION),
        "r109_training_overlap": False,
        "v42_same_capture_family_in_training": True,
    }
    generated_manifest.write_text(json.dumps(comparison_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sharpness = pd.read_csv(output / "tables" / "line_sharpness_summary.csv", encoding="utf-8-sig")
    displacement = pd.read_csv(output / "tables" / "line_displacement_pooled.csv", encoding="utf-8-sig")
    return {"sharpness": sharpness.to_dict(orient="records"), "displacement": displacement.to_dict(orient="records")}


def collect_shared_sem() -> dict[str, object]:
    r109 = json.loads((R109_ROOT / "results" / "FINAL_SELECTION.json").read_text(encoding="utf-8"))["external_acm"]["SEM_per_pillar"]
    v42_table = pd.read_csv(
        Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation\results\tables\v42_paired_comparison_summary.csv")
    )
    values = {
        row.metric: float(row.target_median)
        for row in v42_table.loc[v42_table["comparison"] == "Raw_to_V42E120"].itertuples(index=False)
    }
    return {
        "same_36_pillars_12_exposures": True,
        "v42": {
            "iou": values["iou"],
            "mean_boundary_distance_pitch_pct": values["mean_boundary_distance_pitch_pct"],
            "area_error_pct": values["area_error_pct"],
            "perimeter_error_pct": values["perimeter_error_pct"],
        },
        "r109": {
            "iou": r109["model_iou"],
            "mean_boundary_distance_pitch_pct": r109["model_boundary_pitch_pct"],
            "area_error_pct": r109["model_area_error_pct"],
            "perimeter_error_pct": r109["model_perimeter_error_pct"],
        },
    }


def build_local_summary(
    frozen: dict[str, object],
    static: dict[str, object],
    displacement_qa: dict[str, object],
    cd: dict[str, object],
    circular: dict[str, object],
    line: dict[str, object],
) -> dict[str, object]:
    summary = {
        "status": "local_qualification_complete_external_v42_gmf_pending",
        "generated_local": datetime.now().astimezone().isoformat(),
        "frozen_inputs": frozen,
        "static_reconstruction": static,
        "thesis_displacement": displacement_qa,
        "thesis_cd": cd,
        "circular_edge": circular,
        "line_pattern": line,
        "shared_sem_acm": collect_shared_sem(),
        "tile_parity": json.loads(
            Path(
                r"D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages"
                r"\Pitch1um_Y_100_Raw_Even_R109E48\_records\qa_report.json"
            ).read_text(encoding="utf-8")
        )["tile_grid_parity"],
        "external_gmf": {
            "r109": "complete",
            "v42": "pending package and external coordinates",
            "replacement_decision": "blocked_until_same_101_frame_v42_gmf",
        },
    }
    (RESULTS / "local_qualification_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    frozen = validate_frozen_inputs()
    static = ensure_static_reconstruction()
    audit_root, audit_qa = run_displacement_audit()
    _, _, displacement_qa = summarize_displacement(audit_root)
    displacement_qa.update(audit_qa)
    cd = build_cd_tables()
    circular = run_circular_edge_validation()
    line = run_line_validation()
    summary = build_local_summary(frozen, static, displacement_qa, cd, circular, line)
    print(json.dumps({"status": summary["status"], "summary": str(RESULTS / "local_qualification_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
