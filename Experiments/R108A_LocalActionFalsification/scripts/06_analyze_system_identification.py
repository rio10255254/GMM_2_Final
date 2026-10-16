"""Extract frozen R61/R79 transfer behavior from controlled probes."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.special import expit


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "system_identification_probes"
RESULT = ROOT / "results" / "system_identification"
REPORT = ROOT / "reports" / "06_FROZEN_MODEL_SYSTEM_IDENTIFICATION.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
MODELS = {
    "Raw": DATA / "input",
    "R61_full": RESULT / "inference_runs/R61_full/reconstruct_progress_best_tradeoff_in_input_20260623_200020/R61_full",
    "R61_zero_optics": RESULT / "inference_runs/R61_zero_optics/reconstruct_progress_best_tradeoff_in_input_20260623_200020/R61_zero_optics",
    "R79E23": RESULT / "outputs/R79E23",
    "R79E100": RESULT / "outputs/R79E100",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image.astype(np.float32)


def transition(profile: np.ndarray) -> dict[str, float]:
    outside = float(np.median(profile[:96])); inside = float(np.median(profile[-96:]))
    signed = inside - outside
    normalized = (profile - outside) / (signed if abs(signed) >= 1e-6 else 1.0)
    derivative = np.maximum(np.diff(normalized), 0.0)
    mass = float(derivative.sum())
    midpoints = np.arange(len(profile) - 1, dtype=np.float32) + 0.5
    if mass < 0.1:
        center = width = float("nan")
    else:
        cumulative = np.cumsum(derivative) / mass
        q10 = float(midpoints[np.argmax(cumulative >= 0.10)])
        q50 = float(midpoints[np.argmax(cumulative >= 0.50)])
        q90 = float(midpoints[np.argmax(cumulative >= 0.90)])
        center, width = q50, q90 - q10
    low, high = min(outside, inside), max(outside, inside)
    overshoot = np.maximum(low - profile, 0) + np.maximum(profile - high, 0)
    return {
        "outside": outside,
        "inside": inside,
        "contrast": abs(signed),
        "center": center,
        "width": width,
        "overshoot_mean": float(overshoot.mean()),
        "overshoot_max": float(overshoot.max()),
    }


def edge_metrics(image: np.ndarray, expected_center: float = 255.5) -> dict[str, float]:
    profile = image[64:-64].mean(axis=0)
    radius = 48
    start = max(0, int(round(expected_center)) - radius)
    stop = min(len(profile), int(round(expected_center)) + radius)
    x = np.arange(start, stop, dtype=np.float64)
    y = profile[start:stop].astype(np.float64)
    outside0 = float(np.median(y[:12])); inside0 = float(np.median(y[-12:]))
    def predict(parameters):
        outside, inside, center, log_scale, slope = parameters
        return outside + slope * (x - center) + (inside - outside) * expit((x - center) / np.exp(log_scale))
    initial = np.asarray([outside0, inside0, expected_center, math.log(1.5), 0.0], dtype=np.float64)
    lower = np.asarray([-32.0, -32.0, expected_center - 12.0, math.log(0.12), -0.75])
    upper = np.asarray([287.0, 287.0, expected_center + 12.0, math.log(24.0), 0.75])
    try:
        fit = least_squares(lambda parameters: predict(parameters) - y, initial, bounds=(lower, upper), loss="soft_l1", f_scale=1.5, max_nfev=300)
        outside, inside, center, log_scale, slope = fit.x
        scale = float(np.exp(log_scale))
        fitted = predict(fit.x)
        low = np.minimum(fitted, np.roll(fitted, 1)); high = np.maximum(fitted, np.roll(fitted, 1))
        residual = y - fitted
        result = {
            "outside": float(outside), "inside": float(inside), "contrast": float(abs(inside-outside)),
            "center": float(center), "width": float(2.0 * math.log(9.0) * scale),
            "overshoot_mean": float(np.mean(np.maximum(np.abs(residual)-2.0, 0.0))),
            "overshoot_max": float(np.max(np.abs(residual))),
            "fit_rmse": float(np.sqrt(np.mean(residual * residual))),
            "fit_success": bool(fit.success),
        }
    except Exception:
        result = transition(profile[start:stop])
        if np.isfinite(result["center"]):
            result["center"] += start
        result["fit_rmse"] = float("nan"); result["fit_success"] = False
    left = profile[32:144] - np.median(profile[32:144])
    right = profile[-144:-32] - np.median(profile[-144:-32])
    result["off_transition_artifact_std"] = float(np.std(np.concatenate([left, right])))
    return result


def sinusoid_metrics(image: np.ndarray, period: float, angle_deg: float) -> dict[str, float]:
    margin = 32
    value = image[margin:-margin, margin:-margin]
    yy, xx = np.mgrid[margin:image.shape[0]-margin, margin:image.shape[1]-margin].astype(np.float64)
    angle = math.radians(angle_deg)
    coordinate = xx * math.cos(angle) + yy * math.sin(angle)
    phase = 2.0 * math.pi * coordinate / period
    design = np.stack([np.ones_like(phase), np.sin(phase), np.cos(phase), (xx-xx.mean())/image.shape[1], (yy-yy.mean())/image.shape[0]], axis=-1).reshape(-1, 5)
    coef, *_ = np.linalg.lstsq(design, value.reshape(-1).astype(np.float64), rcond=None)
    fitted = design @ coef
    amplitude = float(np.hypot(coef[1], coef[2]))
    phase_value = float(math.atan2(coef[2], coef[1]))
    residual = float(np.sqrt(np.mean((value.reshape(-1) - fitted) ** 2)))
    return {"amplitude_fit": amplitude, "phase_fit": phase_value, "harmonic_residual": residual, "mean_fit": float(coef[0])}


def wrap_phase(value: float) -> float:
    return float((value + math.pi) % (2.0 * math.pi) - math.pi)


def verify_inputs(metadata: pd.DataFrame) -> dict[str, object]:
    expected = set(metadata["filename"])
    result = {}
    for model, folder in MODELS.items():
        files = {path.name: path for path in folder.glob("*.bmp")}
        if set(files) != expected:
            raise RuntimeError(f"{model}: expected {len(expected)} files, got {len(files)}")
        result[model] = {"folder": str(folder), "files": len(files), "aggregate_sha256": hashlib.sha256("".join(sha256(files[name]) for name in sorted(files)).encode()).hexdigest()}
    return result


def make_contact_sheet(metadata: pd.DataFrame) -> None:
    selections = []
    edge = metadata[(metadata["kind"] == "edge") & (metadata["scale"] == 2.0) & (metadata["contrast"] == 100.0) & (metadata["polarity"] == 1.0)].iloc[0]
    selections.append(edge)
    selections.append(metadata[(metadata["kind"] == "edge_illum") & (metadata["scale"] == 2.5) & (metadata["illumination"] == 90.0)].iloc[0])
    selections.append(metadata[(metadata["kind"] == "sinusoid") & (metadata["period"] == 8.0) & (metadata["amplitude"] == 15.0) & (metadata["angle_deg"] == 0.0)].iloc[0])
    selections.append(metadata[(metadata["kind"] == "flat_noise") & (metadata["level"] == 144.0) & (metadata["noise_sigma"] == 5.0)].iloc[0])
    tile = 256
    names = list(MODELS)
    canvas = np.zeros((len(selections) * tile, len(names) * tile), dtype=np.uint8)
    for row_index, record in enumerate(selections):
        for col, model in enumerate(names):
            image = read_gray(MODELS[model] / record["filename"])
            image = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA).astype(np.uint8)
            canvas[row_index*tile:(row_index+1)*tile, col*tile:(col+1)*tile] = image
            cv2.putText(canvas, model, (col*tile+6, row_index*tile+23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 255, 2, cv2.LINE_AA)
            cv2.putText(canvas, model, (col*tile+6, row_index*tile+23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1, cv2.LINE_AA)
    cv2.imencode(".png", canvas)[1].tofile(str(RESULT / "controlled_probe_comparison.png"))


def main() -> int:
    metadata = pd.read_csv(DATA / "metadata.csv")
    audit = verify_inputs(metadata)
    edge_rows = []
    sinusoid_rows = []
    flat_rows = []
    impulse_rows = []
    for _, record in metadata.iterrows():
        images = {model: read_gray(folder / record["filename"]) for model, folder in MODELS.items()}
        raw = images["Raw"]
        if record["kind"] in ("edge", "edge_illum", "edge_asym"):
            expected_center = float(record.get("center", 255.5))
            raw_metrics = edge_metrics(raw, expected_center)
            for model, image in images.items():
                metrics = edge_metrics(image, expected_center)
                edge_rows.append({
                    "filename": record["filename"], "kind": record["kind"], "model": model,
                    "input_center_command": record.get("center", np.nan), "input_scale": record.get("scale", np.nan), "input_background": record.get("background", np.nan), "input_contrast": record.get("contrast", np.nan), "polarity": record.get("polarity", np.nan), "illumination": record.get("illumination", np.nan), "ghost": record.get("ghost", np.nan), "halo": record.get("halo", np.nan),
                    **metrics,
                    "center_shift_vs_raw": metrics["center"] - raw_metrics["center"],
                    "width_ratio_vs_raw": metrics["width"] / max(raw_metrics["width"], 1e-6),
                    "contrast_ratio_vs_raw": metrics["contrast"] / max(raw_metrics["contrast"], 1e-6),
                    "mean_abs_change_gray": float(np.mean(np.abs(image - raw))),
                })
        elif record["kind"] == "sinusoid":
            raw_metrics = sinusoid_metrics(raw, float(record["period"]), float(record["angle_deg"]))
            for model, image in images.items():
                metrics = sinusoid_metrics(image, float(record["period"]), float(record["angle_deg"]))
                sinusoid_rows.append({
                    "filename": record["filename"], "model": model, "period": float(record["period"]), "input_amplitude": float(record["amplitude"]), "angle_deg": float(record["angle_deg"]),
                    **metrics,
                    "amplitude_gain_vs_raw": metrics["amplitude_fit"] / max(raw_metrics["amplitude_fit"], 1e-8),
                    "phase_shift_vs_raw_rad": wrap_phase(metrics["phase_fit"] - raw_metrics["phase_fit"]),
                    "mean_abs_change_gray": float(np.mean(np.abs(image - raw))),
                })
        elif record["kind"] in ("flat", "flat_noise"):
            for model, image in images.items():
                flat_rows.append({
                    "filename": record["filename"], "kind": record["kind"], "model": model, "level": float(record["level"]), "noise_sigma": float(record["noise_sigma"]),
                    "mean": float(image.mean()), "std": float(image.std()), "mean_shift_vs_raw": float(image.mean() - raw.mean()),
                    "std_ratio_vs_raw": float(image.std() / max(raw.std(), 1e-6)), "mean_abs_change_gray": float(np.mean(np.abs(image - raw))),
                })
        elif record["kind"] == "impulse":
            yy, xx = np.mgrid[0:raw.shape[0], 0:raw.shape[1]]
            for model, image in images.items():
                baseline = float(np.median(image[:64, :64])); delta = image - baseline; weight = np.abs(delta); total = float(weight.sum()) + 1e-8
                cx = float((weight * xx).sum() / total); cy = float((weight * yy).sum() / total)
                impulse_rows.append({
                    "filename": record["filename"], "model": model, "input_blur_sigma": float(record["blur_sigma"]),
                    "baseline": baseline, "abs_mass": float(weight.sum()), "signed_mass": float(delta.sum()), "centroid_x": cx, "centroid_y": cy,
                    "centroid_shift_px": float(np.hypot(cx-SIZE_HALF, cy-SIZE_HALF)), "mean_abs_change_gray": float(np.mean(np.abs(image-raw))),
                })

    edge = pd.DataFrame(edge_rows); sinusoid_frame = pd.DataFrame(sinusoid_rows); flat = pd.DataFrame(flat_rows); impulse = pd.DataFrame(impulse_rows)
    translation_rows = []
    simple_edges = edge[edge["kind"] == "edge"]
    for keys, group in simple_edges.groupby(["model", "input_scale", "input_background", "input_contrast", "polarity"]):
        group = group.sort_values("input_center_command")
        if len(group) != 2:
            continue
        command = float(group["input_center_command"].iloc[-1] - group["input_center_command"].iloc[0])
        observed = float(group["center"].iloc[-1] - group["center"].iloc[0])
        translation_rows.append({
            "model": keys[0], "input_scale": keys[1], "input_background": keys[2], "input_contrast": keys[3], "polarity": keys[4],
            "command_px": command, "observed_px": observed, "response_ratio": observed / max(command, 1e-8), "absolute_error_px": abs(observed-command),
        })
    translation = pd.DataFrame(translation_rows)
    edge.to_csv(RESULT / "edge_response.csv", index=False, encoding="utf-8-sig")
    sinusoid_frame.to_csv(RESULT / "frequency_response.csv", index=False, encoding="utf-8-sig")
    flat.to_csv(RESULT / "flat_response.csv", index=False, encoding="utf-8-sig")
    impulse.to_csv(RESULT / "impulse_response.csv", index=False, encoding="utf-8-sig")
    translation.to_csv(RESULT / "subpixel_translation_response.csv", index=False, encoding="utf-8-sig")

    models = [model for model in MODELS if model != "Raw"]
    summary: dict[str, object] = {"status": "complete", "images": int(len(metadata)), "input_audit": audit, "models": {}, "frequency_by_period": {}}
    for model in models:
        e = edge[edge["model"] == model]
        s = sinusoid_frame[sinusoid_frame["model"] == model]
        f = flat[flat["model"] == model]
        phase_valid = s[s["amplitude_gain_vs_raw"] >= 0.20]
        t = translation[translation["model"] == model]
        summary["models"][model] = {
            "edge": {
                "median_center_shift_px": float(e["center_shift_vs_raw"].median()),
                "p95_abs_center_shift_px": float(e["center_shift_vs_raw"].abs().quantile(0.95)),
                "median_width_ratio": float(e["width_ratio_vs_raw"].median()),
                "median_contrast_ratio": float(e["contrast_ratio_vs_raw"].median()),
                "median_overshoot_mean_gray": float(e["overshoot_mean"].median()),
                "median_off_transition_artifact_std_gray": float(e["off_transition_artifact_std"].median()),
                "p95_off_transition_artifact_std_gray": float(e["off_transition_artifact_std"].quantile(0.95)),
                "median_abs_change_gray": float(e["mean_abs_change_gray"].median()),
            },
            "sinusoid": {
                "median_amplitude_gain": float(s["amplitude_gain_vs_raw"].median()),
                "p95_abs_phase_shift_rad": float(phase_valid["phase_shift_vs_raw_rad"].abs().quantile(0.95)) if len(phase_valid) else float("nan"),
                "phase_valid_observations": int(len(phase_valid)),
                "median_abs_change_gray": float(s["mean_abs_change_gray"].median()),
            },
            "flat": {
                "median_abs_mean_shift_gray": float(f["mean_shift_vs_raw"].abs().median()),
                "clean_flat_output_std_gray": float(f[f["kind"] == "flat"]["std"].median()),
                "noise_std_ratio_median": float(f[f["kind"] == "flat_noise"]["std_ratio_vs_raw"].median()),
            },
            "subpixel_translation": {
                "pairs": int(len(t)),
                "median_response_ratio": float(t["response_ratio"].median()),
                "median_absolute_error_px": float(t["absolute_error_px"].median()),
                "p95_absolute_error_px": float(t["absolute_error_px"].quantile(0.95)),
            },
        }
        summary["frequency_by_period"][model] = {
            str(period): float(group["amplitude_gain_vs_raw"].median())
            for period, group in s.groupby("period")
        }
    for kind in sorted(metadata["kind"].unique()):
        files = metadata[metadata["kind"] == kind]["filename"].tolist()
        diffs = []
        for filename in files:
            a = read_gray(MODELS["R61_full"] / filename); b = read_gray(MODELS["R61_zero_optics"] / filename)
            diffs.append(float(np.mean(np.abs(a-b))))
        summary.setdefault("r61_optics_ablation", {})[kind] = {"median_full_vs_zero_optics_gray": float(np.median(diffs)), "p95": float(np.quantile(diffs, 0.95))}

    (RESULT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    make_contact_sheet(metadata)
    lines = ["# Frozen R61/R79 System Identification", ""]
    for model in models:
        item = summary["models"][model]
        lines.extend([
            f"## {model}", "",
            f"- Edge width ratio: {item['edge']['median_width_ratio']:.3f}; contrast ratio: {item['edge']['median_contrast_ratio']:.3f}.",
            f"- Median/P95 center change: {item['edge']['median_center_shift_px']:.3f} / {item['edge']['p95_abs_center_shift_px']:.3f} px.",
            f"- Sinusoid amplitude gain: {item['sinusoid']['median_amplitude_gain']:.3f}; phase P95: {item['sinusoid']['p95_abs_phase_shift_rad']:.4f} rad.",
            f"- Noise standard-deviation ratio: {item['flat']['noise_std_ratio_median']:.3f}.", "",
        ])
    lines.append("The probes characterize frozen behavior; they do not rank real-image accuracy by themselves.")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


SIZE_HALF = 255.5


if __name__ == "__main__":
    raise SystemExit(main())
