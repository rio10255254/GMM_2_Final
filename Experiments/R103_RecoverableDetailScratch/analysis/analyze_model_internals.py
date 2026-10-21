"""Branch use, cancellation, clipping, translation response, and tile parity for R103 E48."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
from reconstruct import reconstruct_full_reference, reconstruct_tensor  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "model_internals"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_model(device: torch.device) -> torch.nn.Module:
    checkpoint = Path(RUN["weights_dir"]) / "epoch_048.pth.tar"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]), contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]), combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(device)
    rows: list[dict[str, object]] = []
    shift_rows: list[dict[str, object]] = []
    tile_rows: list[dict[str, object]] = []
    for source_name in CONFIG["validation"]["real_preview_sources"]:
        source_path = Path(source_name)
        image = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(source_path)
        tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
        with torch.inference_mode():
            details = model.forward_details(tensor)
        branches = {
            "low": details.low_delta.float(),
            "contour": details.contour_delta.float(),
            "texture": details.texture_delta.float(),
        }
        branch_abs = {name: float(value.abs().mean()) for name, value in branches.items()}
        total_abs = float(details.total_delta.float().abs().mean())
        rows.append({
            "image": source_path.stem,
            **{f"{name}_mean_signed": float(value.mean()) for name, value in branches.items()},
            **{f"{name}_mean_abs": value for name, value in branch_abs.items()},
            "total_mean_signed": float(details.total_delta.float().mean()),
            "total_mean_abs": total_abs,
            "cancellation_fraction": float(1.0 - total_abs / max(sum(branch_abs.values()), 1e-12)),
            "contour_confidence_mean": float(details.contour_confidence.float().mean()),
            "contour_confidence_std": float(details.contour_confidence.float().std()),
            "texture_confidence_mean": float(details.texture_confidence.float().mean()),
            "texture_confidence_std": float(details.texture_confidence.float().std()),
            "low_clip_fraction": float((details.output <= 0).float().mean()),
            "high_clip_fraction": float((details.output >= 1).float().mean()),
        })
        reference = details.output.float()
        for dx, dy in ((1, 0), (0, 1), (3, 5), (8, 8)):
            shifted_input = torch.roll(tensor, shifts=(dy, dx), dims=(-2, -1))
            with torch.inference_mode():
                shifted_output = model(shifted_input).float()
            expected = torch.roll(reference, shifts=(dy, dx), dims=(-2, -1))
            margin = min(128, max(8, (min(tensor.shape[-2:]) - 1) // 4))
            difference = (shifted_output - expected).abs()[..., margin:-margin, margin:-margin]
            if difference.numel() == 0:
                raise RuntimeError(f"Translation comparison crop is empty for {source_path}")
            shift_rows.append({
                "image": source_path.stem, "dx_px": dx, "dy_px": dy,
                "mean_abs_error": float(difference.mean()), "max_abs_error": float(difference.max()),
            })
        with torch.inference_mode():
            full = reconstruct_full_reference(model, tensor, core_size=512, halo=128)
            tiled = reconstruct_tensor(model, tensor, core_size=512, halo=128, tile_batch=4)
        difference = (full - tiled).abs()
        tile_rows.append({
            "image": source_path.stem, "mean_abs_error": float(difference.mean()),
            "p99_abs_error": float(torch.quantile(difference.flatten(), .99)),
            "max_abs_error": float(difference.max()),
        })
        print(f"[internal] {source_path.stem}", flush=True)
    branches = pd.DataFrame(rows)
    shifts = pd.DataFrame(shift_rows)
    tiles = pd.DataFrame(tile_rows)
    branches.to_csv(OUTPUT / "branch_statistics.csv", index=False)
    shifts.to_csv(OUTPUT / "translation_equivariance.csv", index=False)
    tiles.to_csv(OUTPUT / "tile_parity.csv", index=False)
    result = {
        "status": "complete", "checkpoint_epoch": 48,
        "branch_median": branches.select_dtypes(include=[np.number]).median().to_dict(),
        "translation_mean_abs_median": float(shifts["mean_abs_error"].median()),
        "translation_mean_abs_max": float(shifts["mean_abs_error"].max()),
        "tile_mean_abs_median": float(tiles["mean_abs_error"].median()),
        "tile_mean_abs_max": float(tiles["mean_abs_error"].max()),
        "tile_max_abs_max": float(tiles["max_abs_error"].max()),
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
