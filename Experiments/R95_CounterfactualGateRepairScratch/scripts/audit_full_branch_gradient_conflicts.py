"""Read-only full-branch gradient conflict audit on the epoch-33 large-patch transition."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'))
WEIGHT = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights" / "epoch_032.pth.tar"
OUTPUT = ROOT / "reports" / "objective_gradient_conflicts" / "epoch032_full_branch_on_epoch33_large_patch.json"
BRANCHES = ("local_contrast", "boundary", "texture")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load("r95_full_gradient_audit_train", ROOT / "training" / "train_r95.py")


def gradient(loss: torch.Tensor, parameters: list[torch.nn.Parameter]) -> torch.Tensor:
    values = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
    return torch.cat([
        (torch.zeros_like(parameter) if value is None else value).reshape(-1)
        for parameter, value in zip(parameters, values)
    ])


def relation(own: torch.Tensor, output: torch.Tensor) -> dict[str, float]:
    own_norm, output_norm = own.norm(), output.norm()
    denominator = own_norm * output_norm
    combined = own + output
    combined_norm = combined.norm()
    return {
        "cosine": float(torch.dot(own, output) / denominator) if float(denominator) > 1e-12 else 0.0,
        "own_norm": float(own_norm),
        "output_norm": float(output_norm),
        "output_to_own_norm_ratio": float(output_norm / own_norm.clamp_min(1e-12)),
        "own_to_applied_cosine": float(torch.dot(own, combined) / (own_norm * combined_norm).clamp_min(1e-12)),
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
    dataset = TRAIN.DATA.R95SceneDataset(SOURCE, manifest, "train", 896, 512, 33, master_seed=950041)
    checkpoint = torch.load(WEIGHT, map_location="cpu", weights_only=False)
    model = TRAIN.MODEL.build_model(base=16).to(device).train()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    groups = model.parameter_groups()
    rows = []
    for position, index in enumerate(one_index_per_role(dataset), 1):
        item = dataset[index]
        batch = {
            name: (
                value[0:1].to(device)
                if torch.is_tensor(value) and value.ndim > 0 and value.shape[0] == item["source"].shape[0]
                else value.to(device) if torch.is_tensor(value) else value
            )
            for name, value in item.items()
        }
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
        _, branch_values = TRAIN.branch_losses(details, batch, 896, 512)
        output_total, _ = TRAIN.full_output_losses(details, batch, 896, 512)
        row = {"role": item["role"], "scene_id": item["scene_id"], "groups": {}}
        for name in BRANCHES:
            parameters = [parameter for parameter in groups[name] if parameter.requires_grad]
            own = gradient(branch_values[name], parameters)
            output = gradient(output_total, parameters)
            row["groups"][name] = relation(own, output)
        rows.append(row)
        del details, branch_values, output_total
        torch.cuda.empty_cache()
        print(json.dumps({"sample": position, "role": item["role"]}), flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "checkpoint": str(WEIGHT), "dataset_epoch": 33,
        "patch": 896, "core": 512, "branches": BRANCHES, "rows": rows,
    }, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
