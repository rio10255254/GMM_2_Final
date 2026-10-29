"""Frozen-E20 R74 oracle gate probe.

This is deliberately not a deployable method.  R74 synthetic truth is used to
construct local upper-bound reliability maps for the already-trained width and
normal-shift actions.  The frozen model and the locked ACM protocol are never
modified.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import MODEL_CONFIG, _warp, build_full_model
PROJECT_ROOT = Path(__file__).resolve().parents[3]


OUT = ROOT / "results" / "geometry_probe" / "E020" / "oracle_gate_probe"
SOURCE = Path(
    str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')
)
TEMPLATE = Path(
    str(PROJECT_ROOT / 'Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json')
)
CHECKPOINT = (
    ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights" / "epoch_020.pth"
)
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
R82 = Path(
    str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts')
)

METHODS = (
    "FullFrozen",
    "OracleShiftGate",
    "OracleWidthGate",
    "OracleSeparateGates",
)
BOUNDARY_BAND_PX = 18.0
LOCAL_ERROR_SIGMA_PX = 3.0
GATE_FEATHER_SIGMA_PX = 1.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: str | Path) -> np.ndarray:
    path = Path(path)
    image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"cannot read {path}")
    return image


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = np.rint(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8)
    ok, encoded = cv2.imencode(".bmp", value)
    if not ok:
        raise RuntimeError(f"cannot encode {path}")
    encoded.tofile(path)


def load_model(device: torch.device):
    payload = torch.load(CHECKPOINT, map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError("checkpoint violates scratch-only contract")
    model = build_full_model(detail_enabled=False)
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval()


def renderer_state(model, raw: torch.Tensor) -> dict[str, torch.Tensor]:
    controller = model.controller(raw)
    features = model.renderer_tower(F.silu(model.renderer_stem(model.cues(raw))))
    minimum = float(MODEL_CONFIG["minimum_width_gain"])
    maximum = float(MODEL_CONFIG["maximum_width_gain"])
    width_gain = minimum + (maximum - minimum) * torch.sigmoid(model.width_head(features))
    maximum_shift = float(MODEL_CONFIG["maximum_normal_shift_px"])
    normal_shift = maximum_shift * torch.tanh(model.shift_head(features))
    return {
        "normal_x": controller.normal_x,
        "normal_y": controller.normal_y,
        "geometry_gate": controller.geometry_gate,
        "width_gain": width_gain,
        "normal_shift": normal_shift,
    }


def render(
    model,
    raw: torch.Tensor,
    state: dict[str, torch.Tensor],
    shift_gate: torch.Tensor,
    width_gate: torch.Tensor,
) -> torch.Tensor:
    geometry_gate = state["geometry_gate"]
    flow = torch.cat(
        [
            state["normal_shift"] * state["normal_x"],
            state["normal_shift"] * state["normal_y"],
        ],
        dim=1,
    )
    warped = _warp(raw, flow * geometry_gate * shift_gate)
    window = int(MODEL_CONFIG["local_range_window_px"])
    radius = window // 2
    local_max = F.max_pool2d(warped, window, stride=1, padding=radius)
    local_min = -F.max_pool2d(-warped, window, stride=1, padding=radius)
    dynamic = (local_max - local_min).clamp_min(2.0 / 255.0)
    unit = ((warped - local_min) / dynamic).clamp(1.0e-4, 1.0 - 1.0e-4)
    effective_width = 1.0 + width_gate * (state["width_gain"] - 1.0)
    proposal = torch.sigmoid(effective_width * (torch.log(unit) - torch.log1p(-unit)))
    proposal = local_min + dynamic * proposal
    return (raw + geometry_gate * (proposal - raw)).clamp(0.0, 1.0)


def _robust_class_median(value: np.ndarray, region: np.ndarray) -> float:
    selected = value[region]
    if selected.size < 64:
        selected = value.reshape(-1)
    return float(np.median(selected))


def aligned_target_and_band(
    raw: np.ndarray,
    label: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Match clean-label gray levels to the observation without moving its edge."""
    inside = mask > 0.5
    kernel = np.ones((9, 9), np.uint8)
    deep_inside = cv2.erode(inside.astype(np.uint8), kernel) > 0
    deep_outside = cv2.erode((~inside).astype(np.uint8), kernel) > 0
    raw_fg = _robust_class_median(raw, deep_inside)
    raw_bg = _robust_class_median(raw, deep_outside)
    label_fg = _robust_class_median(label, deep_inside)
    label_bg = _robust_class_median(label, deep_outside)
    denominator = label_fg - label_bg
    if abs(denominator) < (2.0 / 255.0):
        target = label.copy()
    else:
        target = raw_bg + (label - label_bg) * ((raw_fg - raw_bg) / denominator)
    target = np.clip(target, 0.0, 1.0).astype(np.float32)

    distance_inside = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
    distance_outside = cv2.distanceTransform((~inside).astype(np.uint8), cv2.DIST_L2, 5)
    distance = np.where(inside, distance_inside, distance_outside)
    band = (distance <= BOUNDARY_BAND_PX).astype(np.float32)
    return target, band


