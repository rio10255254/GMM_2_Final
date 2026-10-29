"""Direct full-frame versus tiled parity on one real frame per magnification."""
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
PROJECT_ROOT = Path(__file__).resolve().parents[3]


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
SEQUENCES = json.loads(Path(str(PROJECT_ROOT / 'Experiments/R68_R61_RealFOVFeatureGeneralization/config/sequences.json')).read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "large_tile_parity"
SELECTED = ("5x_0p5um", "20x_0p5um", "50x_1um")


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
    for sequence in SELECTED:
        raw_path = sorted(Path(PROJECT_ROOT / SEQUENCES["sequences"][sequence]["raw_dir"]).glob("frame_*.bmp"))[0]
        image = cv2.imdecode(np.fromfile(raw_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(raw_path)
        tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        with torch.inference_mode(), torch.autocast(
            device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
        ):
            full = reconstruct_full_reference(model, tensor, core_size=512, halo=128)
            tiled = reconstruct_tensor(model, tensor, core_size=512, halo=128, tile_batch=4)
        difference = (full.float() - tiled.float()).abs()
        seam = torch.zeros_like(difference, dtype=torch.bool)
        for x in range(512, image.shape[1], 512):
            seam[..., max(0, x - 2):min(image.shape[1], x + 3)] = True
        for y in range(512, image.shape[0], 512):
            seam[..., max(0, y - 2):min(image.shape[0], y + 3), :] = True
        rows.append({
            "sequence": sequence, "height": image.shape[0], "width": image.shape[1],
            "mean_abs_error": float(difference.mean()),
            "p99_abs_error": float(torch.quantile(difference.flatten(), .99)),
            "max_abs_error": float(difference.max()),
            "seam_mean_abs_error": float(difference[seam].mean()) if bool(seam.any()) else 0.0,
            "off_seam_mean_abs_error": float(difference[~seam].mean()) if bool((~seam).any()) else 0.0,
            "gpu_peak_gib": float(torch.cuda.max_memory_allocated(device) / 2**30) if device.type == "cuda" else 0.0,
        })
        del full, tiled, difference, tensor
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"[tile-parity] {sequence}", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "large_frame_tile_parity.csv", index=False)
    summary = {
        "status": "complete", "checkpoint_epoch": 48, "frames": len(rows),
        "max_mean_abs_error": float(table["mean_abs_error"].max()),
        "max_p99_abs_error": float(table["p99_abs_error"].max()),
        "max_absolute_error": float(table["max_abs_error"].max()),
        "max_seam_mean_abs_error": float(table["seam_mean_abs_error"].max()),
        "max_gpu_peak_gib": float(table["gpu_peak_gib"].max()),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
