"""Audit whether newly strong 5x edges recover weak source structure or hallucinate flat-region contours."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "five_x_edge_alignment"
RAW_ROOT = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs")
INFER_PATH = ROOT / "scripts" / "infer_no_radiometry_folder.py"
SEQUENCES = ("5x_0p5um", "5x_1um")
FRAME_INDICES = (0, 12, 24, 36, 49)
GUARDS = (0.12, 0.18, 0.25)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


infer = load_module("r108c_5x_infer", INFER_PATH)


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Could not read {path}")
    return value


def write_image(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, value)
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def gradient(value: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Match the locked appearance audit exactly: one-pixel Gaussian smoothing
    # before the Sobel gradient.  This keeps the old 15% warning reproducible.
    image = cv2.GaussianBlur(value.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
    return gx, gy, np.hypot(gx, gy)


def distance_to_support(support: np.ndarray) -> np.ndarray:
    return cv2.distanceTransform((~support).astype(np.uint8), cv2.DIST_L2, 5)


def metrics(raw: np.ndarray, output: np.ndarray) -> tuple[dict[str, float], dict[str, np.ndarray]]:
    raw_gx, raw_gy, raw_gradient = gradient(raw)
    out_gx, out_gy, out_gradient = gradient(output)
    model_strong = out_gradient >= float(np.percentile(out_gradient, 95))
    raw_p85 = raw_gradient >= float(np.percentile(raw_gradient, 85))
    raw_p70 = raw_gradient >= float(np.percentile(raw_gradient, 70))
    raw_p60 = raw_gradient >= float(np.percentile(raw_gradient, 60))
    d85 = distance_to_support(raw_p85)
    d70 = distance_to_support(raw_p70)
    d60 = distance_to_support(raw_p60)
    suspicious85 = model_strong & (d85 > 3.0)
    unexplained70 = model_strong & (d70 > 3.0)
    confirmed_flat = model_strong & (d60 > 5.0)
    raw_norm = np.maximum(raw_gradient, 1e-6)
    out_norm = np.maximum(out_gradient, 1e-6)
    cosine = (raw_gx * out_gx + raw_gy * out_gy) / (raw_norm * out_norm)
    aligned_region = model_strong & (d70 <= 1.0) & (raw_gradient > 1e-3)
    rows = {
        "off_source_from_top15_fraction": float(np.mean(d85[model_strong] > 3.0)),
        "recovered_near_moderate_source_fraction": float(np.mean(d70[model_strong] <= 3.0)),
        "unexplained_from_top30_fraction": float(np.mean(d70[model_strong] > 3.0)),
        "confirmed_flat_fraction": float(np.mean(d60[model_strong] > 5.0)),
        "median_distance_to_top30_px": float(np.median(d70[model_strong])),
        "p95_distance_to_top30_px": float(np.percentile(d70[model_strong], 95)),
        "aligned_gradient_direction_fraction": float(np.mean(cosine[aligned_region] >= 0.8))
        if np.any(aligned_region)
        else 0.0,
        "mean_absolute_change_gray": float(np.mean(np.abs(output.astype(np.float32) - raw.astype(np.float32)))),
        "p95_absolute_change_gray": float(np.percentile(np.abs(output.astype(np.float32) - raw.astype(np.float32)), 95)),
    }
    masks = {
        "model_strong": model_strong,
        "suspicious85": suspicious85,
        "unexplained70": unexplained70,
        "confirmed_flat": confirmed_flat,
    }
    return rows, masks


def panel(value: np.ndarray, label: str) -> np.ndarray:
    shown = cv2.cvtColor(value, cv2.COLOR_GRAY2BGR) if value.ndim == 2 else value.copy()
    cv2.rectangle(shown, (0, 0), (min(shown.shape[1], 560), 48), (0, 0, 0), -1)
    cv2.putText(shown, label, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (255, 255, 255), 2, cv2.LINE_AA)
    return shown


def overlay(raw: np.ndarray, masks: dict[str, np.ndarray]) -> np.ndarray:
    shown = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
    weak_recovery = masks["suspicious85"] & ~masks["unexplained70"]
    unexplained = masks["unexplained70"] & ~masks["confirmed_flat"]
    shown[weak_recovery] = (255, 255, 0)  # cyan: close to a moderate source edge
    shown[unexplained] = (0, 165, 255)  # orange: away from top-30% source edges
    shown[masks["confirmed_flat"]] = (0, 0, 255)  # red: strong edge in a genuinely flat region
    return shown


def main() -> int:
    RESULT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    montage_rows: list[np.ndarray] = []
    loaded = {guard: infer.nr.load(guard) for guard in GUARDS}
    for sequence in SEQUENCES:
        paths = sorted((RAW_ROOT / sequence / "bmp").glob("frame_*.bmp"))
        if len(paths) != 50:
            raise RuntimeError(f"Expected 50 frames for {sequence}, found {len(paths)}")
        for frame_index in FRAME_INDICES:
            source = paths[frame_index]
            raw = read_gray(source)
            visual_panels = [panel(raw, f"RAW {sequence} frame {frame_index}")]
            for guard in GUARDS:
                models, selectors = loaded[guard]
                value = infer.tiled(models, selectors, raw.astype(np.float32) / 255.0, core=512, halo=192)
                output = np.round(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8)
                record, masks = metrics(raw, output)
                rows.append({"sequence": sequence, "frame_index": frame_index, "guard": guard, **record})
                destination = RESULT / "reconstructions" / f"g{guard:.2f}" / sequence / source.name
                write_image(destination, output)
                if frame_index == 24:
                    visual_panels.extend(
                        [
                            panel(output, f"R108C guard {guard:.2f}"),
                            panel(overlay(raw, masks), "cyan=weak source, orange=uncertain, red=flat"),
                        ]
                    )
            if frame_index == 24:
                scale = min(1.0, 560.0 / raw.shape[1])
                resized = [cv2.resize(item, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) for item in visual_panels]
                montage_rows.append(np.concatenate(resized, axis=1))
    table = RESULT / "per_frame.csv"
    with table.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary: list[dict[str, object]] = []
    numeric = [key for key in rows[0] if key not in {"sequence", "frame_index", "guard"}]
    for sequence in SEQUENCES:
        for guard in GUARDS:
            subset = [row for row in rows if row["sequence"] == sequence and row["guard"] == guard]
            summary.append(
                {
                    "sequence": sequence,
                    "guard": guard,
                    **{key: float(np.median([float(row[key]) for row in subset])) for key in numeric},
                }
            )
    summary_path = RESULT / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    write_image(RESULT / "representative_comparison.png", np.concatenate(montage_rows, axis=0))
    decision = {
        "status": "complete",
        "interpretation_rule": {
            "weak_source_recovery": "output top-5% edge is >3 px from raw top-15%, but within 3 px of raw top-30%",
            "confirmed_flat": "output top-5% edge is >5 px from raw top-40%",
        },
        "sampled_frames_per_sequence": len(FRAME_INDICES),
        "guards": list(GUARDS),
        "rows": len(rows),
    }
    (RESULT / "state.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
