"""Independent checks and a visual preview for the external-GMF package."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[4]


PACKAGE = Path(__file__).resolve().parents[1]
RAW = PACKAGE / "pitch1um_y100_raw" / "bmp"
R109 = PACKAGE / "pitch1um_y100_r109_e48" / "bmp"
RECORDS = PACKAGE / "_records"
PRIOR_MAPPING = PACKAGE.parent / "Pitch1um_Y_100_Raw_Even_R103E48_R104E48" / "source_mapping.csv"
MODEL_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))
CHECKPOINT = MODEL_ROOT / "weights" / "selected" / "R109.pth"
sys.path.insert(0, str(MODEL_ROOT / "model"))
from r109_model import build_model  # noqa: E402


def read(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def mapping_names(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row["original_filename"] for row in csv.DictReader(handle)]


@torch.inference_mode()
def reconstruct_with_alternate_grid(image: np.ndarray) -> np.ndarray:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    payload = torch.load(CHECKPOINT, map_location=device, weights_only=False)
    model = build_model().to(device)
    model.load_state_dict(payload["model"])
    model.eval()
    core, halo = 2048, 192
    source = torch.from_numpy(image.astype(np.float32)[None, None] / 255.0).to(device)
    height, width = image.shape
    padded = F.pad(source, (halo, halo, halo, halo), mode="reflect")
    output = torch.zeros_like(source)
    for y in range(0, height, core):
        for x in range(0, width, core):
            core_h = min(core, height - y)
            core_w = min(core, width - x)
            tile = padded[..., y : y + core_h + 2 * halo, x : x + core_w + 2 * halo]
            value = model(tile)
            output[..., y : y + core_h, x : x + core_w] = value[
                ..., halo : halo + core_h, halo : halo + core_w
            ]
    return np.round(np.clip(output[0, 0].cpu().numpy(), 0.0, 1.0) * 255.0).astype(np.uint8)


def make_preview(raw: np.ndarray, output: np.ndarray, destination: Path) -> None:
    center_y, center_x = np.unravel_index(np.argmax(cv2.GaussianBlur(raw, (0, 0), 24)), raw.shape)
    half = 900
    y0 = int(np.clip(center_y - half, 0, raw.shape[0] - 2 * half))
    x0 = int(np.clip(center_x - half, 0, raw.shape[1] - 2 * half))
    crop_raw = raw[y0 : y0 + 2 * half, x0 : x0 + 2 * half]
    crop_output = output[y0 : y0 + 2 * half, x0 : x0 + 2 * half]
    difference = np.abs(crop_output.astype(np.int16) - crop_raw.astype(np.int16)).astype(np.uint8)
    difference = np.clip(difference.astype(np.float32) * 18.0, 0, 255).astype(np.uint8)
    panels = []
    for label, value in (("Raw", crop_raw), ("R109 E48", crop_output), ("Difference x18", difference)):
        panel = cv2.resize(value, (720, 720), interpolation=cv2.INTER_AREA)
        panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (719, 48), (18, 18, 18), thickness=-1)
        cv2.putText(panel, label, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        panels.append(panel)
    cv2.imencode(".png", np.concatenate(panels, axis=1))[1].tofile(str(destination))


def main() -> int:
    expected = [f"frame_{index:04d}.bmp" for index in range(101)]
    raw_names = sorted(path.name for path in RAW.glob("*.bmp"))
    r109_names = sorted(path.name for path in R109.glob("*.bmp"))
    if raw_names != expected or r109_names != expected:
        raise RuntimeError("Unexpected filename set")

    mapping_path = PACKAGE / "source_mapping.csv"
    current_names = mapping_names(mapping_path)
    prior_names = mapping_names(PRIOR_MAPPING)
    if current_names != prior_names:
        raise RuntimeError("Even-frame selection differs from the previously verified package")

    with mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
        mapping_rows = list(csv.DictReader(handle))
    differing_hashes = sum(row["raw_sha256"] != row["r109_sha256"] for row in mapping_rows)
    if differing_hashes != 101:
        raise RuntimeError(f"Expected all 101 R109 outputs to differ from Raw, got {differing_hashes}")

    sample_shapes: dict[str, list[int]] = {}
    for index in (0, 25, 50, 75, 100):
        raw = read(RAW / f"frame_{index:04d}.bmp")
        output = read(R109 / f"frame_{index:04d}.bmp")
        if raw.shape != (5120, 5120) or output.shape != raw.shape:
            raise RuntimeError(f"Shape check failed for frame {index}")
        sample_shapes[f"frame_{index:04d}"] = list(output.shape)

    canonical = read(R109 / "frame_0000.bmp").astype(np.int16)
    reference = reconstruct_with_alternate_grid(read(RAW / "frame_0000.bmp")).astype(np.int16)
    tile_difference = np.abs(canonical - reference)
    tile_parity = {
        "reference": "same image reconstructed with an alternate 2048-pixel tile grid",
        "max_gray_level_difference": int(tile_difference.max()),
        "mean_gray_level_difference": float(tile_difference.mean()),
        "fraction_greater_than_one_gray_level": float(np.mean(tile_difference > 1)),
        "pass": bool(tile_difference.max() <= 1),
    }
    if not tile_parity["pass"]:
        raise RuntimeError("Tile-grid parity failed")

    make_preview(read(RAW / "frame_0050.bmp"), read(R109 / "frame_0050.bmp"), RECORDS / "preview_raw_vs_r109.png")

    raw_score = PACKAGE / "_gmf_scores" / "pitch1um_y100_raw" / "GMF_score.txt"
    r109_score = PACKAGE / "_gmf_scores" / "pitch1um_y100_r109_e48" / "GMF_score.txt"
    coordinate_results_present = raw_score.is_file() and r109_score.is_file()

    report = {
        "status": "pass",
        "raw_images": len(raw_names),
        "r109_images": len(r109_names),
        "identical_order_and_names": raw_names == r109_names == expected,
        "selection_matches_previous_verified_even_frame_package": current_names == prior_names,
        "all_outputs_differ_from_raw": differing_hashes == 101,
        "sample_shapes": sample_shapes,
        "tile_grid_parity": tile_parity,
        "coordinate_results_present": coordinate_results_present,
        "next_action": (
            "Review gmf_analysis/analysis_summary.json and the executed notebook."
            if coordinate_results_present
            else "Run external GMF for both rows in paths_for_gmf_tool.tsv and save each GMF_score.txt in its score folder."
        ),
    }
    (RECORDS / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
