"""Read-only audit of dense versus localized supervision for sparse branches.

This script never changes a checkpoint.  It asks whether the current full-frame
average loss hides local-contrast, boundary and texture targets, and whether a
smooth support-balanced loss supplies a usable private-branch gradient.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'))
WEIGHT = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights" / "epoch_026.pth.tar"
OUTPUT = ROOT / "reports" / "objective_gradient_conflicts" / "epoch026_sparse_branch_supervision_audit.json"
BRANCHES = ("local_contrast", "boundary", "texture")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load("r95_sparse_branch_audit_train", ROOT / "training" / "train_r95.py")


def gradient(loss: torch.Tensor, parameters: list[torch.nn.Parameter]) -> torch.Tensor:
    values = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
    return torch.cat([
        (torch.zeros_like(parameter) if value is None else value).reshape(-1)
        for parameter, value in zip(parameters, values)
    ])


def relation(left: torch.Tensor, right: torch.Tensor) -> dict[str, float]:
    left_norm, right_norm = left.norm(), right.norm()
    denominator = left_norm * right_norm
    return {
        "cosine": float(torch.dot(left, right) / denominator) if float(denominator) > 1e-12 else 0.0,
        "left_norm": float(left_norm),
        "right_norm": float(right_norm),
        "right_to_left_norm_ratio": float(right_norm / left_norm.clamp_min(1e-12)),
    }


def localized_loss(prediction: torch.Tensor, truth: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Continuously balance target-bearing and quiet regions without a hard mask."""
    beta = 1.0 / 255.0
    element = F.smooth_l1_loss(prediction, truth, beta=beta, reduction="none")
    amplitude = truth.detach().abs()
    support = amplitude / (amplitude + beta)
    quiet = 1.0 - support
    active_error = (element * support).sum() / support.sum().clamp_min(1.0)
    quiet_error = (element * quiet).sum() / quiet.sum().clamp_min(1.0)
    whole_error = element.mean()
    mean_amplitude = amplitude.mean()
    presence = mean_amplitude / (mean_amplitude + 0.25 * beta)
    total = 0.30 * whole_error + 0.70 * presence * active_error + 0.20 * quiet_error
    return total, {
        "whole": whole_error,
        "active": active_error,
        "quiet": quiet_error,
        "support_mean": support.mean(),
        "presence": presence,
        "target_abs_mean": mean_amplitude,
    }


def one_index_per_role(dataset) -> list[int]:
    selected: dict[str, int] = {}
    for index in range(len(dataset)):
        selected.setdefault(dataset.role_at(index), index)
    return [selected[role] for role in sorted(selected)]


def main() -> int:
    torch.set_num_threads(4)
    device = torch.device("cuda:0")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    dataset = TRAIN.DATA.R95SceneDataset(SOURCE, manifest, "train", 768, 384, 27, master_seed=950041)
    checkpoint = torch.load(WEIGHT, map_location="cpu", weights_only=False)
    model = TRAIN.MODEL.build_model(base=16).to(device).train()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    groups = model.parameter_groups()
    rows = []
    for position, index in enumerate(one_index_per_role(dataset), 1):
        item = dataset[index]
        batch = {name: value.to(device) if torch.is_tensor(value) else value for name, value in item.items()}
        details = model(
            batch["source"], return_details=True,
            stage_truth={
                "sensor_clean_base": batch["noise_free_source"],
                "restoration_base": batch["optical_source"],
                "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
                "need_truth": batch["need_truth_s"],
                "evidence_truth": batch["evidence_truth_s"],
            },
            stage_truth_fraction=0.0,
        )
        _, branch_values = TRAIN.branch_losses(details, batch, 768, 384)
        output_total, _ = TRAIN.full_output_losses(details, batch, 768, 384)
        row = {"role": item["role"], "scene_id": item["scene_id"], "groups": {}}
        pairs = {
            "local_contrast": (details["local_contrast_raw"], batch["local_contrast_target"]),
            "boundary": (details["boundary_restoration_raw"], batch["boundary_target"]),
            "texture": (details["texture_restoration_raw"], batch["texture_target"]),
        }
        for name in BRANCHES:
            prediction, truth = pairs[name]
            prediction = TRAIN.core_crop(prediction, 768, 384)
            truth = TRAIN.core_crop(truth, 768, 384)
            proposed, components = localized_loss(prediction, truth)
            parameters = [parameter for parameter in groups[name] if parameter.requires_grad]
            old_gradient = gradient(branch_values[name], parameters)
            proposed_gradient = gradient(proposed, parameters)
            output_gradient = gradient(output_total, parameters)
            row["groups"][name] = {
                "old_loss": float(branch_values[name].detach()),
                "localized_loss": float(proposed.detach()),
                **{key: float(value.detach()) for key, value in components.items()},
                "old_vs_localized": relation(old_gradient, proposed_gradient),
                "old_vs_output": relation(old_gradient, output_gradient),
                "localized_vs_output": relation(proposed_gradient, output_gradient),
            }
        rows.append(row)
        del details, branch_values, output_total
        torch.cuda.empty_cache()
        print(json.dumps({"sample": position, "role": item["role"]}), flush=True)

    summary = {}
    for name in BRANCHES:
        values = [row["groups"][name] for row in rows]
        summary[name] = {
            "support_mean": sum(value["support_mean"] for value in values) / len(values),
            "target_abs_mean_gray": 255.0 * sum(value["target_abs_mean"] for value in values) / len(values),
            "localized_to_old_gradient_norm_ratio": sum(
                value["old_vs_localized"]["right_to_left_norm_ratio"] for value in values
            ) / len(values),
            "old_output_conflict_count": sum(value["old_vs_output"]["cosine"] < 0.0 for value in values),
            "localized_output_conflict_count": sum(value["localized_vs_output"]["cosine"] < 0.0 for value in values),
        }
    payload = {
        "checkpoint": str(WEIGHT),
        "dataset_epoch": 27,
        "patch": 768,
        "core": 384,
        "purpose": "read_only_test_of_soft_support_balanced_branch_supervision",
        "summary": summary,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(json.dumps(summary, indent=2), flush=True)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
