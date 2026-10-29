"""Test non-trained residual projections for appearance stability, without claiming GMF scores."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "counterfactual_stability"
OUTPUT.mkdir(parents=True, exist_ok=True)
DOWNSAMPLE = 4
CROP_SMALL = 350


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def coordinates(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        rows.append(
            {
                "frame_index": int(values["FileName"][6:10]),
                "x": float(values["PosX"]),
                "y": float(values["PosY"]),
            }
        )
    return pd.DataFrame(rows).set_index("frame_index")


def ncc(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float64) - float(left.mean())
    b = right.astype(np.float64) - float(right.mean())
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.sum(a * b) / denominator)


def radial(image: np.ndarray) -> tuple[float, float, float]:
    yy, xx = np.indices(image.shape, dtype=np.float32)
    radius = np.sqrt((xx - (image.shape[1] - 1) / 2.0) ** 2 + (yy - (image.shape[0] - 1) / 2.0) ** 2)
    index = np.floor(radius).astype(np.int32)
    sums = np.bincount(index.ravel(), weights=image.astype(np.float64).ravel(), minlength=176)
    counts = np.bincount(index.ravel(), minlength=176)
    profile = sums[:175] / np.maximum(counts[:175], 1)
    peak = int(np.argmax(profile[75:170])) + 75
    baseline = 0.5 * (float(np.median(profile[20:75])) + float(np.median(profile[170:174])))
    threshold = baseline + 0.5 * (float(profile[peak]) - baseline)
    inner_candidates = np.flatnonzero(profile[:peak] <= threshold)
    outer_candidates = np.flatnonzero(profile[peak:] <= threshold)
    inner = float(inner_candidates[-1]) if len(inner_candidates) else np.nan
    outer = float(peak + outer_candidates[0]) if len(outer_candidates) else np.nan
    return float(peak * DOWNSAMPLE), float((outer - inner) * DOWNSAMPLE), float(profile[peak] - baseline)


def main() -> int:
    coords = coordinates(Path(PROJECT_ROOT / CONFIG["models"]["Raw"]["score"]))
    dirs = {arm: Path(PROJECT_ROOT / CONFIG["models"][arm]["image_dir"]) for arm in ("Raw", "V42 E120", "R109 E48")}
    variants: dict[str, list[np.ndarray]] = {
        "Raw": [],
        "V42 E120": [],
        "R109 current": [],
        "R109 residual blend 0.5": [],
        "R109 high-pass residual gain 1.0": [],
        "R109 high-pass residual gain 0.5": [],
        "R109 predictor high-pass anchor": [],
    }
    low_fraction: dict[str, list[float]] = {name: [] for name in variants}
    for frame_index, center in coords.iterrows():
        name = f"frame_{int(frame_index):04d}.bmp"
        small = {
            arm: cv2.resize(read_gray(directory / name), (1280, 1280), interpolation=cv2.INTER_AREA).astype(np.float32)
            for arm, directory in dirs.items()
        }
        raw = small["Raw"]
        model = small["R109 E48"]
        residual = model - raw
        low = cv2.GaussianBlur(residual, (0, 0), 2.0)
        high = residual - low
        model_low = cv2.GaussianBlur(model, (0, 0), 0.5)
        generated = {
            "Raw": raw,
            "V42 E120": small["V42 E120"],
            "R109 current": model,
            "R109 residual blend 0.5": raw + 0.5 * residual,
            "R109 high-pass residual gain 1.0": raw + high,
            "R109 high-pass residual gain 0.5": raw + 0.5 * high,
            "R109 predictor high-pass anchor": raw + 0.35 * (model - model_low),
        }
        center_small = (float(center.x / DOWNSAMPLE), float(center.y / DOWNSAMPLE))
        for variant, image in generated.items():
            clipped = np.clip(image, 0, 255).astype(np.uint8)
            crop = cv2.getRectSubPix(clipped, (CROP_SMALL, CROP_SMALL), center_small)
            variants[variant].append(crop)
            variant_residual = image - raw
            variant_low = cv2.GaussianBlur(variant_residual, (0, 0), 2.0)
            total_mae = float(np.mean(np.abs(variant_residual)))
            low_fraction[variant].append(float(np.mean(np.abs(variant_low)) / max(total_mae, 1e-12)))
        if frame_index % 20 == 0:
            print(json.dumps({"done": int(frame_index), "total": 100}), flush=True)

    rows = []
    for variant, crops in variants.items():
        stack = np.stack(crops).astype(np.float32)
        template = np.median(stack, axis=0)
        correlations = [ncc(crop, template) for crop in crops]
        radial_values = np.asarray([radial(crop) for crop in crops])
        rows.append(
            {
                "variant": variant,
                "frames": len(crops),
                "ncc_median": float(np.median(correlations)),
                "ncc_p05": float(np.percentile(correlations, 5)),
                "template_mae_median_gray": float(np.median(np.mean(np.abs(stack - template), axis=(1, 2)))),
                "ring_peak_radius_std_px": float(np.nanstd(radial_values[:, 0], ddof=1)),
                "ring_width_std_px": float(np.nanstd(radial_values[:, 1], ddof=1)),
                "ring_contrast_std_gray": float(np.nanstd(radial_values[:, 2], ddof=1)),
                "residual_low_fraction_median": float(np.median(low_fraction[variant])),
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(OUTPUT / "counterfactual_stability_summary.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "summary": summary.to_dict(orient="records"),
        "interpretation_boundary": "Appearance stability is not an external-GMF score; these variants require external confirmation.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "variants": len(summary)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
