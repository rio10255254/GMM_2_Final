from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parent
EVIDENCE = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures")
CURRENT = EVIDENCE / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
NETWORK = EVIDENCE / "04_V42_NEURAL_NETWORK_RESULTS"
SCRIPT_ROOT = CURRENT / "scripts"

sys.path.insert(0, str(SCRIPT_ROOT))
from audit_all_displacement_sequences import run_unified_audit  # noqa: E402


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def truthy(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def run_control(output_root: Path, sigmas: list[float]) -> None:
    source_config_path = CURRENT / "config" / "sequence_center9_50x20x.json"
    source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
    selection = pd.read_csv(NETWORK / "tables" / "top30_raw_motion_selection.csv")
    selection = selection.loc[truthy(selection.top30_raw_motion_selected), [
        "sequence",
        "end_frame_index",
    ]]
    if len(selection) != 120:
        raise RuntimeError(f"Expected 120 locked displacement steps, found {len(selection)}")

    summary_rows: list[dict] = []
    per_step_rows: list[pd.DataFrame] = []
    for sigma in sigmas:
        sigma_label = str(sigma).replace(".", "p")
        sigma_root = output_root / f"sigma_{sigma_label}"
        reconstruction_root = sigma_root / "reconstruction"
        config = json.loads(json.dumps(source_config))
        for sequence_name, sequence in config["sequences"].items():
            raw_dir = Path(sequence["raw_dir"])
            destination = reconstruction_root / sequence_name
            expected = int(sequence["frame_count"])
            inputs = sorted(raw_dir.glob("frame_*.bmp"))
            if len(inputs) != expected:
                raise RuntimeError(
                    f"{sequence_name}: expected {expected} raw frames, found {len(inputs)}"
                )
            for input_path in inputs:
                image = read_gray(input_path)
                blurred = cv2.GaussianBlur(
                    image,
                    ksize=(0, 0),
                    sigmaX=sigma,
                    sigmaY=sigma,
                    borderType=cv2.BORDER_REFLECT_101,
                )
                write_bmp(destination / input_path.name, blurred)
            sequence["v42_dir"] = destination.as_posix()

        config["comparison_method"] = f"Raw Gaussian sigma={sigma:.2f} px"
        config_path = sigma_root / "smoothing_control_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        audit_root = sigma_root / "displacement_audit"
        run_unified_audit(
            output_root=audit_root,
            candidate_root=audit_root / "candidate",
            config_path=config_path,
        )
        audit = pd.read_csv(audit_root / "tables" / "all_adjacent_pairs_audit.csv")
        paired = selection.merge(
            audit,
            on=["sequence", "end_frame_index"],
            how="left",
            validate="one_to_one",
        )
        if len(paired) != 120 or not truthy(paired.v42_evaluable).all():
            raise RuntimeError(f"sigma={sigma}: locked top-30 population was not reproduced")
        paired["sigma_px"] = sigma
        paired["smoothed_reference_abs_error_nm"] = (
            (paired.v42_boundary_dx_um - paired.expected_signed_step_um).abs() * 1000.0
        )
        per_step_rows.append(
            paired[[
                "sigma_px",
                "sequence",
                "magnification",
                "nominal_step_um",
                "end_frame_index",
                "v42_boundary_dx_um",
                "v42_within_grid_nm",
                "smoothed_reference_abs_error_nm",
            ]].rename(
                columns={
                    "v42_boundary_dx_um": "smoothed_boundary_dx_um",
                    "v42_within_grid_nm": "smoothed_within_grid_nm",
                }
            )
        )
        summary_rows.append(
            {
                "sigma_px": sigma,
                "paired_step_count": int(len(paired)),
                "reference_mae_nm": float(paired.smoothed_reference_abs_error_nm.mean()),
                "nine_pillar_inconsistency_mean_nm": float(paired.v42_within_grid_nm.mean()),
                "nine_pillar_inconsistency_median_nm": float(paired.v42_within_grid_nm.median()),
                "all_evaluable": bool(truthy(paired.v42_evaluable).all()),
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summary_rows)
    per_step = pd.concat(per_step_rows, ignore_index=True)
    summary.to_csv(output_root / "gaussian_smoothing_displacement_summary.csv", index=False)
    per_step.to_csv(output_root / "gaussian_smoothing_displacement_per_step.csv", index=False)
    manifest = {
        "purpose": "Direct control for whether displacement stability can be explained by raw-image smoothing alone",
        "sigmas_px": sigmas,
        "locked_step_count_per_sigma": 120,
        "same_top30_selection": True,
        "same_measurement_rule": True,
        "summary": summary.to_dict(orient="records"),
    }
    (output_root / "gaussian_smoothing_control_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--sigmas", type=float, nargs="+", default=[0.5, 1.0, 1.5, 2.0])
    arguments = parser.parse_args()
    run_control(arguments.output_root.resolve(), arguments.sigmas)
