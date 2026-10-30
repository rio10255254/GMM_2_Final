from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from PIL import Image
from scipy.io import loadmat
from scipy.stats import iqr
from torch.cuda.amp import autocast
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R81_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
R80_SCRIPTS = Path(str(PROJECT_ROOT / 'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts'))
MODERN_ROOT = (
    Path(str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments'))
    / "Modern_Restoration_Benchmarks_20260719"
)
for import_root in (SCRIPT_DIR, R80_SCRIPTS, MODERN_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import train_modern_baseline as trainer  # noqa: E402
from model_zoo import MODEL_SPECS  # noqa: E402
from reference_circle_core import (  # noqa: E402
    crop_around,
    measure_boundary_and_circles,
    measure_inflection_lsc,
    summarize_reference_circles,
)
from train_model import DEFAULT_PACKAGE, install_registry  # noqa: E402


CENTER9_PACKAGE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9')
)
SEQUENCE_CONFIG = CENTER9_PACKAGE / "config" / "sequence_center9_50x20x.json"
AUDIT_TABLE = (
    CENTER9_PACKAGE
    / "diagnostics"
    / "unified_displacement_step_audit"
    / "tables"
    / "raw_eligibility_locked_before_v42.csv"
)
SESSION_TABLE = AUDIT_TABLE.parent / "session_anchor_summary.csv"

PSF_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/01_global_bads_fit')
)
STATIC_SOURCE_ROOT = (
    PSF_ROOT / "source_data" / "center9_pillar_fit_20x_50x" / "psf_deconvolution_cd"
)
SWEEP_ROOT = Path(str(PROJECT_ROOT / 'PSF_Fitting/tests/artifacts/cd_verification_20260714'))
SEM_TABLE = (
    PSF_ROOT / "tables" / "center9_pillar_fit_20x_50x" / "cd_before_after_per_pillar.csv"
)

SCALE = {"20x": 0.1725, "50x": 0.0690}
EXPECTED_RADIUS = {"20x": 7.6, "50x": 19.5}
SAMPLE_COUNT = {"20x": 72, "50x": 144}
ACM_ITERATIONS = {"20x": 18, "50x": 24}


