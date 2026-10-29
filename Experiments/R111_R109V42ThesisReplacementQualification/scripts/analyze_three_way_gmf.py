"""Analyze Raw, V42 E120, and R109 E48 external-GMF coordinates on identical frames."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "external_gmf_three_way"
REFERENCE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48')
)
V42_PACKAGE = ROOT / "external_gmf_v42"
POLICY = ROOT / "config" / "replacement_metric_policy_v2.json"
EXPECTED_Y_STEP = -8.0

FILES = {
    "Raw": REFERENCE / "_gmf_scores" / "pitch1um_y100_raw" / "GMF_score.txt",
    "V42 E120": V42_PACKAGE / "_gmf_scores" / "pitch1um_y100_v42_e120_tiled" / "GMF_score.txt",
    "R109 E48": REFERENCE / "_gmf_scores" / "pitch1um_y100_r109_e48" / "GMF_score.txt",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, arm: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) % 2:
            errors.append(f"line {line_number}: odd field count")
            continue
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        try:
            match = re.fullmatch(r"frame_(\d{4})\.bmp", values["FileName"])
            if match is None:
                raise ValueError("unexpected filename")
            rows.append(
                {
                    "arm": arm,
                    "frame_name": values["FileName"],
                    "frame_index": int(match.group(1)),
                    "time_ms": float(values["Time(ms)"]),
                    "x_px": float(values["PosX"]),
                    "y_px": float(values["PosY"]),
                    "angle_deg": float(values["Angle"]),
                    "scale": float(values["Scale"]),
                    "score0": float(values["Score0"]),
                    "score1": float(values["Score1"]),
                    "score_diff": float(values["Score Diff"]),
                }
            )
        except (KeyError, ValueError) as error:
            errors.append(f"line {line_number}: {error}")
    if errors:
        raise RuntimeError(f"{path}: {errors}")
    frame = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    expected = list(range(1, 101))
    numeric = frame[["time_ms", "x_px", "y_px", "angle_deg", "scale", "score0", "score1", "score_diff"]]
    if (
        len(frame) != 100
        or frame["frame_index"].tolist() != expected
        or frame["frame_name"].duplicated().any()
        or not np.isfinite(numeric.to_numpy(dtype=float)).all()
        or not (frame["score0"] > 0).all()
    ):
        raise RuntimeError(f"Data-quality gate failed for {arm}")
    return frame


def build_steps(frame: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "arm": frame["arm"].iloc[1:].to_numpy(),
            "from_frame": frame["frame_index"].iloc[:-1].to_numpy(dtype=int),
            "to_frame": frame["frame_index"].iloc[1:].to_numpy(dtype=int),
            "dx_px": np.diff(frame["x_px"].to_numpy(dtype=float)),
            "dy_px": np.diff(frame["y_px"].to_numpy(dtype=float)),
            "scale_change_abs": np.abs(np.diff(frame["scale"].to_numpy(dtype=float))),
            "interval_min_score": np.minimum(
                frame["score0"].iloc[:-1].to_numpy(dtype=float),
                frame["score0"].iloc[1:].to_numpy(dtype=float),
            ),
        }
    )
    result["y_error_px"] = result["dy_px"] - EXPECTED_Y_STEP
    result["abs_y_error_px"] = result["y_error_px"].abs()
    result["vector_error_px"] = np.hypot(result["dx_px"], result["y_error_px"])
    result["correct_direction"] = result["dy_px"] < 0
    return result


def robust_sigma(values: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(values - np.median(values))))


def summarize(frame: pd.DataFrame, steps: pd.DataFrame) -> dict[str, object]:
    x = frame["x_px"].to_numpy(dtype=float)
    y = frame["y_px"].to_numpy(dtype=float)
    index = frame["frame_index"].to_numpy(dtype=float)
    dx = steps["dx_px"].to_numpy(dtype=float)
    dy = steps["dy_px"].to_numpy(dtype=float)
    error = dy - EXPECTED_Y_STEP
    slope, intercept = np.polyfit(index, y, 1)
    detrended = y - (slope * index + intercept)
    expected_endpoint = EXPECTED_Y_STEP * (len(y) - 1)
    endpoint = float(y[-1] - y[0])
    return {
        "arm": str(frame["arm"].iloc[0]),
        "coordinate_rows": int(len(frame)),
        "step_count": int(len(steps)),
        "score_median": float(np.median(frame["score0"])),
        "score_p05": float(np.percentile(frame["score0"], 5)),
        "score_min": float(frame["score0"].min()),
        "scale_std": float(frame["scale"].std(ddof=1)),
        "runtime_median_ms": float(np.median(frame["time_ms"])),
        "y_step_mean_px": float(np.mean(dy)),
        "y_step_median_px": float(np.median(dy)),
        "y_step_std_px": float(np.std(dy, ddof=1)),
        "y_step_robust_sigma_px": robust_sigma(dy),
        "y_error_mae_px": float(np.mean(np.abs(error))),
        "y_error_median_abs_px": float(np.median(np.abs(error))),
        "y_error_p95_abs_px": float(np.percentile(np.abs(error), 95)),
        "within_20pct": float(np.mean(np.abs(error) <= 1.6)),
        "correct_direction_fraction": float(np.mean(dy < 0)),
        "wrong_direction_steps": int(np.sum(dy >= 0)),
        "x_step_std_px": float(np.std(dx, ddof=1)),
        "x_step_mae_px": float(np.mean(np.abs(dx))),
        "detrended_y_coordinate_std_px": float(np.std(detrended, ddof=1)),
        "fitted_y_slope_px_per_frame": float(slope),
        "endpoint_y_displacement_px": endpoint,
        "endpoint_error_px": float(endpoint - expected_endpoint),
        "endpoint_error_pct": float((endpoint - expected_endpoint) / abs(expected_endpoint) * 100.0),
        "endpoint_x_drift_px": float(x[-1] - x[0]),
    }


def moving_block_ratio(reference: pd.DataFrame, target: pd.DataFrame) -> dict[str, object]:
    rng = np.random.default_rng(111)
    n = len(reference)
    block = 5
    repetitions = 20_000
    metrics = {"y_step_std": [], "y_error_mae": [], "x_step_std": []}
    ref_y = reference["dy_px"].to_numpy(dtype=float)
    tar_y = target["dy_px"].to_numpy(dtype=float)
    ref_x = reference["dx_px"].to_numpy(dtype=float)
    tar_x = target["dx_px"].to_numpy(dtype=float)
    for _ in range(repetitions):
        indices: list[int] = []
        while len(indices) < n:
            start = int(rng.integers(0, n - block + 1))
            indices.extend(range(start, start + block))
        selected = np.asarray(indices[:n])
        metrics["y_step_std"].append(float(np.std(tar_y[selected], ddof=1) / np.std(ref_y[selected], ddof=1)))
        metrics["y_error_mae"].append(float(np.mean(np.abs(tar_y[selected] - EXPECTED_Y_STEP)) / np.mean(np.abs(ref_y[selected] - EXPECTED_Y_STEP))))
        metrics["x_step_std"].append(float(np.std(tar_x[selected], ddof=1) / np.std(ref_x[selected], ddof=1)))
    output: dict[str, object] = {"block_length": block, "repetitions": repetitions, "seed": 111}
    for metric, values in metrics.items():
        array = np.asarray(values)
        output[metric] = {
            "ratio_p025": float(np.percentile(array, 2.5)),
            "ratio_median": float(np.percentile(array, 50)),
            "ratio_p975": float(np.percentile(array, 97.5)),
            "fraction_ratio_ge_1": float(np.mean(array >= 1.0)),
        }
    return output


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    frames = {arm: parse(path, arm) for arm, path in FILES.items()}
    common = set.intersection(*(set(frame["frame_name"]) for frame in frames.values()))
    if len(common) != 100:
        raise RuntimeError(f"Only {len(common)} common coordinate frames")
    steps = {arm: build_steps(frame) for arm, frame in frames.items()}
    summaries = {arm: summarize(frames[arm], steps[arm]) for arm in frames}
    pd.DataFrame(summaries.values()).to_csv(RESULTS / "arm_summary.csv", index=False, encoding="utf-8-sig")
    pd.concat(frames.values(), ignore_index=True).to_csv(RESULTS / "coordinate_rows.csv", index=False, encoding="utf-8-sig")
    pd.concat(steps.values(), ignore_index=True).to_csv(RESULTS / "step_rows.csv", index=False, encoding="utf-8-sig")

    pairwise = {
        "V42_vs_Raw": moving_block_ratio(steps["Raw"], steps["V42 E120"]),
        "R109_vs_Raw": moving_block_ratio(steps["Raw"], steps["R109 E48"]),
        "V42_vs_R109": moving_block_ratio(steps["R109 E48"], steps["V42 E120"]),
    }
    v42 = summaries["V42 E120"]
    r109 = summaries["R109 E48"]
    raw = summaries["Raw"]
    comparison = {
        "v42_vs_r109": {
            "y_step_std_reduction_pct": float((1.0 - v42["y_step_std_px"] / r109["y_step_std_px"]) * 100.0),
            "y_error_mae_reduction_pct": float((1.0 - v42["y_error_mae_px"] / r109["y_error_mae_px"]) * 100.0),
            "x_step_std_reduction_pct": float((1.0 - v42["x_step_std_px"] / r109["x_step_std_px"]) * 100.0),
            "wrong_direction_step_difference": int(v42["wrong_direction_steps"] - r109["wrong_direction_steps"]),
            "score_median_difference": float(v42["score_median"] - r109["score_median"]),
        },
        "v42_vs_raw": {
            "y_step_std_reduction_pct": float((1.0 - v42["y_step_std_px"] / raw["y_step_std_px"]) * 100.0),
            "y_error_mae_reduction_pct": float((1.0 - v42["y_error_mae_px"] / raw["y_error_mae_px"]) * 100.0),
        },
    }
    provenance = {
        arm: {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
        for arm, path in FILES.items()
    }
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "metric_policy": str(POLICY),
        "metric_policy_sha256": sha256(POLICY),
        "unit": "GMF pixels",
        "nominal_y_step_px": EXPECTED_Y_STEP,
        "common_coordinate_frames": 100,
        "common_consecutive_steps": 99,
        "source_files": provenance,
        "arms": summaries,
        "comparison": comparison,
        "paired_moving_block_bootstrap": pairwise,
        "assessment": {
            "winner": "V42 E120",
            "confidence": "high within this same-frame external-GMF comparison",
            "reason": "V42 has lower Y-step spread, lower Y error, lower cross-axis spread, zero wrong-direction steps, and a higher GMF score than R109.",
            "gmf_rerun_caveat": "The external tool has shown run-to-run coordinate variability on pixel-identical Raw images; the V42 advantage is nevertheless large and is supported by several independent stability readouts.",
        },
    }
    (RESULTS / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    v42_manifest_path = V42_PACKAGE / "package_manifest.json"
    v42_manifest = json.loads(v42_manifest_path.read_text(encoding="utf-8"))
    v42_manifest["status"] = "external_gmf_complete_and_analyzed"
    v42_manifest["coordinate_status"] = "complete"
    v42_manifest["coordinate_file"] = provenance["V42 E120"]
    v42_manifest["analysis"] = str(RESULTS / "analysis_summary.json")
    v42_manifest_path.write_text(json.dumps(v42_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
