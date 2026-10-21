"""Track R100 operator activation and real-image detail over formal checkpoints."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
R100 = Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch")
MODEL_PATH = R100 / "model" / "r100_model.py"
DESIGN = json.loads((R100 / "config" / "experiment_design.json").read_text(encoding="utf-8"))
WEIGHTS = R100 / "weights" / "formal" / "seed_1000053" / "R100_scratch_seed1000053_20260814_180143" / "weights"
IMAGES = R100 / "data" / "live_validation"
OUTPUT = ROOT / "results" / "r100_operator_trajectory"
EPOCHS = [1, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r101_r100_model", MODEL_PATH)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image.astype(np.float32) / 255.0


def fine_ratio(raw: np.ndarray, output: np.ndarray, sigma: float = 1.0) -> float:
    raw_band = raw - cv2.GaussianBlur(raw, (0, 0), sigma)
    out_band = output - cv2.GaussianBlur(output, (0, 0), sigma)
    return float(np.mean(np.abs(out_band)) / max(np.mean(np.abs(raw_band)), 1e-9))


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    halo = int(DESIGN["architecture"]["tile_contract"]["minimum_halo_px"])
    image_rows = [(path.stem, read_gray(path)) for path in sorted(IMAGES.glob("*.bmp"))]
    rows: list[dict[str, object]] = []
    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        model = MODEL.build_model(base=int(DESIGN["architecture"]["model_width"]))
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
        model.eval().to(device)
        for name, raw in image_rows:
            source = torch.from_numpy(raw)[None, None].to(device)
            padded = F.pad(source, (halo, halo, halo, halo), mode="reflect")
            with torch.inference_mode():
                padded_details = model(padded, return_details=True)
            details = {key: value[..., halo:halo + raw.shape[0], halo:halo + raw.shape[1]] for key, value in padded_details.items()}
            output = details["output"][0, 0].cpu().numpy()
            rows.append({
                "epoch": epoch,
                "image": name,
                "mean_abs_change_gray": float(details["correction"].abs().mean() * 255.0),
                "low_change_gray": float(details["low_delta"].abs().mean() * 255.0),
                "denoise_change_gray": float(details["denoise_delta"].abs().mean() * 255.0),
                "edge_change_gray": float(details["edge_delta"].abs().mean() * 255.0),
                "texture_change_gray": float(details["texture_delta"].abs().mean() * 255.0),
                "edge_strength": float(details["edge_strength"].mean()),
                "texture_coefficient_sum": float(details["texture_coefficients"].sum(1).mean()),
                "fine_detail_ratio": fine_ratio(raw, output),
            })
        del model, checkpoint
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"epoch {epoch} complete", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "per_image.csv", index=False)
    numeric = [column for column in table.columns if column not in {"epoch", "image"}]
    aggregate = table.groupby("epoch", as_index=False)[numeric].median()
    aggregate.to_csv(OUTPUT / "median_trajectory.csv", index=False)
    figure, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for column, label in (("denoise_change_gray", "Denoise"), ("edge_change_gray", "Edge"), ("texture_change_gray", "Texture")):
        axes[0].plot(aggregate["epoch"], aggregate[column], marker="o", label=label)
    axes[0].set_ylabel("median absolute change (gray levels)")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    axes[1].plot(aggregate["epoch"], aggregate["fine_detail_ratio"], marker="o", color="#7C3AED")
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1)
    axes[1].set_ylabel("real fine-detail ratio to Raw")
    axes[1].set_xlabel("epoch")
    axes[1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(OUTPUT / "trajectory.png", dpi=180)
    plt.close(figure)
    summary = {
        "status": "complete",
        "epochs": EPOCHS,
        "images": [name for name, _ in image_rows],
        "median_trajectory": aggregate.to_dict(orient="records"),
        "interpretation": "Fine-detail ratio above one means more real-image high-frequency energy than Raw; below one means smoothing.",
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
