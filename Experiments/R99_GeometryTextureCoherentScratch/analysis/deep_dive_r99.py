from __future__ import annotations

import csv
import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "r99_model.py"
TRAIN_PATH = ROOT / "training" / "train_r99.py"
RUN_ID = "R99_scratch_seed990053_20260814_105831"
WEIGHT_DIR = ROOT / "weights" / "formal" / "seed_990053" / RUN_ID / "weights"
LOG_PATH = ROOT / "runs" / f"training_{RUN_ID}" / "training_log.csv"
REAL_DIR = ROOT / "data" / "live_validation"
REPORT_DIR = ROOT / "reports" / "deep_dive"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EPOCHS = [1, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40]
SELECTED_VISUAL_EPOCHS = [24, 28, 32, 36, 40]
TEXTURE_BANDS = ["fine_3", "fine_5", "medium_3_7", "medium_5_15", "coarse_7_17", "coarse_15_17"]
OPTICAL_BANK = ["raw", "g3", "g5", "g7", "anisotropic_x", "anisotropic_y", "sobel_x", "sobel_y", "laplacian"]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    return image.astype(np.float32) / float(np.iinfo(image.dtype).max)


def tensor_percentile(value: torch.Tensor, q: float) -> float:
    return float(torch.quantile(value.detach().float().reshape(-1), q).cpu())


def gradient_magnitude(value: torch.Tensor) -> torch.Tensor:
    kernel = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        device=value.device,
        dtype=value.dtype,
    ).view(1, 1, 3, 3) / 8.0
    padded = F.pad(value, (1, 1, 1, 1), mode="reflect")
    gx = F.conv2d(padded, kernel)
    gy = F.conv2d(padded, kernel.transpose(-1, -2))
    return torch.sqrt(gx.square() + gy.square() + 1e-12)


def laplacian_abs(value: torch.Tensor) -> torch.Tensor:
    kernel = torch.tensor(
        [[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]],
        device=value.device,
        dtype=value.dtype,
    ).view(1, 1, 3, 3)
    return F.conv2d(F.pad(value, (1, 1, 1, 1), mode="reflect"), kernel).abs()


def stage_metrics(raw: torch.Tensor, value: torch.Tensor) -> dict[str, float]:
    correction = value - raw
    absolute = correction.abs()
    raw_gradient = gradient_magnitude(raw)
    value_gradient = gradient_magnitude(value)
    threshold = torch.quantile(raw_gradient.reshape(-1), 0.90)
    edge_mask = raw_gradient >= threshold
    local_max = F.max_pool2d(raw, 9, stride=1, padding=4)
    local_min = -F.max_pool2d(-raw, 9, stride=1, padding=4)
    overshoot = F.relu(value - local_max - 1.0 / 255.0) + F.relu(local_min - value - 1.0 / 255.0)
    correction_sum = absolute.sum().clamp_min(1e-9)
    return {
        "mean_abs_gray": float(absolute.mean().cpu() * 255.0),
        "p95_abs_gray": tensor_percentile(absolute, 0.95) * 255.0,
        "signed_mean_gray": float(correction.mean().cpu() * 255.0),
        "edge_ratio": float((value_gradient.mean() / raw_gradient.mean().clamp_min(1e-9)).cpu()),
        "laplacian_ratio": float((laplacian_abs(value).mean() / laplacian_abs(raw).mean().clamp_min(1e-9)).cpu()),
        "contrast_ratio": float((value.std() / raw.std().clamp_min(1e-9)).cpu()),
        "edge_correction_fraction": float((absolute[edge_mask].sum() / correction_sum).cpu()),
        "overshoot_fraction": float((overshoot > 0).float().mean().cpu()),
        "overshoot_mean_gray": float(overshoot.mean().cpu() * 255.0),
        "clip_fraction": float(((value <= 1e-6) | (value >= 1.0 - 1e-6)).float().mean().cpu()),
    }


