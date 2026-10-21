"""Formal-sampler, formal-core, read-only CPU audit of an R95 checkpoint."""
from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch\data\r93_formal")
WEIGHTS = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights"
BRANCHES = {
    "radiometry": ("radiometry_delta", "radiometry_raw"),
    "nuisance": ("nuisance_delta", "nuisance_raw"),
    "local_contrast": ("local_contrast_delta", "local_contrast_raw"),
    "boundary": ("boundary_delta", "boundary_restoration_raw"),
    "texture": ("texture_delta", "texture_restoration_raw"),
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load("r95_formal_audit_model", ROOT / "model" / "r95_model.py")
DATA = load("r95_formal_audit_data", ROOT / "training" / "r95_dataset.py")


def core(x: torch.Tensor) -> torch.Tensor:
    return x[..., 192:576, 192:576]


def mae(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(core(a - b).abs().mean() * 255.0)


def magnitude(x: torch.Tensor) -> float:
    return float(core(x).abs().mean() * 255.0)


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    left = core(a).float().reshape(-1)
    right = core(b).float().reshape(-1)
    denominator = left.norm() * right.norm()
    if float(denominator) <= 1e-12:
        return 0.0
    return float(torch.dot(left, right) / denominator)


def centered_cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    left = core(a).float().reshape(-1)
    right = core(b).float().reshape(-1)
    left = left - left.mean()
    right = right - right.mean()
    denominator = left.norm() * right.norm()
    if float(denominator) <= 1e-12:
        return 0.0
    return float(torch.dot(left, right) / denominator)


def least_squares_scale(prediction: torch.Tensor, target: torch.Tensor) -> float:
    left = core(prediction).float().reshape(-1)
    right = core(target).float().reshape(-1)
    denominator = torch.dot(left, left)
    if float(denominator) <= 1e-12:
        return 0.0
    return float(torch.dot(left, right) / denominator)


def output_from(raw: torch.Tensor, branches: dict[str, torch.Tensor]) -> torch.Tensor:
    return torch.clamp(raw + torch.clamp(sum(branches.values()), -0.34, 0.34), 0.0, 1.0)


def selected_indices(dataset, per_role: int) -> list[int]:
    groups = defaultdict(list)
    for index in range(len(dataset)):
        groups[dataset.role_at(index)].append(index)
    selected = {}
    for role, indices in sorted(groups.items()):
        count = min(max(1, per_role), len(indices))
        positions = np.linspace(0, len(indices) - 1, num=count, dtype=np.int64)
        selected[role] = [indices[int(position)] for position in positions]
    return [index for offset in range(max(map(len, selected.values()))) for role in sorted(selected) if offset < len(selected[role]) for index in [selected[role][offset]]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--per-role", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--state", choices=("ema", "model"), default="ema")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    dataset = DATA.R95SceneDataset(SOURCE, manifest, "validation", 768, 384, 0, all_observations=True, master_seed=950041)
    indices = selected_indices(dataset, args.per_role)
    checkpoint = torch.load(WEIGHTS / f"epoch_{args.epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=16).to(device).eval()
    model.load_state_dict(checkpoint[f"{args.state}_state_dict"], strict=True)
    rows = []
    for position, index in enumerate(indices, 1):
        item = dataset[index]
        sources = item["source"].to(device)
        targets = item["supervised_target"].to(device)
        with torch.inference_mode():
            all_details = model(sources, return_details=True)
        for view in range(item["source"].shape[0]):
            raw = sources[view:view + 1]
            target = targets[view:view + 1]
            details = {
                name: value[view:view + 1]
                for name, value in all_details.items()
            }
            branches = {name: details[keys[0]] for name, keys in BRANCHES.items()}
            row = {
                "role": item["role"], "scene_id": item["scene_id"], "dataset_index": index, "view": view,
                "identity": bool(item["identity"][view]),
                "raw_mae_gray": mae(raw, target), "model_mae_gray": mae(details["output"], target),
                "output_change_gray": mae(details["output"], raw),
                "controls": {
                    name: float(core(details[name]).mean())
                    for name in (
                        "need_radiometry", "need_noise", "need_local_contrast",
                        "local_contrast_evidence", "need_boundary", "boundary_evidence",
                        "need_texture", "texture_recoverability",
                    )
                },
                "truth_controls": {
                    **{
                        name: float(core(item["need_truth_s"][view:view + 1, channel:channel + 1].to(device)).mean())
                        for channel, name in enumerate((
                            "need_radiometry", "need_noise", "need_local_contrast",
                            "need_boundary", "need_texture",
                        ))
                    },
                    **{
                        name: float(core(item["evidence_truth_s"][view:view + 1, channel:channel + 1].to(device)).mean())
                        for channel, name in enumerate((
                            "local_contrast_evidence", "boundary_evidence", "texture_recoverability",
                        ))
                    },
                },
                "control_diagnostics": {},
                "branches": {},
            }
            control_truth = {
                **{
                    name: item["need_truth_s"][view:view + 1, channel:channel + 1].to(device)
                    for channel, name in enumerate((
                        "need_radiometry", "need_noise", "need_local_contrast",
                        "need_boundary", "need_texture",
                    ))
                },
                **{
                    name: item["evidence_truth_s"][view:view + 1, channel:channel + 1].to(device)
                    for channel, name in enumerate((
                        "local_contrast_evidence", "boundary_evidence", "texture_recoverability",
                    ))
                },
            }
            for name, target_control in control_truth.items():
                predicted_control = details[name]
                predicted_core = core(predicted_control).float()
                target_core = core(target_control).float()
                high_mask = target_core >= 0.50
                low_mask = target_core <= 0.05
                high_mean = (
                    float(predicted_core[high_mask].mean())
                    if bool(high_mask.any()) else None
                )
                low_mean = (
                    float(predicted_core[low_mask].mean())
                    if bool(low_mask.any()) else None
                )
                row["control_diagnostics"][name] = {
                    "prediction_std": float(predicted_core.std()),
                    "truth_std": float(target_core.std()),
                    "mae": float((predicted_core - target_core).abs().mean()),
                    "spatial_correlation": centered_cosine(predicted_control, target_control),
                    "prediction_on_truth_high": high_mean,
                    "prediction_on_truth_low": low_mean,
                    "within_channel_separation": (
                        high_mean - low_mean
                        if high_mean is not None and low_mean is not None else None
                    ),
                }
            for name, (gated_key, raw_key) in BRANCHES.items():
                current = branches[name]
                ungated = details[raw_key]
                target_branch = item[f"{name}_target"][view:view + 1].to(device)
                optimal_scale = least_squares_scale(ungated, target_branch)
                candidate_removed = dict(branches); candidate_removed[name] = torch.zeros_like(current)
                candidate_double = dict(branches); candidate_double[name] = current * 2.0
                candidate_open = dict(branches); candidate_open[name] = ungated
                row["branches"][name] = {
                    "gated_abs_gray": magnitude(current), "ungated_abs_gray": magnitude(ungated),
                    "target_abs_gray": magnitude(target_branch),
                    "gated_target_mae_gray": mae(current, target_branch),
                    "ungated_target_mae_gray": mae(ungated, target_branch),
                    "ungated_target_cosine": cosine(ungated, target_branch),
                    "least_squares_scale": optimal_scale,
                    "least_squares_target_mae_gray": mae(ungated * optimal_scale, target_branch),
                    "effective_gate_ratio": magnitude(current) / max(magnitude(ungated), 1e-12),
                    "remove_delta_mae_gray": mae(output_from(raw, candidate_removed), target) - row["model_mae_gray"],
                    "double_delta_mae_gray": mae(output_from(raw, candidate_double), target) - row["model_mae_gray"],
                    "open_delta_mae_gray": mae(output_from(raw, candidate_open), target) - row["model_mae_gray"],
                }
            rows.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix(".progress.json").write_text(json.dumps({
            "status": "running", "epoch": args.epoch, "selected_item": position,
            "selected_total": len(indices), "rows": len(rows),
        }, indent=2), encoding="utf-8")
    payload = {
        "analysis_id": "R95_FORMAL_INTERNAL_AUDIT_V1", "epoch": args.epoch,
        "device": str(device), "checkpoint_state": args.state,
        "per_role": args.per_role, "formal_patch": 768, "formal_core": 384,
        "selected_items": len(indices), "rows": rows,
        "checkpoint_metrics": checkpoint.get("metrics", {}),
    }
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    args.output.with_suffix(".progress.json").write_text(json.dumps({
        "status": "complete", "epoch": args.epoch, "selected_items": len(indices),
        "rows": len(rows), "output": str(args.output),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "epoch": args.epoch, "rows": len(rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
