"""Identify whether R79's SEM advantage is explainable by simple local optical bases."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RAW = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))
R79 = Path(str(PROJECT_ROOT / 'Experiments/R80_R79E23vsE100GeneralizationValidation/results/reconstructions/sem/R79E23'))
R108C = ROOT / "results" / "sem_no_radiometry_g0p25"
OUTPUT = ROOT / "results" / "r79_sem_action_basis"
SIGMAS = (0.6, 1.2, 2.4, 4.8, 9.6)


def read(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value.astype(np.float32) / 255.0


def basis(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    columns = []
    names = []
    for sigma in SIGMAS:
        blur = cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        columns.append(image - blur)
        names.append(f"highpass_sigma_{sigma:g}")
    broad = cv2.GaussianBlur(image, (0, 0), 12.0, borderType=cv2.BORDER_REFLECT_101)
    columns.append(broad - float(broad.mean()))
    names.append("broad_local_contrast")
    columns.append(image - float(image.mean()))
    names.append("global_contrast")
    columns.append(np.ones_like(image))
    names.append("constant")
    return np.stack(columns, axis=-1), names


def r2(y: np.ndarray, prediction: np.ndarray) -> float:
    residual = float(np.sum((y - prediction) ** 2))
    total = float(np.sum((y - float(y.mean())) ** 2))
    return 1.0 - residual / max(total, 1e-12)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(108990)
    sampled_x = []
    sampled_y = {"R79E23": [], "R108C": []}
    frames = []
    names: list[str] | None = None
    for path in sorted(RAW.glob("*.bmp")):
        raw = read(path)
        targets = {"R79E23": read(R79 / path.name), "R108C": read(R108C / path.name)}
        values, names = basis(raw)
        flat = values.reshape(-1, values.shape[-1])
        count = min(120_000, len(flat))
        selected = rng.choice(len(flat), count, replace=False)
        sampled_x.append(flat[selected])
        for model, target in targets.items():
            residual = (target - raw).reshape(-1)
            sampled_y[model].append(residual[selected])
        gx = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 1.0), cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 1.0), cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.hypot(gx, gy)
        edge15 = gradient >= np.percentile(gradient, 85)
        edge30 = gradient >= np.percentile(gradient, 70)
        residuals = {name: target - raw for name, target in targets.items()}
        denominator = np.sqrt(np.sum(residuals["R79E23"] ** 2) * np.sum(residuals["R108C"] ** 2))
        row = {"exposure": int(path.stem), "residual_cosine_R79_R108C": float(np.sum(residuals["R79E23"] * residuals["R108C"]) / max(float(denominator), 1e-12))}
        for model, residual in residuals.items():
            energy = residual ** 2
            row[f"{model}_mean_abs_gray"] = float(np.mean(np.abs(residual)) * 255.0)
            row[f"{model}_action_energy_top15_edge_fraction"] = float(energy[edge15].sum() / max(float(energy.sum()), 1e-12))
            row[f"{model}_action_energy_top30_edge_fraction"] = float(energy[edge30].sum() / max(float(energy.sum()), 1e-12))
        frames.append(row)
    assert names is not None
    x = np.concatenate(sampled_x, axis=0).astype(np.float64)
    fits = {}
    coefficient_rows = []
    for model, groups in sampled_y.items():
        y = np.concatenate(groups).astype(np.float64)
        coefficient, *_ = np.linalg.lstsq(x, y, rcond=1e-7)
        prediction = x @ coefficient
        fits[model] = {
            "sampled_pixels": len(y),
            "r2": r2(y, prediction),
            "residual_mae_gray": float(np.mean(np.abs(y - prediction)) * 255.0),
            "target_action_mae_gray": float(np.mean(np.abs(y)) * 255.0),
        }
        for name, value in zip(names, coefficient):
            coefficient_rows.append({"model": model, "basis": name, "coefficient": float(value)})
    frame_table = pd.DataFrame(frames)
    frame_table.to_csv(OUTPUT / "per_exposure.csv", index=False)
    pd.DataFrame(coefficient_rows).to_csv(OUTPUT / "global_coefficients.csv", index=False)
    summary = {
        "status": "complete",
        "basis_names": names,
        "fits": fits,
        "median_action": {
            column: float(frame_table[column].median()) for column in frame_table.columns if column != "exposure"
        },
        "interpretation": "High R2 means simple local optical bases explain the model action; low R2 implies nonlinear/content-dependent action.",
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