def component_metrics(value: torch.Tensor) -> dict[str, float]:
    absolute = value.abs()
    return {
        "mean_abs_gray": float(absolute.mean().cpu() * 255.0),
        "p95_abs_gray": tensor_percentile(absolute, 0.95) * 255.0,
        "max_abs_gray": float(absolute.max().cpu() * 255.0),
        "signed_mean_gray": float(value.mean().cpu() * 255.0),
    }


def optical_weights(model: torch.nn.Module, image: torch.Tensor, crop: tuple[slice, slice]) -> dict[str, Any]:
    raw = image
    g5 = model.optical.g5(raw)
    gx = model.optical._filter(raw, model.optical.sobel_x, (1, 1, 1, 1))
    gy = model.optical._filter(raw, model.optical.sobel_y, (1, 1, 1, 1))
    cues = torch.cat([raw, g5, gx.abs(), gy.abs()], dim=1)
    weights = torch.softmax(model.optical.weight_logits(cues), dim=1)[..., crop[0], crop[1]]
    mean = weights.mean(dim=(0, 2, 3))
    entropy = -(weights.clamp_min(1e-9) * weights.clamp_min(1e-9).log()).sum(dim=1) / math.log(weights.shape[1])
    return {
        "mean": {name: float(mean[index].cpu()) for index, name in enumerate(OPTICAL_BANK)},
        "normalized_entropy": float(entropy.mean().cpu()),
        "maximum_weight_mean": float(weights.max(dim=1).values.mean().cpu()),
    }


def state_group(name: str) -> str:
    if name.startswith("optical"):
        return "optical"
    if name.startswith("low_head"):
        return "low"
    if name.startswith("geometry_head"):
        return "geometry"
    if name.startswith("transport_head"):
        return "transport"
    if name.startswith("edge_head"):
        return "edge"
    if name.startswith("texture_head"):
        return "texture"
    return "backbone"


def weight_statistics(state: dict[str, torch.Tensor], reference: dict[str, torch.Tensor]) -> dict[str, Any]:
    grouped_norm: defaultdict[str, float] = defaultdict(float)
    grouped_diff: defaultdict[str, float] = defaultdict(float)
    grouped_reference: defaultdict[str, float] = defaultdict(float)
    for name, value in state.items():
        if not torch.is_floating_point(value):
            continue
        group = state_group(name)
        current = value.detach().float().cpu()
        baseline = reference[name].detach().float().cpu()
        grouped_norm[group] += float(current.square().sum())
        grouped_diff[group] += float((current - baseline).square().sum())
        grouped_reference[group] += float(baseline.square().sum())
    return {
        group: {
            "l2_norm": math.sqrt(grouped_norm[group]),
            "relative_drift_from_epoch1": math.sqrt(grouped_diff[group]) / max(math.sqrt(grouped_reference[group]), 1e-12),
        }
        for group in sorted(grouped_norm)
    }


def final_head_statistics(model: torch.nn.Module) -> dict[str, Any]:
    heads = {
        "low": model.low_head[-1],
        "geometry": model.geometry_head[-1],
        "transport": model.transport_head[-1],
        "edge": model.edge_head[-1],
        "texture": model.texture_head[-1],
    }
    return {
        name: {
            "weight_l2": float(head.weight.detach().float().norm().cpu()),
            "weight_abs_mean": float(head.weight.detach().float().abs().mean().cpu()),
            "bias": [float(item) for item in head.bias.detach().float().cpu().tolist()],
        }
        for name, head in heads.items()
    }


def save_sheet(path: Path, labels: list[str], images: list[np.ndarray]) -> None:
    panels = []
    for label, image in zip(labels, images):
        panel = np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
        panel = panel.copy()
        cv2.putText(panel, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, 255, 2, cv2.LINE_AA)
        panels.append(panel)
    sheet = np.concatenate(panels, axis=1)
    if not cv2.imwrite(str(path), sheet):
        raise RuntimeError(f"Cannot save {path}")


