"""Locked six-sequence real displacement audit for R116 E24 and E48."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "results" / "detailed_validation" / "03_real_motion"
HELPER = Path(r"D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\scripts\evaluate_real_holdout.py")
CONFIG_PATH = Path(r"D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\config\sequences.json")
LOCKED = Path(r"D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\results\tables\tile_motion_measurements.csv")
R109_SUMMARY = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch\results\posttraining_motion\E048\motion_sequence_summary.csv")
R61_SUMMARY = Path(r"D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\results\tables\sequence_summary.csv")
CANDIDATES = {
    "R116_E024": ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_024.pth",
    "R116_E042": ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "failure_snapshot.pth",
    "R116_E048": ROOT / "runs" / "r116_calibration_from_e42_20260903_235500" / "weights" / "epoch_048.pth",
}

from inference.tiled import forward_tiled
from model.r116_model import build_model


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


helpers = load_module("r116_motion_helpers", HELPER)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bools(series: pd.Series) -> pd.Series:
    return series if series.dtype == bool else series.astype(str).str.lower().isin({"true", "1"})


def read(path: Path) -> np.ndarray:
    return helpers.read_gray(path)


def load_model(checkpoint: Path, device: torch.device):
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True:
        raise RuntimeError(f"Checkpoint is not scratch: {checkpoint}")
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False)
    return model.eval()


@torch.inference_mode()
def reconstruct(model, raw: np.ndarray, device: torch.device) -> np.ndarray:
    tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
    output = forward_tiled(model, tensor, core_size=1024, halo=224)
    return np.rint(output[0, 0].clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)


def reconstruct_all(name: str, checkpoint: Path, device: torch.device) -> tuple[Path, pd.DataFrame]:
    candidate_root = OUTPUT / name
    model = load_model(checkpoint, device)
    records = []
    appearance = []
    total = sum(int(item["frame_count"]) for item in CONFIG["sequences"].values())
    done = 0
    for sequence, item in CONFIG["sequences"].items():
        paths = sorted(Path(item["raw_dir"]).glob("frame_*.bmp"))
        if len(paths) != int(item["frame_count"]):
            raise RuntimeError(f"{sequence}: input inventory mismatch")
        for index, path in enumerate(paths):
            destination = candidate_root / "reconstructions" / sequence / path.name
            if destination.is_file():
                value = read(destination)
            else:
                raw = read(path)
                value = reconstruct(model, raw, device)
                helpers.write_gray(destination, value)
            raw = read(path)
            records.append({
                "candidate": name,
                "sequence": sequence,
                "frame_index": index,
                "source": str(path),
                "source_sha256": sha256(path),
                "output": str(destination),
                "output_sha256": sha256(destination),
            })
            appearance.append({
                "candidate": name,
                "sequence": sequence,
                "frame_index": index,
                **helpers.appearance_metrics(raw, value, 1024),
            })
            done += 1
            if done % 10 == 0 or done == total:
                print(json.dumps({"candidate": name, "done": done, "total": total, "sequence": sequence}), flush=True)
    del model
    torch.cuda.empty_cache()
    records_frame = pd.DataFrame(records)
    appearance_frame = pd.DataFrame(appearance)
    candidate_root.mkdir(parents=True, exist_ok=True)
    records_frame.to_csv(candidate_root / "reconstruction_manifest.csv", index=False, encoding="utf-8-sig")
    appearance_frame.to_csv(candidate_root / "appearance_per_frame.csv", index=False, encoding="utf-8-sig")
    appearance_frame.groupby("sequence").median(numeric_only=True).reset_index().to_csv(
        candidate_root / "appearance_sequence_summary.csv", index=False, encoding="utf-8-sig",
    )
    return candidate_root, records_frame


def evaluate_motion(name: str, candidate_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    locked = pd.read_csv(LOCKED)
    rows = []
    for _, row in locked.iterrows():
        sequence = str(row.sequence)
        step = int(row.step_index)
        first = read(candidate_root / "reconstructions" / sequence / f"frame_{step:04d}.bmp")
        second = read(candidate_root / "reconstructions" / sequence / f"frame_{step + 1:04d}.bmp")
        tile_h, tile_w = first.shape[0] // 6, first.shape[1] // 8
        y0, x0 = int(row.tile_row) * tile_h, int(row.tile_column) * tile_w
        before = first[y0:y0 + tile_h, x0:x0 + tile_w]
        after = second[y0:y0 + tile_h, x0:x0 + tile_w]
        phase_dx, phase_dy, response = helpers.phase_shift(before, after)
        try:
            dx, dy, ecc = helpers.bounded_ecc_shift(
                before, after, float(row.raw_dx_px), float(row.raw_dy_px),
            )
            finite = all(math.isfinite(value) for value in (dx, dy, ecc))
        except cv2.error:
            dx = dy = ecc = math.nan
            finite = False
        limit = max(12.0, abs(float(row.expected_dx_px)) * 2.5)
        evaluable = finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit
        raw_valid = str(row.raw_reference_valid).lower() in {"true", "1"}
        valid = bool(raw_valid and evaluable)
        rows.append({
            **row.to_dict(),
            "candidate": name,
            "candidate_phase_dx_px": phase_dx,
            "candidate_phase_dy_px": phase_dy,
            "candidate_response": response,
            "candidate_dx_px": dx,
            "candidate_dy_px": dy,
            "candidate_ecc": ecc,
            "candidate_evaluable": evaluable,
            "candidate_valid": valid,
            "candidate_direction_agreement": bool(valid and np.sign(dx) == np.sign(float(row.raw_dx_px))),
        })
    frame = pd.DataFrame(rows)
    frame["common_valid"] = bools(frame.raw_reference_valid) & bools(frame.candidate_valid)
    summaries = []
    decisions = []
    gates = CONFIG["gates"]
    for sequence, group in frame.groupby("sequence", sort=False):
        common = group[group.common_valid]
        scale = float(group.object_um_per_px.iloc[0])
        nominal = float(group.nominal_step_um.iloc[0])
        dx = common.candidate_dx_px.astype(float)
        dy = common.candidate_dy_px.astype(float)
        raw_dx = common.raw_dx_px.astype(float)
        raw_dy = common.raw_dy_px.astype(float)
        step = dx.abs() * scale
        raw_step = raw_dx.abs() * scale
        vector = np.hypot(
            dx.to_numpy() - raw_dx.to_numpy(), dy.to_numpy() - raw_dy.to_numpy(),
        ) * scale
        ratio = step / raw_step.clip(lower=1.0e-9)
        response_ratio = common.candidate_response.astype(float) / common.raw_response.astype(float).clip(lower=1.0e-9)
        valid_fraction = len(common) / max(int(bools(group.raw_reference_valid).sum()), 1)
        direction = float(bools(common.candidate_direction_agreement).mean()) if len(common) else 0.0
        summary = {
            "candidate": name,
            "sequence": sequence,
            "magnification": float(group.magnification.iloc[0]),
            "nominal_step_um": nominal,
            "common_measurements": len(common),
            "common_fraction_of_raw_reference": valid_fraction,
            "median_abs_dx_um": float(step.median()),
            "step_std_um": float(step.std(ddof=1)),
            "median_model_over_raw_abs_dx": float(ratio.median()),
            "median_scale_error_fraction": float(abs(ratio.median() - 1.0)),
            "median_vector_difference_from_raw_um": float(np.median(vector)),
            "p95_vector_difference_from_raw_um": float(np.quantile(vector, 0.95)),
            "median_response_ratio": float(response_ratio.median()),
            "median_ecc": float(common.candidate_ecc.median()),
            "direction_agreement": direction,
        }
        checks = {
            "valid_fraction": valid_fraction >= float(gates["minimum_valid_fraction"]),
            "direction": direction >= float(gates["minimum_direction_agreement"]),
            "scale": summary["median_scale_error_fraction"] <= float(gates["maximum_median_scale_error_fraction"]),
            "median_difference": summary["median_vector_difference_from_raw_um"] / nominal <= float(gates["maximum_median_difference_of_step"]),
            "p95_difference": summary["p95_vector_difference_from_raw_um"] / nominal <= float(gates["maximum_p95_difference_of_step"]),
            "response": summary["median_response_ratio"] >= float(gates["minimum_median_response_ratio"]),
            "ecc": summary["median_ecc"] >= float(gates["minimum_median_ecc"]),
        }
        summary["sequence_pass"] = all(checks.values())
        summaries.append(summary)
        decisions.append({"sequence": sequence, "pass": all(checks.values()), "checks": checks})
    summary_frame = pd.DataFrame(summaries)
    result = {
        "status": "complete",
        "candidate": name,
        "frames": sum(int(item["frame_count"]) for item in CONFIG["sequences"].values()),
        "measurements": len(frame),
        "all_sequences_pass": all(item["pass"] for item in decisions),
        "decisions": decisions,
    }
    return frame, summary_frame, result


def reference_rows() -> pd.DataFrame:
    rows = []
    r109 = pd.read_csv(R109_SUMMARY)
    for row in r109.itertuples(index=False):
        rows.append({
            "candidate": "R109_E048", "sequence": row.sequence,
            "magnification": row.magnification, "nominal_step_um": row.nominal_step_um,
            "common_fraction_of_raw_reference": row.common_fraction_of_raw_reference,
            "median_abs_dx_um": row.median_abs_dx_um, "step_std_um": row.step_std_um,
            "median_scale_error_fraction": row.median_scale_error_fraction,
            "median_vector_difference_from_raw_um": row.median_vector_difference_from_raw_um,
            "p95_vector_difference_from_raw_um": row.p95_vector_difference_from_raw_um,
            "median_response_ratio": row.median_response_ratio, "median_ecc": row.median_ecc,
            "direction_agreement": row.direction_agreement, "sequence_pass": True,
        })
    r61 = pd.read_csv(R61_SUMMARY)
    for row in r61.itertuples(index=False):
        rows.append({
            "candidate": "R61v16", "sequence": row.sequence,
            "magnification": row.magnification, "nominal_step_um": row.nominal_step_um,
            "common_fraction_of_raw_reference": row.valid_fraction,
            "median_abs_dx_um": row.r61_median_abs_dx_um, "step_std_um": math.nan,
            "median_scale_error_fraction": row.median_scale_error_fraction,
            "median_vector_difference_from_raw_um": row.median_vector_difference_um,
            "p95_vector_difference_from_raw_um": row.p95_vector_difference_um,
            "median_response_ratio": row.median_response_ratio, "median_ecc": row.median_r61_ecc,
            "direction_agreement": row.direction_agreement_fraction,
            "sequence_pass": str(row.sequence_pass).lower() in {"true", "1"},
        })
    return pd.DataFrame(rows)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0")
    summaries = []
    candidate_results = []
    for name, checkpoint in CANDIDATES.items():
        candidate_root = OUTPUT / name
        summary_path = candidate_root / "motion_sequence_summary.csv"
        result_path = candidate_root / "summary.json"
        if summary_path.is_file() and result_path.is_file():
            summary = pd.read_csv(summary_path)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            print(json.dumps({"candidate": name, "status": "reused_complete_motion"}), flush=True)
        else:
            candidate_root, _records = reconstruct_all(name, checkpoint, device)
            frame, summary, result = evaluate_motion(name, candidate_root)
            frame.to_csv(candidate_root / "motion_measurements.csv", index=False, encoding="utf-8-sig")
            summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
            result.update({"checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint)})
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        summaries.append(summary)
        candidate_results.append(result)
        print(json.dumps(result), flush=True)
    comparison = pd.concat([reference_rows(), *summaries], ignore_index=True, sort=False)
    comparison.to_csv(OUTPUT / "comparison_sequence_summary.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "complete",
        "population": "locked Raw-selected common-valid tile measurements",
        "raw_measurement_rows": int(len(pd.read_csv(LOCKED))),
        "candidates": candidate_results,
        "all_r116_sequences_pass": all(row["all_sequences_pass"] for row in candidate_results),
        "reference_models": ["R109_E048", "R61v16"],
        "claim_boundary": "Motion truth is Raw-referenced and commanded, not an independent stage encoder."
    }
    (OUTPUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
