"""Compare low- and high-frequency reconstruction residuals on shared Raw-centered crops."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "residual_bands"
OUTPUT.mkdir(parents=True, exist_ok=True)
CROP_SIZE = 1400
DOWNSAMPLE = 2


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def scores(path: Path, prefix: str) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        rows.append(
            {
                "frame_index": int(values["FileName"][6:10]),
                f"{prefix}_x": float(values["PosX"]),
                f"{prefix}_y": float(values["PosY"]),
                f"{prefix}_score": float(values["Score0"]),
            }
        )
    return pd.DataFrame(rows).set_index("frame_index")


def correlation(left: pd.Series, right: pd.Series) -> dict[str, float]:
    value, p = spearmanr(left, right)
    return {"spearman": float(value), "p_value": float(p)}


def main() -> int:
    raw_coords = scores(Path(PROJECT_ROOT / CONFIG["models"]["Raw"]["score"]), "raw")
    v42_coords = scores(Path(PROJECT_ROOT / CONFIG["models"]["V42 E120"]["score"]), "v42")
    r109_coords = scores(Path(PROJECT_ROOT / CONFIG["models"]["R109 E48"]["score"]), "r109")
    coordinates = raw_coords.join(v42_coords).join(r109_coords)
    directories = {arm: Path(PROJECT_ROOT / CONFIG["models"][arm]["image_dir"]) for arm in ("Raw", "V42 E120", "R109 E48")}
    rows: list[dict[str, object]] = []
    yy, xx = np.indices((CROP_SIZE // DOWNSAMPLE, CROP_SIZE // DOWNSAMPLE), dtype=np.float32)
    radius = np.sqrt((xx - (CROP_SIZE / DOWNSAMPLE - 1) / 2.0) ** 2 + (yy - (CROP_SIZE / DOWNSAMPLE - 1) / 2.0) ** 2)
    annulus = (radius >= 210.0) & (radius <= 325.0)
    for frame_index, coordinate in coordinates.iterrows():
        name = f"frame_{int(frame_index):04d}.bmp"
        center = (float(coordinate.raw_x), float(coordinate.raw_y))
        images = {
            arm: cv2.resize(
                cv2.getRectSubPix(read_gray(directory / name), (CROP_SIZE, CROP_SIZE), center),
                (CROP_SIZE // DOWNSAMPLE, CROP_SIZE // DOWNSAMPLE),
                interpolation=cv2.INTER_AREA,
            ).astype(np.float32)
            for arm, directory in directories.items()
        }
        raw = images["Raw"]
        for arm in ("V42 E120", "R109 E48"):
            residual = images[arm] - raw
            low = cv2.GaussianBlur(residual, (0, 0), 4.0)
            high = residual - low
            total_mae = float(np.mean(np.abs(residual)))
            rows.append(
                {
                    "arm": arm,
                    "frame_index": int(frame_index),
                    "external_score": float(coordinate.v42_score if arm == "V42 E120" else coordinate.r109_score),
                    "external_y": float(coordinate.v42_y if arm == "V42 E120" else coordinate.r109_y),
                    "residual_total_mae_gray": total_mae,
                    "residual_low_mae_gray": float(np.mean(np.abs(low))),
                    "residual_low_fraction": float(np.mean(np.abs(low)) / max(total_mae, 1e-12)),
                    "residual_high_rms_gray": float(np.sqrt(np.mean(high**2))),
                    "annulus_residual_mean_gray": float(np.mean(residual[annulus])),
                    "annulus_residual_std_gray": float(np.std(residual[annulus], ddof=1)),
                    "annulus_low_std_gray": float(np.std(low[annulus], ddof=1)),
                    "annulus_high_rms_gray": float(np.sqrt(np.mean(high[annulus] ** 2))),
                }
            )
        if frame_index % 20 == 0:
            print(json.dumps({"done": int(frame_index), "total": 100}), flush=True)

    frame_table = pd.DataFrame(rows)
    frame_table.to_csv(OUTPUT / "residual_band_per_frame.csv", index=False, encoding="utf-8-sig")
    summary = (
        frame_table.groupby("arm", as_index=False)
        .agg(
            frames=("frame_index", "count"),
            total_mae_median=("residual_total_mae_gray", "median"),
            low_mae_median=("residual_low_mae_gray", "median"),
            low_fraction_median=("residual_low_fraction", "median"),
            low_fraction_std=("residual_low_fraction", "std"),
            high_rms_median=("residual_high_rms_gray", "median"),
            annulus_residual_mean_std=("annulus_residual_mean_gray", "std"),
            annulus_low_std_median=("annulus_low_std_gray", "median"),
            annulus_high_rms_median=("annulus_high_rms_gray", "median"),
        )
    )
    summary.to_csv(OUTPUT / "residual_band_summary.csv", index=False, encoding="utf-8-sig")

    step_rows: list[pd.DataFrame] = []
    correlation_results: dict[str, object] = {}
    feature_columns = [
        "residual_total_mae_gray",
        "residual_low_mae_gray",
        "residual_low_fraction",
        "residual_high_rms_gray",
        "annulus_residual_mean_gray",
        "annulus_low_std_gray",
        "annulus_high_rms_gray",
    ]
    for arm, group in frame_table.groupby("arm", sort=False):
        group = group.sort_values("frame_index").reset_index(drop=True)
        step = pd.DataFrame(
            {
                "arm": arm,
                "from_frame": group["frame_index"].iloc[:-1].to_numpy(),
                "to_frame": group["frame_index"].iloc[1:].to_numpy(),
                "external_y_error_abs_px": np.abs(np.diff(group["external_y"]) + 8.0),
            }
        )
        for column in feature_columns:
            step[f"abs_delta_{column}"] = np.abs(np.diff(group[column]))
        step_rows.append(step)
        correlation_results[arm] = {
            "frame_score": {column: correlation(group[column], group["external_score"]) for column in feature_columns},
            "step_error": {
                f"abs_delta_{column}": correlation(step[f"abs_delta_{column}"], step["external_y_error_abs_px"])
                for column in feature_columns
            },
        }
    step_table = pd.concat(step_rows, ignore_index=True)
    step_table.to_csv(OUTPUT / "residual_band_per_step.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "summary": summary.to_dict(orient="records"),
        "correlations": correlation_results,
        "interpretation_boundary": "Residual-band correlations are associative and do not prove a causal GMF mechanism.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "frames": len(frame_table), "steps": len(step_table)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
