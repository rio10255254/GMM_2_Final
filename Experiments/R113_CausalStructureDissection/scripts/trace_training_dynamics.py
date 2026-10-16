"""Trace matched synthetic behavior through V42 and R109 training checkpoints."""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "training_dynamics"
OUTPUT.mkdir(parents=True, exist_ok=True)
R109_ROOT = Path(CONFIG["models"]["R109_E48"]["model_root"])
V42_CHECKPOINT = Path(CONFIG["models"]["V42_E120"]["checkpoint"])
V42_RUN = V42_CHECKPOINT.parent
V42_LOADER = Path(CONFIG["models"]["V42_E120"]["loader"])
R109_RUN = R109_ROOT / "runs" / "r109_formal_scratch_continuous_b8_20260826" / "weights"
V42_EPOCHS = (1, 5, 10, 20, 40, 60, 80, 100, 120)
R109_EPOCHS = tuple(range(4, 49, 4))
SCENES = 32
BATCH = 8


@dataclass
class Sample:
    source: np.ndarray
    target: np.ndarray
    mask: np.ndarray
    midpoint: float
    polarity: float
    scene_index: int
    role: str
    family: str
    challenge: str
    observation: str


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def gradients(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3) / 8.0, cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3) / 8.0


def binary_boundary(mask: np.ndarray) -> np.ndarray:
    value = mask.astype(np.uint8)
    eroded = cv2.erode(value, np.ones((3, 3), np.uint8), iterations=1)
    return (value != eroded).astype(np.uint8)


def boundary_distance(predicted: np.ndarray, truth: np.ndarray) -> float:
    pred_edge = binary_boundary(predicted)
    truth_edge = binary_boundary(truth)
    if not pred_edge.any() or not truth_edge.any():
        return math.nan
    pred_distance = cv2.distanceTransform(1 - pred_edge, cv2.DIST_L2, 5)
    truth_distance = cv2.distanceTransform(1 - truth_edge, cv2.DIST_L2, 5)
    return float(0.5 * (pred_distance[truth_edge > 0].mean() + truth_distance[pred_edge > 0].mean()))


def centroid(mask: np.ndarray) -> tuple[float, float]:
    yy, xx = np.nonzero(mask)
    return (float(xx.mean()), float(yy.mean())) if len(xx) else (math.nan, math.nan)


def sample_metrics(sample: Sample, output: np.ndarray) -> dict[str, float | int | str]:
    source = sample.source.astype(np.float32)
    target = sample.target.astype(np.float32)
    truth = sample.mask > 0.5
    score = sample.polarity * (output - sample.midpoint)
    predicted = score > 0
    intersection = np.logical_and(predicted, truth).sum()
    dice = (2.0 * intersection + 1.0) / (predicted.sum() + truth.sum() + 1.0)
    pred_center = centroid(predicted)
    truth_center = centroid(truth)
    center_error = math.hypot(pred_center[0] - truth_center[0], pred_center[1] - truth_center[1]) if all(math.isfinite(v) for v in (*pred_center, *truth_center)) else math.nan
    output_gx, output_gy = gradients(output)
    target_gx, target_gy = gradients(target)
    output_hf = output - cv2.GaussianBlur(output, (0, 0), 1.5)
    target_hf = target - cv2.GaussianBlur(target, (0, 0), 1.5)
    residual = output - source
    low_residual = cv2.GaussianBlur(residual, (0, 0), 8.0)
    return {
        "scene_index": sample.scene_index,
        "role": sample.role,
        "family": sample.family,
        "challenge": sample.challenge,
        "observation": sample.observation,
        "mae_to_target_gray": float(np.mean(np.abs(output - target)) * 255.0),
        "mae_change_from_source_gray": float(np.mean(np.abs(residual)) * 255.0),
        "low_frequency_change_gray": float(np.mean(np.abs(low_residual)) * 255.0),
        "gradient_mae_gray": float(np.mean(np.abs(output_gx - target_gx) + np.abs(output_gy - target_gy)) * 255.0),
        "high_frequency_energy_ratio": float(np.sqrt(np.mean(output_hf**2)) / max(float(np.sqrt(np.mean(target_hf**2))), 1e-8)),
        "dice": float(dice),
        "boundary_distance_px": boundary_distance(predicted, truth),
        "centroid_error_px": float(center_error),
        "area_error_fraction": float(abs(predicted.mean() - truth.mean())),
    }


def load_samples() -> list[Sample]:
    sys.path.insert(0, str(R109_ROOT / "training"))
    from r109_dataset import R109Dataset

    dataset = R109Dataset("validation", epoch=0, limit=SCENES)
    samples: list[Sample] = []
    for index in range(len(dataset)):
        item = dataset[index]
        for observation_index, observation in enumerate(("degraded", "clear")):
            samples.append(
                Sample(
                    source=item["source"][observation_index, 0].numpy().copy(),
                    target=item["target"][observation_index, 0].numpy().copy(),
                    mask=item["mask"][observation_index, 0].numpy().copy(),
                    midpoint=float(item["midpoint"][observation_index]),
                    polarity=float(item["polarity"][observation_index]),
                    scene_index=int(item["scene_index"]),
                    role=str(item["role"]),
                    family=str(item["family"]),
                    challenge=str(item["challenge"]),
                    observation=observation,
                )
            )
    return samples


@torch.inference_mode()
def infer_samples(model: torch.nn.Module, samples: list[Sample], device: torch.device) -> list[np.ndarray]:
    outputs: list[np.ndarray] = []
    for start in range(0, len(samples), BATCH):
        batch = np.stack([sample.source for sample in samples[start : start + BATCH]]).astype(np.float32)
        tensor = torch.from_numpy(batch[:, None]).to(device)
        value = model(tensor).float().clamp(0, 1).cpu().numpy()[:, 0]
        outputs.extend(value)
    return outputs


