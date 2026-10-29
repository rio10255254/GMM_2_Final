"""Reconstruct the real 50x x_1um sequence with read-only R96 counterfactual arms.

The real sequence has no clean optical target.  These arms therefore do not
claim oracle truth.  They translate the oracle audit into interventions on the
fixed E44 branch outputs so external GMF can test the resulting coordinates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / '20260702_100MG_位移_50x/x_1um'))
CHECKPOINT = ROOT / "weights" / "formal" / "seed_960041" / "R96_scratch_seed960041_20260813_131438" / "weights" / "epoch_044.pth.tar"
OUTPUT = ROOT / "results" / "x1um_counterfactual_reconstruction"

ARM_NAMES = (
    "00_raw",
    "01_r96",
    "02_detail_gate_open",
    "03_all_gate_open",
    "04_phase_safe_detail",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r96_x1_counterfactual_model", ROOT / "model" / "r96_model.py")
INFERENCE = load_module("r96_x1_counterfactual_inference", ROOT / "inference" / "reconstruct.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Cannot encode {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded.tofile(temporary)
    temporary.replace(path)


def to_u8(tensor: torch.Tensor) -> np.ndarray:
    return np.rint(tensor.clamp(0.0, 1.0).cpu().numpy() * 255.0).astype(np.uint8)


def phase_safe_detail(image: np.ndarray, amount: float = 0.35) -> np.ndarray:
    value = image.astype(np.float32)
    low = cv2.GaussianBlur(value, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    local_min = cv2.erode(value, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    local_max = cv2.dilate(value, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    strengthened = np.clip(value + float(amount) * (value - low), local_min, local_max)
    return np.rint(strengthened).clip(0, 255).astype(np.uint8)


def phase_safe_detail_float(image: torch.Tensor, amount: float = 0.35) -> torch.Tensor:
    """Match the validated zero-phase comparator before 8-bit quantization."""
    value = image.float()
    low = cv2.GaussianBlur(
        value[0, 0].cpu().numpy(), (0, 0), 1.0,
        borderType=cv2.BORDER_REFLECT_101,
    )
    base = value[0, 0].cpu().numpy()
    local_min = cv2.erode(base, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    local_max = cv2.dilate(base, np.ones((5, 5), np.uint8), borderType=cv2.BORDER_REFLECT_101)
    result = np.clip(base + float(amount) * (base - low), local_min, local_max)
    return torch.from_numpy(result)[None, None].to(value)


def save_preview(output: Path, frame_name: str, source_name: str) -> None:
    images = [read_gray(output / arm / frame_name) for arm in ARM_NAMES]
    labels = ["Raw", "R96 E44", "Detail gate open", "All gates open", "Phase-safe detail"]
    canvas_h, canvas_w = 420, 560
    panels = []
    for label, image in zip(labels, images):
        resized = cv2.resize(image, (canvas_w, canvas_h), interpolation=cv2.INTER_AREA)
        panel = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (canvas_w, 35), (255, 255, 255), -1)
        cv2.putText(panel, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (0, 0, 0), 2, cv2.LINE_AA)
        panels.append(panel)
    overview = np.concatenate(panels, axis=1)
    ok, encoded = cv2.imencode(".png", overview)
    if not ok:
        raise RuntimeError("Cannot encode preview")
    preview_dir = output / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    encoded.tofile(preview_dir / f"{Path(frame_name).stem}_overview.png")
    (preview_dir / f"{Path(frame_name).stem}_source_name.txt").write_text(source_name, encoding="utf-8")


@torch.inference_mode()
def reconstruct_arms(model: torch.nn.Module, image: torch.Tensor, core: int = 512, halo: int = 192) -> dict[str, np.ndarray]:
    canvas, (height, width, grid_h, grid_w) = INFERENCE.canonical_canvas(image, core, halo)
    buffers = {
        name: torch.empty((1, 1, grid_h, grid_w), device=image.device, dtype=torch.float32)
        for name in ARM_NAMES[1:4]
    }
    locations = [(y, x) for y in range(0, grid_h, core) for x in range(0, grid_w, core)]
    for y, x in locations:
        tile = canvas[..., y:y + core + 2 * halo, x:x + core + 2 * halo]
        details = model(tile, return_details=True)
        raw = tile.float()
        standard = details["output"].float()
        # The target generator applies physical evidence once.  R96 currently
        # also multiplies branch amplitude by its soft need map.  This arm keeps
        # the learned branch and evidence but removes that second attenuation.
        detail_open = torch.clamp(
            raw + details["radiometry_delta"] + details["nuisance_delta"]
            + details["local_contrast_evidence"] * details["local_contrast_raw"]
            + model.blur7(details["boundary_evidence"]) * details["boundary_restoration_raw"]
            + details["texture_recoverability"] * details["texture_restoration_raw"],
            0.0, 1.0,
        )
        # A stronger diagnostic removes need attenuation from all branch heads.
        # It is intentionally separated from the detail-only causal arm.
        all_open = torch.clamp(
            raw + details["radiometry_raw"] + details["nuisance_raw"]
            + details["local_contrast_evidence"] * details["local_contrast_raw"]
            + model.blur7(details["boundary_evidence"]) * details["boundary_restoration_raw"]
            + details["texture_recoverability"] * details["texture_restoration_raw"],
            0.0, 1.0,
        )
        tile_arms = {
            "01_r96": standard,
            "02_detail_gate_open": detail_open,
            "03_all_gate_open": all_open,
        }
        for name, value in tile_arms.items():
            core_value = value[..., halo:halo + core, halo:halo + core]
            buffers[name][..., y:y + core, x:x + core] = core_value
    cropped = {name: value[..., :height, :width] for name, value in buffers.items()}
    outputs = {name: to_u8(value[0, 0]) for name, value in cropped.items()}
    outputs["04_phase_safe_detail"] = to_u8(phase_safe_detail_float(cropped["01_r96"], amount=0.35)[0, 0])
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--indices", default="", help="Comma-separated zero-based frames; empty means all")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    source_paths = sorted(SOURCE.glob("*.bmp"))
    if len(source_paths) != 50:
        raise RuntimeError(f"Expected 50 source frames, found {len(source_paths)}")
    indices = list(range(len(source_paths))) if not args.indices else [int(v) for v in args.indices.split(",")]
    if any(index < 0 or index >= len(source_paths) for index in indices):
        raise ValueError(indices)
    if args.output.exists() and any(args.output.iterdir()) and not args.allow_existing:
        raise RuntimeError(f"Refusing to overwrite non-empty output: {args.output}")
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != 44:
        raise RuntimeError("Checkpoint is not epoch 44")
    model = MODEL.build_model(base=16)
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    torch.set_num_threads(4)
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for index in indices:
        source_path = source_paths[index]
        raw = read_gray(source_path)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        frame_started = time.perf_counter()
        outputs = reconstruct_arms(model, tensor)
        outputs["00_raw"] = raw
        frame_name = f"frame_{index:04d}.bmp"
        for arm in ARM_NAMES:
            destination = args.output / arm / frame_name
            if arm == "00_raw":
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, destination)
            else:
                write_gray(destination, outputs[arm])
            records.append({
                "frame_index": index,
                "original_name": source_path.name,
                "arm": arm,
                "output_name": frame_name,
                "height": int(raw.shape[0]),
                "width": int(raw.shape[1]),
                "source_sha256": sha256_file(source_path),
                "output_sha256": sha256_file(destination),
                "mean_abs_change_gray": float(np.abs(outputs[arm].astype(np.float32) - raw.astype(np.float32)).mean()),
                "elapsed_seconds": time.perf_counter() - frame_started,
            })
        print(f"[{index + 1:02d}/50] {source_path.name}", flush=True)
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    protocol = {
        "status": "reconstruction_complete",
        "source": str(SOURCE),
        "source_frame_count": len(source_paths),
        "processed_indices": indices,
        "checkpoint": str(CHECKPOINT),
        "checkpoint_epoch": 44,
        "checkpoint_state": "ema_state_dict",
        "checkpoint_sha256": sha256_file(CHECKPOINT),
        "device": str(device),
        "ordering": "original filenames sorted lexicographically; copied as frame_0000..frame_0049",
        "arms": {
            "00_raw": "bit-identical source sequence for GMF reference",
            "01_r96": "canonical R96 E44 output",
            "02_detail_gate_open": "learned detail branches with physical evidence applied once and soft need attenuation removed",
            "03_all_gate_open": "strong diagnostic with soft need attenuation removed from all learned branches",
            "04_phase_safe_detail": "R96 plus symmetric zero-phase local detail gain 0.35; visual/motion compatibility comparator, not oracle truth",
        },
        "claim_boundary": "No clean target exists for the real sequence; counterfactual arms test fixed learned branch interventions and are not ground truth reconstructions.",
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    preview_index = indices[len(indices) // 2]
    save_preview(
        args.output,
        f"frame_{preview_index:04d}.bmp",
        source_paths[preview_index].name,
    )
    print(json.dumps({"status": "complete", "output": str(args.output), "indices": indices}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
