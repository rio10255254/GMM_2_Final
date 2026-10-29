"""Read-only branch-vs-auxiliary gradient audit at the epoch-33 transition."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'))
WEIGHT = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights" / "epoch_026.pth.tar"
OUTPUT = ROOT / "reports" / "objective_gradient_conflicts" / "epoch026_auxiliaries_on_epoch27_transition.json"
BRANCHES = ("local_contrast", "boundary", "texture")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load("r95_aux_gradient_audit_train", ROOT / "training" / "train_r95.py")


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
        "left_norm": float(left_norm), "right_norm": float(right_norm),
        "right_to_left_norm_ratio": float(right_norm / left_norm.clamp_min(1e-12)),
    }


def selected_indices(dataset) -> list[int]:
    selected: dict[str, int] = {}
    eligible_roles = {
        "exposure_coherent_bundle",
        "persistent_detail_bundle",
        "signed_subpixel_motion",
    }
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role in eligible_roles:
            selected.setdefault(role, index)
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
    for position, index in enumerate(selected_indices(dataset), 1):
        item = dataset[index]
        batch = {name: value.to(device) if torch.is_tensor(value) else value for name, value in item.items()}
        views = int(batch["source"].shape[0])
        details = model(
            batch["source"], return_details=True,
            stage_truth={
                "sensor_clean_base": batch["noise_free_source"],
                "restoration_base": batch["optical_source"],
                "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
                "need_truth": batch["need_truth_s"],
                "evidence_truth": batch["evidence_truth_s"],
            }, stage_truth_fraction=0.0,
        )
        _, branch_values = TRAIN.branch_losses(details, batch, 768, 384)
        motion = 0.30 * TRAIN.motion_loss(details, batch, 768, 384, 1, views)
        cross_noise = 0.25 * TRAIN.cross_noise_consistency(details, batch, 768, 384, 1, views)
        row = {
            "role": item["role"], "scene_id": item["scene_id"],
            "pair_kind": int(item["pair_kind"]), "views": views,
            "motion_loss": float(motion.detach()), "cross_noise_loss": float(cross_noise.detach()),
            "groups": {},
        }
        for name in BRANCHES:
            parameters = list(groups[name])
            own = gradient(branch_values[name], parameters)
            motion_gradient = gradient(motion, parameters)
            noise_gradient = gradient(cross_noise, parameters)
            row["groups"][name] = {
                "own_vs_motion": relation(own, motion_gradient),
                "own_vs_cross_noise": relation(own, noise_gradient),
            }
        rows.append(row)
        del details, branch_values, motion, cross_noise
        torch.cuda.empty_cache()
        print(json.dumps({"sample": position, "role": item["role"], "pair_kind": int(item["pair_kind"])}), flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "checkpoint": str(WEIGHT), "dataset_epoch": 27,
        "patch": 768, "core": 384, "branches": BRANCHES, "rows": rows,
    }, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