def read_gray(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    array = np.asarray(Image.open(path), dtype=np.float64)
    if array.ndim == 3:
        array = np.mean(array[:, :, :3], axis=2)
    if float(np.max(array)) > 1.5:
        array /= 255.0
    return np.clip(array, 0.0, 1.0)


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    u8 = np.clip(np.rint(np.asarray(image) * 255.0), 0, 255).astype(np.uint8)
    success, encoded = cv2.imencode(path.suffix or ".png", u8)
    if not success:
        raise RuntimeError(f"could not encode {path}")
    encoded.tofile(str(path))


def tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    if length <= tile_size:
        return [0]
    positions = list(range(0, length - tile_size + 1, stride))
    last = length - tile_size
    if positions[-1] != last:
        positions.append(last)
    return positions


def feather_window(tile_size: int, overlap: int) -> np.ndarray:
    edge = max(1, overlap // 2)
    vector = np.ones(tile_size, dtype=np.float32)
    phase = np.linspace(0.0, np.pi / 2.0, edge, endpoint=False, dtype=np.float32)
    ramp = np.sin(phase) ** 2
    vector[:edge] = ramp
    vector[-edge:] = ramp[::-1]
    return np.maximum(vector[:, None] * vector[None, :], 1.0e-6)


@torch.inference_mode()
def reconstruct_tiled(
    model: torch.nn.Module,
    image: np.ndarray,
    device: torch.device,
    *,
    amp_enabled: bool,
    tile_size: int = 128,
    overlap: int = 64,
    tile_batch: int = 32,
) -> tuple[np.ndarray, float]:
    source = np.asarray(image, dtype=np.float32)
    stride = tile_size - overlap
    pad = overlap // 2
    padded = np.pad(source, ((pad, pad), (pad, pad)), mode="reflect")
    add_y = max(0, tile_size - padded.shape[0])
    add_x = max(0, tile_size - padded.shape[1])
    if add_y or add_x:
        padded = np.pad(padded, ((0, add_y), (0, add_x)), mode="reflect")
    ys = tile_positions(padded.shape[0], tile_size, stride)
    xs = tile_positions(padded.shape[1], tile_size, stride)
    positions = [(y, x) for y in ys for x in xs]
    window = feather_window(tile_size, overlap)
    accumulation = np.zeros_like(padded, dtype=np.float32)
    weights = np.zeros_like(padded, dtype=np.float32)

    model.eval()
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    tick = time.perf_counter()
    for start in range(0, len(positions), tile_batch):
        chunk = positions[start : start + tile_batch]
        batch = np.stack(
            [padded[y : y + tile_size, x : x + tile_size] for y, x in chunk]
        )
        tensor = torch.from_numpy(batch)[:, None].to(device, non_blocking=True)
        with autocast(enabled=amp_enabled):
            prediction = model(tensor)
        outputs = prediction[:, 0].float().clamp(0.0, 1.0).cpu().numpy()
        for output, (y, x) in zip(outputs, chunk):
            accumulation[y : y + tile_size, x : x + tile_size] += output * window
            weights[y : y + tile_size, x : x + tile_size] += window
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - tick
    restored = accumulation / np.maximum(weights, 1.0e-8)
    restored = restored[pad : pad + source.shape[0], pad : pad + source.shape[1]]
    # Match the formal 8-bit measurement inputs used for Raw and MOSR.
    restored = np.rint(np.clip(restored, 0.0, 1.0) * 255.0) / 255.0
    return restored, elapsed


def load_model(checkpoint_path: Path, package: Path) -> tuple[torch.nn.Module, dict, torch.device]:
    install_registry()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    training_config = dict(checkpoint.get("training_config", {}))
    key = str(checkpoint.get("model_key", training_config.get("model_key", "")))
    if not key:
        raise RuntimeError("checkpoint has no model key")
    allowed = trainer.TrainConfig.__dataclass_fields__
    values = {name: value for name, value in training_config.items() if name in allowed}
    values["model_key"] = key
    config = trainer.TrainConfig(**values)
    model = trainer.build_training_model(package, config, device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model, checkpoint, device


def load_static_raw(magnification: str) -> tuple[np.ndarray, np.ndarray]:
    metadata = loadmat(
        STATIC_SOURCE_ROOT / f"{magnification}_wiener_deconvolution.mat", squeeze_me=True
    )
    centers = np.asarray(metadata["centers_xy"], dtype=float)
    sweep = loadmat(SWEEP_ROOT / f"{magnification}_deconvolution_sweep.mat", squeeze_me=True)
    raw = np.asarray(sweep["I"], dtype=float)
    return np.clip(raw, 0.0, 1.0), centers


def evaluate_static(
    model_key: str,
    model: torch.nn.Module,
    device: torch.device,
    output: Path,
    amp_enabled: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[float]]:
    sem = pd.read_csv(SEM_TABLE)
    rows: list[dict[str, object]] = []
    timings: list[float] = []
    for magnification in ("20x", "50x"):
        raw, centers = load_static_raw(magnification)
        restored, elapsed = reconstruct_tiled(
            model, raw, device, amp_enabled=amp_enabled, tile_batch=32
        )
        timings.append(elapsed)
        write_gray(output / "previews" / f"{magnification}_{model_key}.png", restored)
        truth = sem[sem["magnification"] == magnification].sort_values("pillar_image_index")
        if len(truth) != 9:
            raise RuntimeError(f"expected nine SEM values for {magnification}")
        for pillar_index, (center_xy, truth_row) in enumerate(
            zip(centers, truth.itertuples(index=False)), start=1
        ):
            measurement = measure_boundary_and_circles(
                restored,
                (float(center_xy[0]), float(center_xy[1])),
                EXPECTED_RADIUS[magnification],
                sample_count=SAMPLE_COUNT[magnification],
                acm_iterations=ACM_ITERATIONS[magnification],
                polarity="dark",
            )
            metrics = summarize_reference_circles(
                measurement, scale_um_per_px=SCALE[magnification]
            )
            sem_cd_um = float(truth_row.sem_cd_nm) / 1000.0
            row: dict[str, object] = {
                "magnification": magnification,
                "method": model_key,
                "pillar_image_index": pillar_index,
                "sem_cd_um": sem_cd_um,
                "object_um_per_px": SCALE[magnification],
            }
            row.update(metrics)
            row["lsc_signed_error_nm"] = (float(row["lsc_diameter_um"]) - sem_cd_um) * 1000.0
            row["lsc_abs_error_nm"] = abs(float(row["lsc_signed_error_nm"]))
            rows.append(row)
    per_pillar = pd.DataFrame(rows)
    summary_rows: list[dict[str, object]] = []
    for magnification, group in per_pillar.groupby("magnification", sort=False):
        error = group["lsc_abs_error_nm"].to_numpy(float)
        summary_rows.append(
            {
                "magnification": magnification,
                "method": model_key,
                "n_pillars": len(group),
                "median_abs_error_nm": float(np.median(error)),
                "iqr_abs_error_nm": float(iqr(error)),
                "mean_abs_error_nm": float(np.mean(error)),
                "median_mzc_roundness_nm": float(np.median(group["mzc_roundness_um"]) * 1000.0),
                "median_harmonic4_relative_pct": float(np.median(group["harmonic4_relative_pct"])),
            }
        )
    return per_pillar, pd.DataFrame(summary_rows), timings


def selected_pairs(sequence: str, limit_pairs: int = 30) -> pd.DataFrame:
    audit = pd.read_csv(AUDIT_TABLE)
    subset = audit[
        (audit["sequence"] == sequence)
        & audit["raw_eligible_25pct"].astype(bool)
        & (~audit["cross_session"].astype(bool))
    ].copy()
    subset["raw_nominal_abs_error_um"] = np.abs(
        subset["raw_boundary_dx_um"] - subset["expected_signed_step_um"]
    )
    subset = subset.sort_values(
        ["raw_nominal_abs_error_um", "raw_within_grid_nm", "start_frame_index"],
        kind="mergesort",
    ).head(limit_pairs)
    return subset.sort_values("start_frame_index").reset_index(drop=True)


def session_prediction(
    sequence: str,
    frame_index: int,
    base_centers: np.ndarray,
    expected_dx_px: float,
) -> np.ndarray:
    sessions = pd.read_csv(SESSION_TABLE)
    candidates = sessions[
        (sessions["sequence"] == sequence)
        & (sessions["start_frame_index"] <= frame_index)
        & (sessions["end_frame_index"] >= frame_index)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"frame {frame_index} in {sequence} has {len(candidates)} sessions")
    session = candidates.iloc[0]
    delta = frame_index - int(session["start_frame_index"])
    predicted = base_centers.copy()
    predicted[:, 1] += float(session["anchor_offset_x_px"]) + delta * expected_dx_px
    predicted[:, 2] += float(session["anchor_offset_y_px"])
    return predicted


def evaluate_displacement(
    model_key: str,
    model: torch.nn.Module,
    device: torch.device,
    amp_enabled: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[float]]:
    configuration = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    center_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    timings: list[float] = []

    for sequence, specification in configuration["sequences"].items():
        pairs = selected_pairs(sequence, limit_pairs=30)
        frame_indices = sorted(
            set(pairs["start_frame_index"].astype(int))
            | set(pairs["end_frame_index"].astype(int))
        )
        base_centers = np.asarray(specification["centers"], dtype=float)
        raw_dir = Path(PROJECT_ROOT / specification["raw_dir"])
        magnification = specification["magnification"]
        pitch = float(specification["pitch_px"])
        radius = float(specification["radius_px"])
        scale = float(specification["object_um_per_px"])
        expected_dx_px = float(specification["expected_signed_dx_px"])
        patch_half = int(np.ceil(0.46 * pitch))
        sample_count = 64 if magnification == "20x" else 96
        acm_iterations = 13 if magnification == "20x" else 15
        normal_half = 2.4 if magnification == "20x" else 4.0

        for frame_index in frame_indices:
            raw = read_gray(raw_dir / f"frame_{frame_index:04d}.bmp")
            predicted = session_prediction(sequence, frame_index, base_centers, expected_dx_px)
            # The margin includes the 50-pixel PSF radius and keeps each outer pillar
            # away from the reconstruction boundary.
            margin = max(64, int(np.ceil(0.65 * pitch)))
            x0 = max(0, int(np.floor(np.min(predicted[:, 1]))) - margin)
            x1 = min(raw.shape[1], int(np.ceil(np.max(predicted[:, 1]))) + margin + 1)
            y0 = max(0, int(np.floor(np.min(predicted[:, 2]))) - margin)
            y1 = min(raw.shape[0], int(np.ceil(np.max(predicted[:, 2]))) + margin + 1)
            raw_roi = raw[y0:y1, x0:x1]
            restored, elapsed = reconstruct_tiled(
                model, raw_roi, device, amp_enabled=amp_enabled, tile_batch=32
            )
            timings.append(elapsed)

            for pillar_id, predicted_x, predicted_y in predicted:
                local_center = (float(predicted_x - x0), float(predicted_y - y0))
                patch, patch_center, patch_origin = crop_around(
                    restored, local_center, patch_half
                )
                measurement = measure_inflection_lsc(
                    patch,
                    patch_center,
                    radius,
                    sample_count=sample_count,
                    acm_iterations=acm_iterations,
                    normal_half_width_px=normal_half,
                    polarity="dark",
                )
                center_rows.append(
                    {
                        "sequence": sequence,
                        "magnification": magnification,
                        "frame_index": frame_index,
                        "method": model_key,
                        "pillar_id": int(pillar_id),
                        "lsc_center_x_px": measurement.lsc.cx + patch_origin[0] + x0,
                        "lsc_center_y_px": measurement.lsc.cy + patch_origin[1] + y0,
                        "lsc_radius_px": measurement.lsc.radius,
                        "gradient_strength_median": float(
                            np.median(measurement.signed_gradient_strength)
                        ),
                        "object_um_per_px": scale,
                    }
                )

        centers_sequence = pd.DataFrame(
            row for row in center_rows if row["sequence"] == sequence
        ).set_index(["frame_index", "pillar_id"])
        for pair_rank, pair in pairs.iterrows():
            start = int(pair["start_frame_index"])
            end = int(pair["end_frame_index"])
            pillar_dx: list[float] = []
            pillar_dy: list[float] = []
            for pillar_id in base_centers[:, 0].astype(int):
                before = centers_sequence.loc[(start, pillar_id)]
                after = centers_sequence.loc[(end, pillar_id)]
                pillar_dx.append(
                    (float(after["lsc_center_x_px"]) - float(before["lsc_center_x_px"])) * scale
                )
                pillar_dy.append(
                    (float(after["lsc_center_y_px"]) - float(before["lsc_center_y_px"])) * scale
                )
            aggregate_dx = float(np.median(pillar_dx))
            aggregate_dy = float(np.median(pillar_dy))
            nominal = float(specification["nominal_step_um"])
            pair_rows.append(
                {
                    "sequence": sequence,
                    "magnification": magnification,
                    "pair_rank_raw_locked": pair_rank + 1,
                    "start_frame_index": start,
                    "end_frame_index": end,
                    "method": model_key,
                    "nominal_step_um": nominal,
                    "measured_step_um": abs(aggregate_dx),
                    "nominal_abs_error_nm": abs(abs(aggregate_dx) - nominal) * 1000.0,
                    "within_grid_sd_nm": float(np.std(pillar_dx, ddof=1) * 1000.0),
                    "cross_axis_abs_nm": abs(aggregate_dy) * 1000.0,
                }
            )

    centers = pd.DataFrame(center_rows)
    per_pair = pd.DataFrame(pair_rows)
    summary_rows: list[dict[str, object]] = []
    for sequence, group in per_pair.groupby("sequence", sort=False):
        summary_rows.append(
            {
                "scope": "per_sequence",
                "sequence": sequence,
                "method": model_key,
                "n_pairs": len(group),
                "step_sd_nm": float(np.std(group["measured_step_um"], ddof=1) * 1000.0),
                "mean_nominal_abs_error_nm": float(np.mean(group["nominal_abs_error_nm"])),
                "median_within_grid_sd_nm": float(np.median(group["within_grid_sd_nm"])),
            }
        )
    summary_rows.append(
        {
            "scope": "all_four_sequences",
            "sequence": "combined",
            "method": model_key,
            "n_pairs": len(per_pair),
            "step_sd_nm": float(
                np.mean(
                    [
                        np.std(group["measured_step_um"], ddof=1) * 1000.0
                        for _, group in per_pair.groupby("sequence")
                    ]
                )
            ),
            "mean_nominal_abs_error_nm": float(np.mean(per_pair["nominal_abs_error_nm"])),
            "median_within_grid_sd_nm": float(np.median(per_pair["within_grid_sd_nm"])),
        }
    )
    return centers, per_pair, pd.DataFrame(summary_rows), timings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    checkpoint = arguments.checkpoint or (
        R81_ROOT / "results" / "training" / arguments.model / f"best_{arguments.model}.pth.tar"
    )
    output = arguments.output or (R81_ROOT / "results" / "evaluation" / arguments.model)
    output.mkdir(parents=True, exist_ok=True)
    model, checkpoint_data, device = load_model(checkpoint.resolve(), arguments.package.resolve())
    checkpoint_key = str(
        checkpoint_data.get(
            "model_key", checkpoint_data.get("training_config", {}).get("model_key", "")
        )
    )
    if checkpoint_key != arguments.model:
        raise RuntimeError(
            f"checkpoint/model mismatch: checkpoint={checkpoint_key!r}, argument={arguments.model!r}"
        )
    amp_enabled = arguments.model != "pft" and device.type == "cuda"

    static_per, static_summary, static_timings = evaluate_static(
        arguments.model, model, device, output, amp_enabled
    )
    centers, per_pair, displacement_summary, displacement_timings = evaluate_displacement(
        arguments.model, model, device, amp_enabled
    )
    static_per.to_csv(output / "static_per_pillar.csv", index=False, encoding="utf-8-sig")
    static_summary.to_csv(output / "static_summary.csv", index=False, encoding="utf-8-sig")
    centers.to_csv(output / "displacement_centers.csv", index=False, encoding="utf-8-sig")
    per_pair.to_csv(output / "displacement_per_pair.csv", index=False, encoding="utf-8-sig")
    displacement_summary.to_csv(
        output / "displacement_summary.csv", index=False, encoding="utf-8-sig"
    )

    if len(static_per) != 18 or len(per_pair) != 120:
        raise RuntimeError(
            f"incomplete evaluation: static={len(static_per)}, displacement pairs={len(per_pair)}"
        )
    manifest = {
        "model_key": arguments.model,
        "model_spec": MODEL_SPECS[arguments.model].__dict__,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_epoch": int(checkpoint_data.get("epoch", 0)),
        "checkpoint_validation": checkpoint_data.get("validation", {}),
        "parameter_count": int(checkpoint_data.get("parameter_count", 0)),
        "static_pillars": len(static_per),
        "displacement_pairs": len(per_pair),
        "displacement_sequences": int(per_pair["sequence"].nunique()),
        "measurement_backend": "ACM + correct-polarity maximum-gradient inflection + LSC/MZC/MIC/MCC",
        "grayscale_threshold_used": False,
        "pair_selection": "Raw-only locked list before all learned model evaluation",
        "formal_displacement_frames_have_training_package_crops": True,
        "blind_external_generalization": False,
        "static_center9_role": "PSF and scale calibration region, not an independent sample",
        "stage_reference": "nominal platform setpoint, not independent interferometer truth",
        "tile_size": 128,
        "tile_overlap": 64,
        "tile_batch": 32,
        "amp_enabled": amp_enabled,
        "median_static_inference_seconds": float(np.median(static_timings)),
        "median_displacement_roi_inference_seconds": float(np.median(displacement_timings)),
    }
    (output / "evaluation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(static_summary.to_string(index=False))
    print(displacement_summary.tail(1).to_string(index=False))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
