"""Measure R109 control-map dynamics and V42 quality scaling over all 100 GMF frames."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "internal_dynamics"
OUTPUT.mkdir(parents=True, exist_ok=True)
CROP_SIZE = 1536

R111_LOADER = Path(
    r"D:\GMM_2_Final\Experiments\R111_R109V42ThesisReplacementQualification"
    r"\scripts\build_v42_external_gmf.py"
)
R109_ROOT = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def parse_score(path: Path, prefix: str) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [part.strip() for part in line.split(",")]
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        rows.append(
            {
                "frame_index": int(values["FileName"][6:10]),
                f"{prefix}_x": float(values["PosX"]),
                f"{prefix}_y": float(values["PosY"]),
                f"{prefix}_scale": float(values["Scale"]),
                f"{prefix}_score": float(values["Score0"]),
            }
        )
    return pd.DataFrame(rows).set_index("frame_index")


def corr(left: pd.Series, right: pd.Series) -> dict[str, float]:
    valid = pd.concat([left, right], axis=1).dropna()
    value, p = spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
    return {"spearman": float(value), "p_value": float(p)}


def main() -> int:
    raw_score = parse_score(Path(CONFIG["models"]["Raw"]["score"]), "raw")
    v42_score = parse_score(Path(CONFIG["models"]["V42 E120"]["score"]), "v42")
    r109_score = parse_score(Path(CONFIG["models"]["R109 E48"]["score"]), "r109")
    coordinates = raw_score.join(v42_score).join(r109_score)
    raw_dir = Path(CONFIG["models"]["Raw"]["image_dir"])

    v42_loader = load_module(R111_LOADER, "r112_dynamics_v42_loader")
    _, v42_model, device, temp_psf_dir, _, _ = v42_loader.load_model()
    sys.path.insert(0, str(R109_ROOT / "model"))
    from r109_model import build_model

    r109_payload = torch.load(Path(CONFIG["models"]["R109 E48"]["checkpoint"]), map_location=device, weights_only=False)
    r109_model = build_model().to(device)
    r109_model.load_state_dict(r109_payload["model"])
    r109_model.eval()

    yy, xx = torch.meshgrid(
        torch.arange(CROP_SIZE, device=device),
        torch.arange(CROP_SIZE, device=device),
        indexing="ij",
    )
    radius = torch.sqrt((xx - (CROP_SIZE - 1) / 2.0) ** 2 + (yy - (CROP_SIZE - 1) / 2.0) ** 2)
    annulus = ((radius >= 420.0) & (radius <= 650.0)).reshape(-1)
    rows: list[dict[str, object]] = []
    try:
        for frame_index, coordinate in coordinates.iterrows():
            name = f"frame_{int(frame_index):04d}.bmp"
            raw = read_gray(raw_dir / name)
            crop = cv2.getRectSubPix(raw, (CROP_SIZE, CROP_SIZE), (float(coordinate.raw_x), float(coordinate.raw_y)))
            tensor = torch.from_numpy(crop.astype(np.float32)[None, None] / 255.0).to(device)
            with torch.inference_mode():
                details = r109_model.forward_details(tensor)
                quality_scale = v42_model.quality_gate(tensor)
                quality_score = v42_model.quality_gate.last_quality_score
            support = details.support.detach().float().reshape(-1)
            width = details.width_gain.detach().float().reshape(-1)
            shift = details.normal_shift.detach().float().reshape(-1)
            rows.append(
                {
                    "frame_index": int(frame_index),
                    "r109_external_score": float(coordinate.r109_score),
                    "r109_external_scale": float(coordinate.r109_scale),
                    "r109_external_x": float(coordinate.r109_x),
                    "r109_external_y": float(coordinate.r109_y),
                    "v42_external_score": float(coordinate.v42_score),
                    "v42_external_scale": float(coordinate.v42_scale),
                    "v42_external_x": float(coordinate.v42_x),
                    "v42_external_y": float(coordinate.v42_y),
                    "v42_quality_score": float(quality_score.mean().cpu()),
                    "v42_quality_scale": float(quality_scale.mean().cpu()),
                    "r109_support_mean": float(support.mean().cpu()),
                    "r109_support_annulus_mean": float(support[annulus].mean().cpu()),
                    "r109_support_annulus_fraction_over_0p5": float((support[annulus] > 0.5).float().mean().cpu()),
                    "r109_width_gain_mean": float(width.mean().cpu()),
                    "r109_width_gain_annulus_mean": float(width[annulus].mean().cpu()),
                    "r109_width_gain_annulus_std": float(width[annulus].std(unbiased=True).cpu()),
                    "r109_shift_mean_px": float(shift.mean().cpu()),
                    "r109_shift_annulus_mean_px": float(shift[annulus].mean().cpu()),
                    "r109_shift_annulus_std_px": float(shift[annulus].std(unbiased=True).cpu()),
                    "r109_shift_annulus_abs_p95_px": float(torch.quantile(torch.abs(shift[annulus]), 0.95).cpu()),
                }
            )
            if len(rows) % 20 == 0:
                print(json.dumps({"done": len(rows), "total": 100}), flush=True)
    finally:
        if temp_psf_dir is not None:
            shutil.rmtree(temp_psf_dir, ignore_errors=True)

    frame_table = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    step_table = pd.DataFrame(
        {
            "from_frame": frame_table["frame_index"].iloc[:-1].to_numpy(),
            "to_frame": frame_table["frame_index"].iloc[1:].to_numpy(),
            "r109_external_y_error_abs_px": np.abs(np.diff(frame_table["r109_external_y"]) + 8.0),
            "v42_external_y_error_abs_px": np.abs(np.diff(frame_table["v42_external_y"]) + 8.0),
        }
    )
    dynamic_columns = [
        "r109_support_annulus_mean",
        "r109_support_annulus_fraction_over_0p5",
        "r109_width_gain_annulus_mean",
        "r109_width_gain_annulus_std",
        "r109_shift_annulus_mean_px",
        "r109_shift_annulus_std_px",
        "r109_shift_annulus_abs_p95_px",
        "v42_quality_score",
        "v42_quality_scale",
    ]
    for column in dynamic_columns:
        step_table[f"abs_delta_{column}"] = np.abs(np.diff(frame_table[column].to_numpy(dtype=float)))

    frame_table.to_csv(OUTPUT / "internal_state_per_frame.csv", index=False, encoding="utf-8-sig")
    step_table.to_csv(OUTPUT / "internal_state_per_step.csv", index=False, encoding="utf-8-sig")
    correlations = {
        "frame_to_external_score": {
            column: corr(frame_table[column], frame_table["r109_external_score"])
            for column in dynamic_columns
            if column.startswith("r109_")
        },
        "r109_step_error": {
            f"abs_delta_{column}": corr(
                step_table[f"abs_delta_{column}"], step_table["r109_external_y_error_abs_px"]
            )
            for column in dynamic_columns
            if column.startswith("r109_")
        },
        "v42_step_error": {
            f"abs_delta_{column}": corr(
                step_table[f"abs_delta_{column}"], step_table["v42_external_y_error_abs_px"]
            )
            for column in dynamic_columns
            if column.startswith("v42_")
        },
    }
    summary = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "frames": len(frame_table),
        "steps": len(step_table),
        "frame_summary": frame_table[dynamic_columns].agg(["mean", "std", "min", "max"]).to_dict(),
        "correlations": correlations,
        "interpretation_boundary": "Associations do not prove component causality; component ablations still require external GMF confirmation.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "frames": len(frame_table), "steps": len(step_table)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
