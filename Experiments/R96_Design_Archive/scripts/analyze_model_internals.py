"""Read-only R95 internal intervention and counterfactual analysis on CPU."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
WEIGHT_ROOT = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights"
REPORT_ROOT = ROOT / "reports" / "model_internal_analysis"
REAL_ROOT = ROOT / "data" / "live_validation"
SOURCE_ROOT = Path(r"D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch\data\r93_formal")
BRANCHES = ("radiometry", "nuisance", "local_contrast", "boundary", "texture")
CONTROL_KEYS = (
    "need_radiometry", "need_noise", "need_local_contrast", "need_boundary", "need_texture",
    "local_contrast_evidence", "boundary_evidence", "texture_recoverability",
    "geometry_probability", "boundary_support",
    "local_contrast_intervention", "boundary_intervention", "texture_intervention",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r95_internal_model", ROOT / "model" / "r95_model.py")
DATA = load_module("r95_internal_dataset", ROOT / "training" / "r95_dataset.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(path)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.float32) / float(np.iinfo(image.dtype).max)


def core_crop(tensor: torch.Tensor, margin: int = 96) -> torch.Tensor:
    if tensor.shape[-2] <= 2 * margin or tensor.shape[-1] <= 2 * margin:
        return tensor
    return tensor[..., margin:-margin, margin:-margin]


def tensor_stats(tensor: torch.Tensor, *, scale: float = 1.0) -> dict[str, float]:
    array = core_crop(tensor.detach().float()).cpu().numpy().reshape(-1) * float(scale)
    absolute = np.abs(array)
    return {
        "signed_mean": float(array.mean()),
        "abs_mean": float(absolute.mean()),
        "abs_p95": float(np.percentile(absolute, 95)),
        "abs_p99": float(np.percentile(absolute, 99)),
        "minimum": float(array.min()),
        "maximum": float(array.max()),
    }


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    left = core_crop(a).detach().float().flatten()
    right = core_crop(b).detach().float().flatten()
    denominator = float(left.norm() * right.norm())
    return float(torch.dot(left, right) / denominator) if denominator > 1e-12 else 0.0


def active_fraction(raw: torch.Tensor, delta: torch.Tensor) -> float:
    raw = core_crop(raw).detach().float()
    delta = core_crop(delta).detach().float()
    unclamped = raw + delta
    return float(((unclamped < 0.0) | (unclamped > 1.0)).float().mean())


def spatial_effects(source: torch.Tensor, maps: dict[str, torch.Tensor]) -> dict[str, Any]:
    """Signed effects inside, around, and outside the measured dark structure."""
    raw = core_crop(source).detach().float().cpu().numpy()[0, 0]
    raw_u8 = np.rint(np.clip(raw, 0.0, 1.0) * 255.0).astype(np.uint8)
    _, mask_u8 = cv2.threshold(raw_u8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = mask_u8 > 0
    edge = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    near = cv2.dilate(edge.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    regions = {
        "foreground_interior": mask & ~near,
        "boundary_band": near,
        "background_interior": ~mask & ~near,
    }
    result: dict[str, Any] = {}
    for name, tensor in maps.items():
        array = core_crop(tensor).detach().float().cpu().numpy()[0, 0] * 255.0
        result[name] = {
            region: {
                "signed_mean_gray": float(array[selected].mean()) if selected.any() else 0.0,
                "abs_mean_gray": float(np.abs(array[selected]).mean()) if selected.any() else 0.0,
            }
            for region, selected in regions.items()
        }
    return result


def collect_details(model: torch.nn.Module, image: torch.Tensor) -> dict[str, torch.Tensor]:
    with torch.inference_mode():
        return model(image, return_details=True)


def branch_map(details: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {
        "radiometry": details["radiometry_delta"],
        "nuisance": details["nuisance_delta"],
        "local_contrast": details["local_contrast_delta"],
        "boundary": details["boundary_delta"],
        "texture": details["texture_delta"],
    }


def sample_analysis(details: dict[str, torch.Tensor], source: torch.Tensor, target: torch.Tensor | None) -> dict[str, Any]:
    raw = source.clamp(0.0, 1.0)
    branches = branch_map(details)
    sum_abs = sum(core_crop(value).abs() for value in branches.values())
    combined = sum(branches.values())
    final_delta = details["output"] - raw
    result: dict[str, Any] = {
        "output_change_gray": tensor_stats(final_delta, scale=255.0),
        "sum_branch_abs_mean_gray": float(sum(value["abs_mean"] for value in (
            tensor_stats(branches[name], scale=255.0) for name in BRANCHES
        ))),
        "effective_abs_mean_gray": tensor_stats(final_delta, scale=255.0)["abs_mean"],
        "cancellation_fraction": float(1.0 - core_crop(combined).abs().sum() / sum_abs.sum().clamp_min(1e-12)),
        "output_clamp_fraction": active_fraction(raw, combined),
        "branches": {},
        "controls": {},
        "branch_cosines": {},
        "spatial_effects": spatial_effects(raw, {**branches, "combined": final_delta}),
    }
    for name, delta in branches.items():
        raw_key = "restoration_raw" if name in {"boundary", "texture"} else f"{name}_raw"
        if name == "boundary":
            raw_key = "boundary_restoration_raw"
        elif name == "texture":
            raw_key = "texture_restoration_raw"
        gated = tensor_stats(delta, scale=255.0)
        ungated = tensor_stats(details[raw_key], scale=255.0)
        gate_ratio = gated["abs_mean"] / max(ungated["abs_mean"], 1e-12)
        result["branches"][name] = {
            "gated_gray": gated,
            "ungated_gray": ungated,
            "effective_gate_ratio": float(gate_ratio),
            "cosine_to_final_change": cosine(delta, final_delta),
        }
    for key in CONTROL_KEYS:
        result["controls"][key] = tensor_stats(details[key])
    for left_index, left in enumerate(BRANCHES):
        for right in BRANCHES[left_index + 1:]:
            result["branch_cosines"][f"{left}__{right}"] = cosine(branches[left], branches[right])
    if target is not None:
        target_delta = target - raw
        raw_mae = float(core_crop(target_delta).abs().mean() * 255.0)
        output_mae = float(core_crop(details["output"] - target).abs().mean() * 255.0)
        result["truth"] = {
            "raw_target_mae_gray": raw_mae,
            "output_target_mae_gray": output_mae,
            "recovered_fraction": float((raw_mae - output_mae) / max(raw_mae, 1e-12)),
            "correction_cosine_to_truth": cosine(final_delta, target_delta),
            "branch_cosine_to_truth": {name: cosine(delta, target_delta) for name, delta in branches.items()},
        }
        ablations: dict[str, Any] = {}
        for name, delta in branches.items():
            candidate = torch.clamp(details["output"] - delta, 0.0, 1.0)
            mae = float(core_crop(candidate - target).abs().mean() * 255.0)
            ablations[name] = {
                "mae_without_branch_gray": mae,
                "branch_value_positive_is_helpful_gray": float(mae - output_mae),
            }
        result["ablations"] = ablations
    return result


def load_checkpoint(epoch: int) -> tuple[torch.nn.Module, dict[str, Any]]:
    path = WEIGHT_ROOT / f"epoch_{epoch:03d}.pth.tar"
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=16).eval()
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    model.set_active_training_groups(None)
    return model, {"path": str(path), "sha256": sha256_file(path), "metrics": payload.get("metrics", {})}


def parameter_group_stats(model: torch.nn.Module) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, parameters in model.parameter_groups().items():
        values = torch.cat([parameter.detach().float().reshape(-1) for parameter in parameters])
        result[name] = {
            "parameter_count": int(values.numel()),
            "rms": float(values.square().mean().sqrt()),
            "abs_mean": float(values.abs().mean()),
            "abs_max": float(values.abs().max()),
            "near_zero_fraction": float((values.abs() <= 1e-6).float().mean()),
        }
    return result


def head_stats(model: torch.nn.Module) -> dict[str, Any]:
    names = (
        "need_head", "evidence_head", "geometry_head", "radiometry_head",
        "nuisance_head", "local_contrast_head", "boundary_head", "texture_head",
    )
    result: dict[str, Any] = {}
    for name in names:
        module = getattr(model, name)
        weight = module.weight.detach().float()
        bias = module.bias.detach().float() if module.bias is not None else None
        result[name] = {
            "weight_rms": float(weight.square().mean().sqrt()),
            "weight_abs_max": float(weight.abs().max()),
            "bias": [] if bias is None else [float(value) for value in bias],
        }
    return result


def real_samples() -> list[tuple[str, torch.Tensor, None]]:
    rows = []
    for path in sorted(REAL_ROOT.glob("*.bmp")):
        image = torch.from_numpy(read_gray(path))[None, None]
        rows.append((path.stem, image, None))
    return rows


def synthetic_samples(manifest: dict[str, Any]) -> list[tuple[str, torch.Tensor, torch.Tensor]]:
    dataset = DATA.R95SceneDataset(
        SOURCE_ROOT, manifest, "validation", 768, 384, 0,
        all_observations=True, master_seed=950041,
    )
    selected: dict[str, tuple[str, torch.Tensor, torch.Tensor]] = {}
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role in selected:
            continue
        item = dataset[index]
        selected[role] = (role, item["source"][0:1], item["supervised_target"][0:1])
    return [selected[name] for name in sorted(selected)]


def summarize(report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for epoch_text, block in report["epochs"].items():
        epoch = int(epoch_text)
        for domain in ("real", "synthetic"):
            for name, result in block[domain].items():
                row = {
                    "epoch": epoch, "domain": domain, "sample": name,
                    "output_abs_gray": result["output_change_gray"]["abs_mean"],
                    "cancellation_fraction": result["cancellation_fraction"],
                    "output_clamp_fraction": result["output_clamp_fraction"],
                }
                for branch in BRANCHES:
                    row[f"{branch}_abs_gray"] = result["branches"][branch]["gated_gray"]["abs_mean"]
                    row[f"{branch}_gate_ratio"] = result["branches"][branch]["effective_gate_ratio"]
                    if "truth" in result:
                        row[f"{branch}_value_gray"] = result["ablations"][branch]["branch_value_positive_is_helpful_gray"]
                for control in CONTROL_KEYS:
                    row[f"{control}_mean"] = result["controls"][control]["signed_mean"]
                if "truth" in result:
                    row["recovered_fraction"] = result["truth"]["recovered_fraction"]
                    row["correction_truth_cosine"] = result["truth"]["correction_cosine_to_truth"]
                rows.append(row)
    return {"rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", nargs="+", type=int, default=[16, 24, 28, 32])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--report-root", type=Path, default=REPORT_ROOT)
    parser.add_argument("--progress-file", type=Path, default=None)
    args = parser.parse_args()
    torch.set_num_threads(max(1, int(args.threads)))
    torch.set_num_interop_threads(1)
    manifest_path = SOURCE_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    real = real_samples()
    synthetic = synthetic_samples(manifest)
    report: dict[str, Any] = {
        "analysis_id": "R95_MODEL_INTERNAL_CAUSAL_AUDIT_V1",
        "read_only": True,
        "device": "cpu",
        "epochs": {},
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_content_sha256": manifest["content_sha256"],
        "real_images": [name for name, _, _ in real],
        "synthetic_roles": [name for name, _, _ in synthetic],
    }
    progress_path = args.progress_file or (args.report_root / "analysis_progress.json")
    args.report_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for epoch in args.epochs:
        completed_samples = 0
        total_samples = len(real) + len(synthetic)

        def write_progress(sample: str) -> None:
            progress_path.write_text(json.dumps({
                "status": "running", "device": "cpu", "epoch": epoch,
                "sample": sample, "completed_samples_in_epoch": completed_samples,
                "total_samples_in_epoch": total_samples,
                "completed_epochs": [int(value) for value in report["epochs"]],
                "elapsed_seconds": time.perf_counter() - started,
            }, indent=2), encoding="utf-8")

        progress_path.write_text(json.dumps({
            "status": "running", "device": "cpu", "epoch": epoch,
            "completed_epochs": [int(value) for value in report["epochs"]],
            "elapsed_seconds": time.perf_counter() - started,
        }, indent=2), encoding="utf-8")
        model, checkpoint = load_checkpoint(epoch)
        epoch_result = {
            "checkpoint": checkpoint,
            "parameter_groups": parameter_group_stats(model),
            "heads": head_stats(model),
            "real": {}, "synthetic": {},
        }
        for name, source, target in real:
            write_progress(f"real:{name}")
            epoch_result["real"][name] = sample_analysis(collect_details(model, source), source, target)
            completed_samples += 1
        for name, source, target in synthetic:
            write_progress(f"synthetic:{name}")
            epoch_result["synthetic"][name] = sample_analysis(collect_details(model, source), source, target)
            completed_samples += 1
        report["epochs"][str(epoch)] = epoch_result
        del model
    summary = summarize(report)
    report["summary"] = summary
    json_path = args.report_root / "internal_causal_audit.json"
    temporary = json_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, json_path)
    rows = summary["rows"]
    csv_path = args.report_root / "internal_causal_audit_rows.csv"
    fields = sorted({key for row in rows for key in row})
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "status": "complete", "epochs": args.epochs,
        "real_samples": len(real), "synthetic_samples": len(synthetic),
        "json": str(json_path), "csv": str(csv_path),
    }, indent=2))
    progress_path.write_text(json.dumps({
        "status": "complete", "device": "cpu", "epochs": args.epochs,
        "elapsed_seconds": time.perf_counter() - started,
        "json": str(json_path), "csv": str(csv_path),
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