def aggregate_rows(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    return {key: float(np.mean([row[key] for row in rows])) for key in rows[0]}


def analyze_synthetic_dataset() -> dict[str, Any]:
    trainer = load_module("r99_trainer_for_analysis", TRAIN_PATH)
    package = Path(trainer.DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R99SceneDataset(package, manifest, "validation", 256, 128, 0, all_observations=True)
    grouped: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    core = slice(64, 192)
    for index in range(len(dataset)):
        item = dataset[index]
        role = str(item["role"])
        for view in range(int(item["source"].shape[0])):
            source = item["source"][view : view + 1, :, core, core]
            target = item["target"][view : view + 1, :, core, core]
            sdf = item["sdf"][view : view + 1, :, core, core]
            source_gradient = gradient_magnitude(source).mean().item()
            target_gradient = gradient_magnitude(target).mean().item()
            source_lap = laplacian_abs(source).mean().item()
            target_lap = laplacian_abs(target).mean().item()
            residual = (target - source).abs()
            boundary = sdf.abs() < 6.0
            flat = sdf.abs() > 16.0
            row = {
                "source_target_mae_gray": float(residual.mean() * 255.0),
                "target_to_source_gradient_ratio": float(target_gradient / max(source_gradient, 1e-9)),
                "target_to_source_laplacian_ratio": float(target_lap / max(source_lap, 1e-9)),
                "target_to_source_contrast_ratio": float(target.std() / source.std().clamp_min(1e-9)),
                "boundary_residual_gray": float(residual[boundary].mean() * 255.0) if bool(boundary.any()) else 0.0,
                "flat_residual_gray": float(residual[flat].mean() * 255.0) if bool(flat.any()) else 0.0,
            }
            grouped[role].append(row)
            grouped["identity_views" if bool(item["identity"][view]) else "nonidentity_views"].append(row)
            grouped["all_views"].append(row)
    summary: dict[str, Any] = {}
    for name, rows in grouped.items():
        summary[name] = {"count": len(rows)}
        for key in rows[0]:
            values = np.asarray([row[key] for row in rows], dtype=np.float64)
            summary[name][key] = {
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
                "p10": float(np.percentile(values, 10)),
                "p90": float(np.percentile(values, 90)),
            }
    return summary


def read_training_log() -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    with LOG_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            epoch = int(row["epoch"])
            converted: dict[str, Any] = {"epoch": epoch}
            for key, value in row.items():
                if key == "epoch":
                    continue
                if value == "":
                    converted[key] = None
                else:
                    try:
                        converted[key] = float(value)
                    except ValueError:
                        converted[key] = value
            rows[epoch] = converted
    return rows


def correlation_summary(training: dict[int, dict[str, Any]], real: dict[str, Any]) -> dict[str, Any]:
    epochs = [epoch for epoch in EPOCHS if training[epoch].get("val_reference_score") is not None]
    synthetic_score = np.asarray([training[epoch]["val_reference_score"] for epoch in epochs], dtype=np.float64)
    real_mae = np.asarray([
        np.mean([real[str(epoch)][name]["stages"]["output"]["mean_abs_gray"] for name in real[str(epoch)]])
        for epoch in epochs
    ])
    real_laplacian = np.asarray([
        np.mean([real[str(epoch)][name]["stages"]["output"]["laplacian_ratio"] for name in real[str(epoch)]])
        for epoch in epochs
    ])
    identity = np.asarray([training[epoch]["val_identity_axis"] for epoch in epochs], dtype=np.float64)
    return {
        "epochs": epochs,
        "pearson_synthetic_score_vs_real_change": float(np.corrcoef(synthetic_score, real_mae)[0, 1]),
        "pearson_synthetic_score_vs_real_laplacian_ratio": float(np.corrcoef(synthetic_score, real_laplacian)[0, 1]),
        "pearson_synthetic_identity_vs_real_change": float(np.corrcoef(identity, real_mae)[0, 1]),
        "synthetic_score": synthetic_score.tolist(),
        "real_mean_abs_change_gray": real_mae.tolist(),
        "real_mean_laplacian_ratio": real_laplacian.tolist(),
    }


def plot_trajectory(training: dict[int, dict[str, Any]], real: dict[str, Any], weight: dict[str, Any]) -> None:
    epochs = [epoch for epoch in EPOCHS if training[epoch].get("val_reference_score") is not None]
    mean_real = lambda key: [
        np.mean([real[str(epoch)][name]["stages"]["output"][key] for name in real[str(epoch)]])
        for epoch in epochs
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), dpi=160)
    axes[0, 0].plot(epochs, [training[e]["val_reference_score"] for e in epochs], "o-", label="synthetic balanced")
    axes[0, 0].plot(epochs, [training[e]["val_detail_axis"] for e in epochs], "o-", label="synthetic detail")
    axes[0, 0].plot(epochs, [training[e]["val_contour_axis"] for e in epochs], "o-", label="synthetic contour")
    axes[0, 0].set_title("Synthetic validation (lower is better)"); axes[0, 0].legend(); axes[0, 0].grid(alpha=.3)
    axes[0, 1].plot(epochs, mean_real("mean_abs_gray"), "o-", label="real mean change (gray)")
    axes[0, 1].plot(epochs, mean_real("p95_abs_gray"), "o-", label="real p95 change (gray)")
    axes[0, 1].set_title("Real-image intervention grows"); axes[0, 1].legend(); axes[0, 1].grid(alpha=.3)
    components = ["low_delta", "transport_delta", "edge_delta", "detail_delta"]
    for component in components:
        values = [
            np.mean([real[str(epoch)][name]["components"][component]["mean_abs_gray"] for name in real[str(epoch)]])
            for epoch in epochs
        ]
        axes[1, 0].plot(epochs, values, "o-", label=component.replace("_delta", ""))
    axes[1, 0].set_title("Functional branch magnitude on real inputs"); axes[1, 0].legend(); axes[1, 0].grid(alpha=.3)
    for group in ["low", "geometry", "transport", "edge", "texture"]:
        axes[1, 1].plot(epochs, [weight[str(e)]["groups"][group]["relative_drift_from_epoch1"] for e in epochs], "o-", label=group)
    axes[1, 1].set_title("EMA weight drift from epoch 1"); axes[1, 1].legend(); axes[1, 1].grid(alpha=.3)
    for ax in axes.flat:
        ax.set_xlabel("epoch")
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "r99_epoch_trajectory.png")
    plt.close(fig)


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model_module = load_module("r99_model_deep_dive", MODEL_PATH)
    real_images = {path.stem: read_gray(path) for path in sorted(REAL_DIR.glob("*.bmp"))}
    reference_checkpoint = torch.load(WEIGHT_DIR / "epoch_001.pth.tar", map_location="cpu", weights_only=False)
    reference_state = reference_checkpoint["ema_state_dict"]
    real_results: dict[str, Any] = {}
    weight_results: dict[str, Any] = {}
    selected_outputs: defaultdict[str, dict[int, np.ndarray]] = defaultdict(dict)
    selected_stages: defaultdict[str, dict[int, dict[str, np.ndarray]]] = defaultdict(dict)

    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHT_DIR / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        state = checkpoint["ema_state_dict"]
        model = model_module.build_model().to(device).eval()
        model.load_state_dict(state, strict=True)
        weight_results[str(epoch)] = {
            "groups": weight_statistics(state, reference_state),
            "heads": final_head_statistics(model),
        }
        epoch_results: dict[str, Any] = {}
        for image_name, array in real_images.items():
            raw = torch.from_numpy(array).unsqueeze(0).unsqueeze(0).to(device)
            halo = 192
            padded = F.pad(raw, (halo, halo, halo, halo), mode="reflect")
            with torch.inference_mode():
                details = model(padded, return_details=True)
            crop = (slice(halo, halo + raw.shape[-2]), slice(halo, halo + raw.shape[-1]))
            cropped = {name: value[..., crop[0], crop[1]].float() for name, value in details.items()}
            low_stage = (raw + cropped["low_delta"]).clamp(0.0, 1.0)
            geometry_stage = (low_stage + cropped["transport_delta"]).clamp(0.0, 1.0)
            edge_stage = (geometry_stage + cropped["edge_delta"]).clamp(0.0, 1.0)
            output = cropped["output"]
            stages = {
                "raw": stage_metrics(raw, raw),
                "radiometry": stage_metrics(raw, low_stage),
                "geometry": stage_metrics(raw, geometry_stage),
                "edge": stage_metrics(raw, edge_stage),
                "output": stage_metrics(raw, output),
            }
            components = {
                name: component_metrics(cropped[name])
                for name in ("low_delta", "transport_delta", "edge_delta", "detail_delta", "correction")
            }
            texture_contribution = cropped["texture_coefficients"] * cropped["texture_candidates"]
            texture = {
                "coefficient_abs_mean": {
                    name: float(cropped["texture_coefficients"][:, index].abs().mean().cpu())
                    for index, name in enumerate(TEXTURE_BANDS)
                },
                "contribution_abs_mean_gray": {
                    name: float(texture_contribution[:, index].abs().mean().cpu() * 255.0)
                    for index, name in enumerate(TEXTURE_BANDS)
                },
                "coefficient_l1_sum_mean": float(cropped["texture_coefficients"].abs().sum(dim=1).mean().cpu()),
            }
            geometry = {
                "support_mean": float(cropped["geometry_boundary_support"].mean().cpu()),
                "support_p95": tensor_percentile(cropped["geometry_boundary_support"], 0.95),
                "support_fraction_above_half": float((cropped["geometry_boundary_support"] > 0.5).float().mean().cpu()),
                "offset_abs_mean_px": float(cropped["transport_offset_px"].abs().mean().cpu()),
                "offset_abs_p95_px": tensor_percentile(cropped["transport_offset_px"], 0.95),
                "actual_motion_abs_mean_px": float(torch.sqrt(cropped["transport_dx_px"].square() + cropped["transport_dy_px"].square()).mean().cpu()),
            }
            epoch_results[image_name] = {
                "stages": stages,
                "components": components,
                "texture": texture,
                "geometry": geometry,
                "optical": optical_weights(model, padded, crop),
            }
            if epoch in SELECTED_VISUAL_EPOCHS:
                selected_outputs[image_name][epoch] = output[0, 0].detach().cpu().numpy()
            if epoch in (24, 40):
                selected_stages[image_name][epoch] = {
                    "raw": raw[0, 0].detach().cpu().numpy(),
                    "radiometry": low_stage[0, 0].detach().cpu().numpy(),
                    "geometry": geometry_stage[0, 0].detach().cpu().numpy(),
                    "edge": edge_stage[0, 0].detach().cpu().numpy(),
                    "texture": output[0, 0].detach().cpu().numpy(),
                }
        real_results[str(epoch)] = epoch_results
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    for image_name, array in real_images.items():
        save_sheet(
            REPORT_DIR / f"real_epoch_comparison_{image_name}.png",
            ["RAW"] + [f"E{epoch}" for epoch in SELECTED_VISUAL_EPOCHS],
            [array] + [selected_outputs[image_name][epoch] for epoch in SELECTED_VISUAL_EPOCHS],
        )
        for epoch in (24, 40):
            stages = selected_stages[image_name][epoch]
            save_sheet(
                REPORT_DIR / f"branch_decomposition_e{epoch:03d}_{image_name}.png",
                ["RAW", "+LOW", "+TRANSPORT", "+EDGE", "+TEXTURE"],
                [stages[name] for name in ("raw", "radiometry", "geometry", "edge", "texture")],
            )

    training = read_training_log()
    synthetic = analyze_synthetic_dataset()
    correlations = correlation_summary(training, real_results)
    plot_trajectory(training, real_results, weight_results)
    report = {
        "experiment": "R99_GeometryTextureCoherentScratch",
        "run_id": RUN_ID,
        "device": str(device),
        "epochs": EPOCHS,
        "real_functional_probes": real_results,
        "weight_probes": weight_results,
        "synthetic_dataset_profile": synthetic,
        "trajectory_correlations": correlations,
        "training_validation_rows": {str(epoch): training[epoch] for epoch in EPOCHS},
    }
    (REPORT_DIR / "r99_deep_dive.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report": str(REPORT_DIR / "r99_deep_dive.json"),
        "trajectory": str(REPORT_DIR / "r99_epoch_trajectory.png"),
        "correlations": correlations,
        "synthetic_counts": {name: value["count"] for name, value in synthetic.items()},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