def save_preview(model_name: str, epoch: int, samples: list[Sample], outputs: list[np.ndarray]) -> None:
    if (model_name == "V42" and epoch not in {1, 60, 120}) or (model_name == "R109" and epoch not in {4, 24, 48}):
        return
    indices = [index for index, sample in enumerate(samples) if sample.observation == "degraded"][:4]
    figure, axes = plt.subplots(len(indices), 3, figsize=(9, 3 * len(indices)))
    for row, index in enumerate(indices):
        for column, (image, title) in enumerate(((samples[index].source, "Source"), (outputs[index], f"{model_name} E{epoch}"), (samples[index].target, "Truth"))):
            axes[row, column].imshow(image, cmap="gray", vmin=0, vmax=1)
            axes[row, column].set_title(title)
            axes[row, column].axis("off")
    figure.tight_layout()
    preview = OUTPUT / "previews" / f"{model_name.lower()}_e{epoch:03d}.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(preview, dpi=150)
    plt.close(figure)


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    numeric = [
        "mae_to_target_gray",
        "mae_change_from_source_gray",
        "low_frequency_change_gray",
        "gradient_mae_gray",
        "high_frequency_energy_ratio",
        "dice",
        "boundary_distance_px",
        "centroid_error_px",
        "area_error_fraction",
    ]
    result = rows.groupby(["model", "epoch", "observation"], as_index=False)[numeric].median()
    worst = rows.groupby(["model", "epoch", "observation"], as_index=False)["boundary_distance_px"].quantile(0.95).rename(columns={"boundary_distance_px": "boundary_distance_p95_px"})
    return result.merge(worst, on=["model", "epoch", "observation"], validate="one_to_one")


def summarize_challenges(rows: pd.DataFrame) -> pd.DataFrame:
    degraded = rows.loc[rows["observation"].eq("degraded")].copy()
    metrics = ["mae_to_target_gray", "dice", "boundary_distance_px", "centroid_error_px", "low_frequency_change_gray"]
    return degraded.groupby(["model", "epoch", "challenge"], as_index=False)[metrics].median()


def plot_summary(summary: pd.DataFrame) -> None:
    metrics = ("boundary_distance_px", "mae_to_target_gray", "low_frequency_change_gray", "high_frequency_energy_ratio")
    figure, axes = plt.subplots(2, 2, figsize=(12, 8))
    for axis, metric in zip(axes.ravel(), metrics):
        for model_name, group in summary[summary["observation"].eq("degraded")].groupby("model"):
            axis.plot(group["epoch"], group[metric], marker="o", label=model_name)
        axis.set_title(metric.replace("_", " "))
        axis.set_xlabel("epoch")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    figure.savefig(OUTPUT / "training_dynamics.png", dpi=180)
    plt.close(figure)


def main() -> int:
    torch.manual_seed(113001)
    np.random.seed(113001)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    samples = load_samples()
    rows: list[dict[str, object]] = []

    sys.path.insert(0, str(R109_ROOT / "model"))
    from r109_model import build_model

    r109_model = build_model().to(device).eval()
    for epoch in R109_EPOCHS:
        checkpoint = torch.load(R109_RUN / f"epoch_{epoch:03d}.pth", map_location="cpu", weights_only=False)
        r109_model.load_state_dict(checkpoint["model"])
        outputs = infer_samples(r109_model, samples, device)
        save_preview("R109", epoch, samples, outputs)
        for sample, output in zip(samples, outputs):
            rows.append({"model": "R109", "epoch": epoch, **sample_metrics(sample, output)})
        print(json.dumps({"model": "R109", "epoch": epoch, "samples": len(samples)}), flush=True)

    loader = load_module(V42_LOADER, "r113_v42_loader")
    module, v42_model, v42_device, temporary_psf, _, _ = loader.load_model()
    try:
        for epoch in V42_EPOCHS:
            checkpoint_path = V42_RUN / f"epoch_{epoch:03d}.pth.tar"
            checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            state = module.extract_state_dict(checkpoint)
            module.load_weights(v42_model, state, strict=False)
            v42_model.eval()
            outputs = infer_samples(v42_model, samples, v42_device)
            save_preview("V42", epoch, samples, outputs)
            for sample, output in zip(samples, outputs):
                rows.append({"model": "V42", "epoch": epoch, **sample_metrics(sample, output)})
            print(json.dumps({"model": "V42", "epoch": epoch, "samples": len(samples)}), flush=True)
    finally:
        if temporary_psf is not None:
            shutil.rmtree(temporary_psf, ignore_errors=True)

    table = pd.DataFrame(rows)
    if len(table) != len(samples) * (len(R109_EPOCHS) + len(V42_EPOCHS)):
        raise RuntimeError("Unexpected trajectory row count")
    table.to_csv(OUTPUT / "per_sample.csv", index=False, encoding="utf-8-sig")
    summary = summarize(table)
    summary.to_csv(OUTPUT / "summary.csv", index=False, encoding="utf-8-sig")
    challenge_summary = summarize_challenges(table)
    challenge_summary.to_csv(OUTPUT / "challenge_summary.csv", index=False, encoding="utf-8-sig")
    plot_summary(summary)
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "device": str(device),
        "scenes": SCENES,
        "observations_per_scene": 2,
        "r109_epochs": list(R109_EPOCHS),
        "v42_epochs": list(V42_EPOCHS),
        "rows": len(table),
        "summary": summary.to_dict(orient="records"),
        "challenge_summary_rows": len(challenge_summary),
        "interpretation_boundary": "Within-model training trajectories on a fixed R109 synthetic validation subset; not an architecture-controlled comparison.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "rows": len(table), "output": str(OUTPUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
