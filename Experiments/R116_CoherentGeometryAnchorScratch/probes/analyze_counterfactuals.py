"""Locked internal readout for the four full R109 causal variants.

This deliberately does not pretend to be the external GMF.  It uses the
already-recorded Raw GMF coordinates only to keep the same physical object in
the crop, then measures appearance stability and a fixed-template surrogate.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "results" / "counterfactual_full_101"
OUTPUT = ROOT / "results" / "counterfactual_analysis"
RAW_SCORE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages\Pitch1um_Y_100_Raw_Even_R109E48\_gmf_scores\pitch1um_y100_raw\GMF_score.txt"
)
VARIANTS = (
    "r109_current",
    "r109_no_normal_shift",
    "raw_anchor_half_detail",
    "geometry_anchor_half_detail",
)
DOWNSAMPLE = 4
CROP_SIDE = 350
TEMPLATE_SIDE = 300
SEARCH_MARGIN = 48
EXPECTED_STEP_SMALL = -8.0 / DOWNSAMPLE


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def parse_coordinates(path: Path) -> pd.DataFrame:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        match = re.fullmatch(r"frame_(\d{4})\.bmp", values["FileName"])
        if match is None:
            raise RuntimeError(f"Bad coordinate line {line_number}")
        rows.append({
            "frame_index": int(match.group(1)),
            "x": float(values["PosX"]),
            "y": float(values["PosY"]),
        })
    frame = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    if frame["frame_index"].tolist() != list(range(1, 101)):
        raise RuntimeError("Raw coordinate population must be frame 0001 through 0100")
    return frame


def ncc(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float64) - float(left.mean())
    b = right.astype(np.float64) - float(right.mean())
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.sum(a * b) / denominator) if denominator > 0 else float("nan")


def subpixel_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left, center, right = map(float, values[index - 1:index + 2])
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1.0e-12:
        return float(index)
    return float(index + np.clip(0.5 * (left - right) / denominator, -1.0, 1.0))


def fixed_template(frames: list[np.ndarray], first_center: tuple[float, float]) -> dict[str, float]:
    template = cv2.getRectSubPix(frames[0], (TEMPLATE_SIDE, TEMPLATE_SIDE), first_center)
    coordinates = []
    scores = []
    for index, frame in enumerate(frames):
        predicted = (first_center[0], first_center[1] + index * EXPECTED_STEP_SMALL)
        side = TEMPLATE_SIDE + 2 * SEARCH_MARGIN
        search = cv2.getRectSubPix(frame, (side, side), predicted)
        surface = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, peak = cv2.minMaxLoc(surface)
        px = subpixel_peak(surface[int(peak[1]), :], int(peak[0]))
        py = subpixel_peak(surface[:, int(peak[0])], int(peak[1]))
        coordinates.append((
            (predicted[0] + px - SEARCH_MARGIN) * DOWNSAMPLE,
            (predicted[1] + py - SEARCH_MARGIN) * DOWNSAMPLE,
        ))
        scores.append(float(score))
    values = np.asarray(coordinates)
    dx = np.diff(values[:, 0])
    dy = np.diff(values[:, 1])
    return {
        "surrogate_y_step_mean_px": float(dy.mean()),
        "surrogate_y_step_std_px": float(dy.std(ddof=1)),
        "surrogate_y_step_mae_px": float(np.mean(np.abs(dy + 8.0))),
        "surrogate_x_step_std_px": float(dx.std(ddof=1)),
        "surrogate_wrong_direction_steps": int(np.sum(dy >= 0)),
        "surrogate_score_median": float(np.median(scores)),
    }


def analyze_variant(name: str, coordinates: pd.DataFrame) -> tuple[dict[str, object], list[dict[str, object]]]:
    frames: list[np.ndarray] = []
    crops: list[np.ndarray] = []
    per_frame = []
    for row in coordinates.itertuples(index=False):
        path = INPUT / name / f"frame_{int(row.frame_index):04d}.bmp"
        image = read_gray(path)
        small = cv2.resize(
            image, (image.shape[1] // DOWNSAMPLE, image.shape[0] // DOWNSAMPLE),
            interpolation=cv2.INTER_AREA,
        )
        center = (float(row.x / DOWNSAMPLE), float(row.y / DOWNSAMPLE))
        crop = cv2.getRectSubPix(small, (CROP_SIDE, CROP_SIDE), center)
        high = crop.astype(np.float32) - cv2.GaussianBlur(crop.astype(np.float32), (0, 0), 1.5)
        frames.append(small)
        crops.append(crop)
        per_frame.append({
            "variant": name,
            "frame_index": int(row.frame_index),
            "crop_mean_gray": float(crop.mean()),
            "crop_std_gray": float(crop.std(ddof=1)),
            "high_frequency_rms_gray": float(np.sqrt(np.mean(np.square(high)))),
        })
        if len(frames) % 20 == 0:
            print(json.dumps({"variant": name, "loaded": len(frames), "total": 100}), flush=True)
    stack = np.stack(crops).astype(np.float32)
    template = np.median(stack, axis=0)
    correlations = np.asarray([ncc(crop, template) for crop in crops])
    template_mae = np.mean(np.abs(stack - template), axis=(1, 2))
    first = coordinates.iloc[0]
    summary: dict[str, object] = {
        "variant": name,
        "frames": len(frames),
        "ncc_median": float(np.median(correlations)),
        "ncc_p05": float(np.percentile(correlations, 5)),
        "template_mae_median_gray": float(np.median(template_mae)),
        "crop_mean_std_gray": float(stack.mean(axis=(1, 2)).std(ddof=1)),
        "crop_contrast_std_gray": float(stack.std(axis=(1, 2), ddof=1).std(ddof=1)),
        "high_frequency_rms_median_gray": float(np.median([
            row["high_frequency_rms_gray"] for row in per_frame
        ])),
        **fixed_template(frames, (float(first.x / DOWNSAMPLE), float(first.y / DOWNSAMPLE))),
    }
    return summary, per_frame


def main() -> int:
    state = json.loads((INPUT / "counterfactual_state.json").read_text(encoding="utf-8"))
    if state.get("status") != "complete" or int(state.get("images", 0)) != 101:
        raise RuntimeError("Counterfactual generation is incomplete")
    coordinates = parse_coordinates(RAW_SCORE)
    summaries = []
    frames = []
    for variant in VARIANTS:
        summary, per_frame = analyze_variant(variant, coordinates)
        summaries.append(summary)
        frames.extend(per_frame)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).to_csv(
        OUTPUT / "variant_summary.csv", index=False, encoding="utf-8-sig",
    )
    pd.DataFrame(frames).to_csv(
        OUTPUT / "per_frame.csv", index=False, encoding="utf-8-sig",
    )
    payload = {
        "status": "complete",
        "population": "frame_0001.bmp through frame_0100.bmp",
        "raw_coordinate_source": str(RAW_SCORE),
        "variants": summaries,
        "surrogate_limit": "The fixed-template locator is directional only and cannot rank external GMF performance.",
        "external_gmf_still_required": True,
    }
    (OUTPUT / "analysis.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
