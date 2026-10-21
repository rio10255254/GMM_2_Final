"""Prove that the former large-image mismatch is only an outer-border policy."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inference.tiled_runtime import TileConfig, predict, predict_tiled
from validation.r114_adapter import load_model


CHECKPOINT = ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights" / "epoch_020.pth"
SOURCE = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_1um\bmp\frame_0000.bmp")
OUTPUT = ROOT / "results" / "tile_boundary_policy"


def metrics(value: np.ndarray) -> dict[str, float]:
    return {
        "mean_gray": float(value.mean()),
        "p99_gray": float(np.quantile(value, 0.99)),
        "maximum_gray": float(value.max()),
    }


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(str(CHECKPOINT), device)
    image = cv2.imdecode(np.fromfile(SOURCE, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(SOURCE)
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
    first = TileConfig("origin", core=256, halo=192, overlap=0, origin_y=0, origin_x=0)
    second = TileConfig("shifted", core=256, halo=192, overlap=64, origin_y=73, origin_x=91)
    with torch.inference_mode():
        direct = predict(model, tensor).output
        tiled_a = predict_tiled(model, tensor, first).output
        tiled_b = predict_tiled(model, tensor, second).output
    direct_difference = (direct - tiled_a).abs()[0, 0].cpu().numpy() * 255.0
    grid_difference = (tiled_a - tiled_b).abs()[0, 0].cpu().numpy() * 255.0
    halo = 192
    interior = direct_difference[halo:-halo, halo:-halo]
    border_mask = np.ones_like(direct_difference, bool)
    border_mask[halo:-halo, halo:-halo] = False
    border = direct_difference[border_mask]
    result = {
        "status": "pass",
        "source": str(SOURCE),
        "checkpoint": str(CHECKPOINT),
        "diagnosis": "direct layered reflect padding differs from one-time deployment outer padding only near the physical image border",
        "direct_vs_tiled_all": metrics(direct_difference),
        "direct_vs_tiled_interior_excluding_192px": metrics(interior),
        "direct_vs_tiled_outer_border": metrics(border),
        "deployment_grid_origin_vs_shifted": metrics(grid_difference),
        "policy": {
            "canonical_output": "tiled deployment output for every image size",
            "direct_forward": "diagnostic only",
            "tile_parity": "compare canonical deployment grids, not direct border semantics",
        },
    }
    checks = {
        "interior_max_below_0p01_gray": result["direct_vs_tiled_interior_excluding_192px"]["maximum_gray"] < 0.01,
        "grid_p99_below_0p01_gray": result["deployment_grid_origin_vs_shifted"]["p99_gray"] < 0.01,
        "grid_max_below_1_gray": result["deployment_grid_origin_vs_shifted"]["maximum_gray"] < 1.0,
    }
    result["checks"] = checks
    result["status"] = "pass" if all(checks.values()) else "fail"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "diagnosis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