def oracle_reliability(
    raw: np.ndarray,
    candidate: np.ndarray,
    target: np.ndarray,
    band: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    identity_error = cv2.GaussianBlur(
        np.abs(raw - target), (0, 0), LOCAL_ERROR_SIGMA_PX, borderType=cv2.BORDER_REFLECT
    )
    candidate_error = cv2.GaussianBlur(
        np.abs(candidate - target), (0, 0), LOCAL_ERROR_SIGMA_PX, borderType=cv2.BORDER_REFLECT
    )
    local_gain = identity_error - candidate_error
    hard = ((local_gain > 0.0) & (band > 0.5)).astype(np.float32)
    gate = cv2.GaussianBlur(
        hard, (0, 0), GATE_FEATHER_SIGMA_PX, borderType=cv2.BORDER_REFLECT
    )
    gate = np.clip(gate * band, 0.0, 1.0).astype(np.float32)
    active = band > 0.5
    stats = {
        "band_fraction": float(band.mean()),
        "hard_reliable_fraction_in_band": float(hard[active].mean()),
        "soft_gate_mean_in_band": float(gate[active].mean()),
        "median_local_gain_gray_in_band": float(np.median(local_gain[active]) * 255.0),
        "positive_gain_gray_in_band": float(np.mean(np.maximum(local_gain[active], 0.0)) * 255.0),
    }
    return gate, stats


def generate(records: list[dict], model, device: torch.device) -> tuple[dict[str, Path], pd.DataFrame, float]:
    roots = {name: OUT / "inputs" / name for name in METHODS}
    gate_rows: list[dict] = []
    maximum_reproduction_error = 0.0
    one = None
    zero = None
    with torch.inference_mode():
        for index, row in enumerate(records, 1):
            raw_np = read_gray(row["src"]).astype(np.float32) / 255.0
            label_np = read_gray(row["lbl"]).astype(np.float32) / 255.0
            mask_np = read_gray(row["mask"]).astype(np.float32) / 255.0
            raw = torch.from_numpy(raw_np)[None, None].to(device)
            state = renderer_state(model, raw)
            if one is None or tuple(one.shape) != tuple(raw.shape):
                one = torch.ones_like(raw)
                zero = torch.zeros_like(raw)

            full = render(model, raw, state, one, one)
            reference = model(raw)
            reproduction_error = float((full - reference).abs().max().item())
            maximum_reproduction_error = max(maximum_reproduction_error, reproduction_error)
            if reproduction_error > 2.0e-6:
                raise RuntimeError(f"renderer reproduction drift at {row['image_id']}: {reproduction_error}")
            width_only = render(model, raw, state, zero, one)
            shift_only = render(model, raw, state, one, zero)

            target_np, band_np = aligned_target_and_band(raw_np, label_np, mask_np)
            shift_gate_np, shift_stats = oracle_reliability(
                raw_np, shift_only[0, 0].cpu().numpy(), target_np, band_np
            )
            width_gate_np, width_stats = oracle_reliability(
                raw_np, width_only[0, 0].cpu().numpy(), target_np, band_np
            )
            shift_gate = torch.from_numpy(shift_gate_np)[None, None].to(device)
            width_gate = torch.from_numpy(width_gate_np)[None, None].to(device)

            outputs = {
                "FullFrozen": full,
                "OracleShiftGate": render(model, raw, state, shift_gate, one),
                "OracleWidthGate": render(model, raw, state, one, width_gate),
                "OracleSeparateGates": render(model, raw, state, shift_gate, width_gate),
            }
            for method, output in outputs.items():
                destination = roots[method] / str(row["stage"]) / str(row["filename"])
                write_gray(destination, output[0, 0].cpu().numpy())

            gate_stage = OUT / "gates" / str(row["stage"])
            write_gray(gate_stage / "shift" / str(row["filename"]), shift_gate_np)
            write_gray(gate_stage / "width" / str(row["filename"]), width_gate_np)
            write_gray(gate_stage / "boundary_band" / str(row["filename"]), band_np)
            gate_rows.append(
                {
                    "image_id": row["image_id"],
                    "family": row["family"],
                    "shape_family": row["shape_family"],
                    "shift_hard_reliable_fraction": shift_stats["hard_reliable_fraction_in_band"],
                    "shift_gate_mean": shift_stats["soft_gate_mean_in_band"],
                    "shift_median_gain_gray": shift_stats["median_local_gain_gray_in_band"],
                    "shift_positive_gain_gray": shift_stats["positive_gain_gray_in_band"],
                    "width_hard_reliable_fraction": width_stats["hard_reliable_fraction_in_band"],
                    "width_gate_mean": width_stats["soft_gate_mean_in_band"],
                    "width_median_gain_gray": width_stats["median_local_gain_gray_in_band"],
                    "width_positive_gain_gray": width_stats["positive_gain_gray_in_band"],
                    "boundary_band_fraction": shift_stats["band_fraction"],
                }
            )
            if index % 10 == 0:
                print(f"generated {index}/{len(records)}", flush=True)
    gate_table = pd.DataFrame(gate_rows)
    tables = OUT / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    gate_table.to_csv(tables / "gate_statistics_per_image.csv", index=False, encoding="utf-8-sig")
    gate_table.groupby("family", as_index=False).median(numeric_only=True).to_csv(
        tables / "gate_statistics_by_family.csv", index=False, encoding="utf-8-sig"
    )
    return roots, gate_table, maximum_reproduction_error


def prepare_contract(records: list[dict], roots: dict[str, Path]) -> tuple[Path, int, int]:
    contract = OUT / "locked_acm_contract"
    config = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    config["experiment_id"] = "R114_R74_E020_OracleSeparateGate_UpperBound"
    config["dataset"]["root"] = str(SOURCE)
    config_path = contract / "config" / "experiment.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    methods = ["Raw", *METHODS]
    directories = {name: {} for name in methods}
    for family in config["dataset"]["families"]:
        family_name, stage = family["name"], family["stage"]
        directories["Raw"][family_name] = str(SOURCE / "src" / stage)
        for method, root in roots.items():
            directories[method][family_name] = str(root / stage)
    manifest = contract / "results" / "inference_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {"suite": "R74", "methods": methods, "output_dirs": directories},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    primary = int(config["dataset"]["total_images"]) * len(methods) * 2
    sensitivity = (
        len(config["dataset"]["families"])
        * len(config["acm"]["sensitivity_filenames"])
        * len(config["acm"]["sensitivity_presets"])
        * len(methods)
    )
    return contract, primary, sensitivity


def acm_complete(contract: Path, primary_count: int, sensitivity_count: int) -> bool:
    tables = contract / "results" / "tables"
    primary = tables / "primary_contour_metrics.csv"
    sensitivity = tables / "acm_sensitivity_metrics.csv"
    return (
        primary.is_file()
        and sensitivity.is_file()
        and len(pd.read_csv(primary)) == primary_count
        and len(pd.read_csv(sensitivity)) == sensitivity_count
    )


def run_locked_acm(contract: Path, primary_count: int, sensitivity_count: int) -> None:
    if acm_complete(contract, primary_count, sensitivity_count):
        return
    expression = f"addpath('{R82.as_posix()}'); run_acm_multimethod('{contract.as_posix()}')"
    result = subprocess.run(
        [str(MATLAB), "-batch", expression],
        cwd=contract,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log = contract / "logs" / "matlab_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not acm_complete(contract, primary_count, sensitivity_count):
        raise RuntimeError(f"locked ACM failed; inspect {log}")


def summarize(contract: Path, gate_table: pd.DataFrame, reproduction_error: float) -> dict:
    table = pd.read_csv(contract / "results" / "tables" / "primary_contour_metrics.csv")
    translated = table.loc[table["alignment"].eq("translation_only")].copy()
    metrics = [
        "iou",
        "mean_boundary_distance_px",
        "hd95_px",
        "area_error_pct",
        "perimeter_error_pct",
    ]
    overall = translated.groupby("method", as_index=False)[metrics].median()
    family = translated.groupby(["method", "family"], as_index=False)[metrics].median()
    tables = OUT / "tables"
    overall.to_csv(tables / "locked_acm_overall.csv", index=False, encoding="utf-8-sig")
    family.to_csv(tables / "locked_acm_by_family.csv", index=False, encoding="utf-8-sig")
    overall_index = overall.set_index("method")
    family_index = family.set_index(["method", "family"])
    raw = overall_index.loc["Raw"]
    model_results: dict[str, dict] = {}
    for method in METHODS:
        current = overall_index.loc[method]
        family_results = []
        for name in sorted(translated["family"].unique()):
            before = family_index.loc[("Raw", name)]
            after = family_index.loc[(method, name)]
            family_results.append(
                {
                    "family": name,
                    "boundary_change_pct": float(
                        (after["mean_boundary_distance_px"] / before["mean_boundary_distance_px"] - 1.0)
                        * 100.0
                    ),
                    "hd95_change_pct": float((after["hd95_px"] / before["hd95_px"] - 1.0) * 100.0),
                    "iou_delta": float(after["iou"] - before["iou"]),
                }
            )
        model_results[method] = {
            "metrics": {key: float(current[key]) for key in metrics},
            "boundary_change_pct": float(
                (current["mean_boundary_distance_px"] / raw["mean_boundary_distance_px"] - 1.0)
                * 100.0
            ),
            "hd95_change_pct": float((current["hd95_px"] / raw["hd95_px"] - 1.0) * 100.0),
            "iou_delta": float(current["iou"] - raw["iou"]),
            "families": family_results,
        }

    full_family = {row["family"]: row for row in model_results["FullFrozen"]["families"]}
    oracle_family = {
        row["family"]: row for row in model_results["OracleSeparateGates"]["families"]
    }
    desired = ("asymmetric_blur_halo", "uneven_illumination")
    repairs = ("boundary_fade", "low_contrast", "mixed_hard")
    desired_preserved = {
        name: bool(
            oracle_family[name]["boundary_change_pct"] < 0.0
            and oracle_family[name]["iou_delta"] >= 0.0
        )
        for name in desired
    }
    repair_improved_over_full = {
        name: bool(
            oracle_family[name]["boundary_change_pct"]
            < full_family[name]["boundary_change_pct"]
            and oracle_family[name]["iou_delta"] > full_family[name]["iou_delta"]
        )
        for name in repairs
    }
    repair_beats_raw = {
        name: bool(
            oracle_family[name]["boundary_change_pct"] < 0.0
            and oracle_family[name]["iou_delta"] >= 0.0
        )
        for name in repairs
    }
    boundary_per_image = translated.pivot(
        index=["image_id", "family"], columns="method", values="mean_boundary_distance_px"
    )
    image_selector_upper_bounds = []
    for family_name, group in boundary_per_image.groupby(level="family"):
        raw_median = float(group["Raw"].median())
        best_raw_or_full = group[["Raw", "FullFrozen"]].min(axis=1)
        best_any_observed = group[["Raw", *METHODS]].min(axis=1)
        image_selector_upper_bounds.append(
            {
                "family": family_name,
                "raw_or_full_boundary_change_pct": float(
                    (best_raw_or_full.median() / raw_median - 1.0) * 100.0
                ),
                "raw_or_any_observed_boundary_change_pct": float(
                    (best_any_observed.median() / raw_median - 1.0) * 100.0
                ),
                "full_beats_raw_fraction": float((group["FullFrozen"] < group["Raw"]).mean()),
                "separate_gate_beats_raw_fraction": float(
                    (group["OracleSeparateGates"] < group["Raw"]).mean()
                ),
                "separate_gate_beats_full_fraction": float(
                    (group["OracleSeparateGates"] < group["FullFrozen"]).mean()
                ),
            }
        )
    conclusion = {
        "desired_family_improvements_preserved": desired_preserved,
        "failure_families_improved_over_full": repair_improved_over_full,
        "failure_families_better_than_raw": repair_beats_raw,
        "supports_learned_separate_gates": bool(
            all(desired_preserved.values())
            and sum(repair_improved_over_full.values()) >= 2
        ),
        "oracle_upper_bound_only": True,
        "not_deployable": True,
    }
    gate_family = gate_table.groupby("family", as_index=False).median(numeric_only=True)
    gate_summary = gate_family.to_dict(orient="records")
    payload = {
        "status": "complete",
        "purpose": "causal upper bound for separate local shift and width reliability gates",
        "protocol": "frozen E20 plus locked Chan-Vese ACM; translation-only primary",
        "truth_usage": (
            "R74 clean label and mask are used only to form local oracle reliability maps; "
            "they are not model inputs and no weights are updated"
        ),
        "gate_rule": {
            "component_comparison": "component-only local L1 error versus identity",
            "target_gray_alignment": "clean-label foreground/background levels aligned to raw medians",
            "boundary_band_px": BOUNDARY_BAND_PX,
            "local_error_sigma_px": LOCAL_ERROR_SIGMA_PX,
            "gate_feather_sigma_px": GATE_FEATHER_SIGMA_PX,
            "threshold": "strictly positive local gain; no ACM-based tuning",
        },
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "source_manifest_sha256": sha256(SOURCE / "manifest.json"),
        "maximum_full_renderer_reproduction_error": reproduction_error,
        "models": model_results,
        "gate_statistics_by_family": gate_summary,
        "image_selector_upper_bounds": image_selector_upper_bounds,
        "acm_failures": table.groupby("method")["acm_success"]
        .apply(lambda values: int((~values.astype(bool)).sum()))
        .to_dict(),
        "conclusion": conclusion,
    }
    (OUT / "analysis_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def write_readme(payload: dict) -> None:
    full = {row["family"]: row for row in payload["models"]["FullFrozen"]["families"]}
    oracle = {
        row["family"]: row for row in payload["models"]["OracleSeparateGates"]["families"]
    }
    lines = [
        "# R74 E20 Oracle / Local-Reliability Gate Probe",
        "",
        "This is a frozen-model causal upper bound, not a deployable model and not training.",
        "Synthetic truth is used only to decide where an already-learned shift or width action is locally reliable.",
        "The gate rule was fixed before locked ACM and was not tuned from ACM results.",
        "",
        "| family | Full boundary change | Separate-oracle boundary change | Full IoU delta | Separate-oracle IoU delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in sorted(full):
        lines.append(
            f"| {name} | {full[name]['boundary_change_pct']:.3f}% | "
            f"{oracle[name]['boundary_change_pct']:.3f}% | {full[name]['iou_delta']:.6f} | "
            f"{oracle[name]['iou_delta']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Per-image selector upper bound",
            "",
            "This supplementary bound chooses the lower boundary error after seeing truth. "
            "It asks whether the existing action library contains a repair at all.",
            "",
            "| family | Best of Raw/Full | Best of Raw/all observed methods |",
            "|---|---:|---:|",
        ]
    )
    for row in payload["image_selector_upper_bounds"]:
        lines.append(
            f"| {row['family']} | {row['raw_or_full_boundary_change_pct']:.3f}% | "
            f"{row['raw_or_any_observed_boundary_change_pct']:.3f}% |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Supports learning separate gates: **{payload['conclusion']['supports_learned_separate_gates']}**",
            "",
            "See `analysis_summary.json` and `tables/` for the complete locked results.",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    for required in (SOURCE / "manifest.json", TEMPLATE, CHECKPOINT, MATLAB):
        if not required.is_file():
            raise FileNotFoundError(required)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest["records"]) != 100:
        raise RuntimeError("R74 frozen contract must contain exactly 100 records")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(device)
    roots, gate_table, reproduction_error = generate(manifest["records"], model, device)
    contract, primary_count, sensitivity_count = prepare_contract(manifest["records"], roots)
    run_locked_acm(contract, primary_count, sensitivity_count)
    payload = summarize(contract, gate_table, reproduction_error)
    write_readme(payload)
    print(json.dumps(payload["conclusion"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
