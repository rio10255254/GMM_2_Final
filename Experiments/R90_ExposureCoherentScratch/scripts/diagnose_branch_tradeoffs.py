"""Attribute SEM exposure drift and 5x dark edges to R90 correction branches."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import pandas as pd
from scipy.io import loadmat
import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "early_stop_validation.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
BASE_MASK = Path(r"D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch\results\final_validation\sem_acm_epoch100\acm_validation\results\masks\acm_primary_masks.mat")
OUTPUT = ROOT / "results" / "early_stop_validation" / "branch_diagnostics"
SEM_EXPOSURES = (13, 17, 18, 19, 24)
BRANCHES = ("low_delta", "detail_delta", "edge_delta", "correction")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


@torch.inference_mode()
def reconstruct_details(inference, model, image: np.ndarray, device: torch.device) -> dict[str, np.ndarray]:
    tensor = inference.image_tensor(image, device)
    core, halo = 512, 192
    canvas, (height, width, grid_h, grid_w) = inference.canonical_canvas(tensor, core, halo)
    outputs = {key: torch.empty((grid_h, grid_w), dtype=torch.float32, device=device) for key in BRANCHES}
    for y in range(0, grid_h, core):
        for x in range(0, grid_w, core):
            tile = canvas[..., y:y + core + 2 * halo, x:x + core + 2 * halo]
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
                details = model(tile, return_details=True)
            for key in BRANCHES:
                outputs[key][y:y + core, x:x + core] = details[key][0, 0, halo:halo + core, halo:halo + core].float()
    return {key: value[:height, :width].cpu().numpy() for key, value in outputs.items()}


def extract_cell(image: np.ndarray, center: np.ndarray, half: int) -> np.ndarray:
    cx, cy = np.rint(center).astype(int)
    padded = np.pad(image, half, mode="symmetric")
    cx += half
    cy += half
    return padded[cy - half:cy + half, cx - half:cx + half]


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    stages = [int(value) for value in protocol["stage_candidates"]]
    checkpoint_root = Path(protocol["checkpoint_root"])
    sem_root = Path(protocol["development_arms"]["sem_contour"]["optical_inputs"])
    base = loadmat(BASE_MASK, variable_names=["opt_centers", "cell_half"])
    centers = np.asarray(base["opt_centers"], dtype=float)
    half = int(np.asarray(base["cell_half"]).squeeze())
    yy, xx = np.mgrid[:2 * half, :2 * half]
    radius = np.hypot(xx - (2 * half - 1) / 2, yy - (2 * half - 1) / 2)
    regions = {
        "inside": radius < 25,
        "edge_annulus": (radius >= 35) & (radius < 42),
        "outside": (radius >= 47) & (radius < 51),
    }
    five_x_path = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_0p5um\bmp\frame_0024.bmp")
    five_x = read_gray(five_x_path)
    raw_gradient = gradient_magnitude(five_x)
    raw_support = raw_gradient >= float(np.percentile(raw_gradient, 85))
    five_x_edge_band = cv2.dilate(raw_support.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    inference = load_module("r90_branch_diagnostic_inference", INFERENCE)
    sem_rows: list[dict[str, Any]] = []
    five_x_rows: list[dict[str, Any]] = []
    for epoch in stages:
        checkpoint = checkpoint_root / f"epoch_{epoch:03d}.pth.tar"
        if sha256_file(checkpoint) != protocol["checkpoint_sha256"][str(epoch)]:
            raise RuntimeError(f"E{epoch}: checkpoint hash mismatch")
        model, payload = inference.load_model(checkpoint, device)
        for exposure in SEM_EXPOSURES:
            image = read_gray(sem_root / f"{exposure}.bmp")
            details = reconstruct_details(inference, model, image, device)
            for position, center in enumerate(centers, start=1):
                for branch in BRANCHES:
                    cell = extract_cell(details[branch] * 255.0, center, half)
                    branch_gradient = gradient_magnitude(cell)
                    for region, mask in regions.items():
                        sem_rows.append({
                            "epoch": epoch,
                            "exposure": exposure,
                            "grid_position": position,
                            "branch": branch,
                            "region": region,
                            "mean_gray": float(cell[mask].mean()),
                            "median_gray": float(np.median(cell[mask])),
                            "p05_gray": float(np.percentile(cell[mask], 5)),
                            "p95_gray": float(np.percentile(cell[mask], 95)),
                            "mean_gradient_gray": float(branch_gradient[mask].mean()),
                        })
        if epoch >= 35:
            details = reconstruct_details(inference, model, five_x, device)
            dark_mask = five_x_edge_band & (details["correction"] * 255.0 < -10.0)
            for branch in BRANCHES:
                values = details[branch][five_x_edge_band] * 255.0
                dark_values = details[branch][dark_mask] * 255.0 if dark_mask.any() else np.asarray([], dtype=np.float32)
                five_x_rows.append({
                    "epoch": epoch,
                    "branch": branch,
                    "edge_band_median_gray": float(np.median(values)),
                    "edge_band_p05_gray": float(np.percentile(values, 5)),
                    "edge_band_fraction_below_minus2": float(np.mean(values < -2.0)),
                    "edge_band_fraction_below_minus5": float(np.mean(values < -5.0)),
                    "output_dark_edge_fraction": float(np.mean(dark_mask[five_x_edge_band])),
                    "mean_branch_on_output_dark_pixels_gray": float(dark_values.mean()) if len(dark_values) else 0.0,
                    "p05_branch_on_output_dark_pixels_gray": float(np.percentile(dark_values, 5)) if len(dark_values) else 0.0,
                })
        del model, payload
        torch.cuda.empty_cache()
        print(json.dumps({"epoch": epoch, "sem_exposures": list(SEM_EXPOSURES), "five_x": epoch >= 35}), flush=True)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    sem = pd.DataFrame(sem_rows)
    five = pd.DataFrame(five_x_rows)
    sem.to_csv(OUTPUT / "sem_branch_per_position.csv", index=False, encoding="utf-8-sig")
    five.to_csv(OUTPUT / "five_x_branch_summary.csv", index=False, encoding="utf-8-sig")
    sem_summary = sem.groupby(["epoch", "exposure", "branch", "region"], observed=True)[[
        "mean_gray", "median_gray", "p05_gray", "p95_gray", "mean_gradient_gray"
    ]].median().reset_index()
    sem_summary.to_csv(OUTPUT / "sem_branch_summary.csv", index=False, encoding="utf-8-sig")

    exposure18 = sem_summary.loc[sem_summary["exposure"] == 18]
    diagnostic: dict[str, Any] = {"status": "complete", "sem": {}, "five_x": {}}
    for epoch in stages:
        diagnostic["sem"][str(epoch)] = {}
        for branch in BRANCHES:
            selected = exposure18.loc[(exposure18["epoch"] == epoch) & (exposure18["branch"] == branch)].set_index("region")
            diagnostic["sem"][str(epoch)][branch] = {
                "inside_mean_gray": float(selected.loc["inside", "mean_gray"]),
                "edge_annulus_mean_gray": float(selected.loc["edge_annulus", "mean_gray"]),
                "outside_mean_gray": float(selected.loc["outside", "mean_gray"]),
                "edge_minus_outside_gray": float(selected.loc["edge_annulus", "mean_gray"] - selected.loc["outside", "mean_gray"]),
            }
    for epoch in sorted(five["epoch"].unique()):
        selected = five.loc[five["epoch"] == epoch].set_index("branch")
        diagnostic["five_x"][str(int(epoch))] = {
            branch: {
                "output_dark_edge_fraction": float(selected.loc[branch, "output_dark_edge_fraction"]),
                "mean_branch_on_output_dark_pixels_gray": float(selected.loc[branch, "mean_branch_on_output_dark_pixels_gray"]),
                "edge_band_fraction_below_minus5": float(selected.loc[branch, "edge_band_fraction_below_minus5"]),
            }
            for branch in BRANCHES
        }
    (OUTPUT / "summary.json").write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(diagnostic, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
