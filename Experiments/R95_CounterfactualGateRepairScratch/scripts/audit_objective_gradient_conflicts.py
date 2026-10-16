"""Read-only head-gradient conflict audit at the epoch-32 to large-patch transition."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch\data\r93_formal")
WEIGHT = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights" / "epoch_032.pth.tar"
OUTPUT = ROOT / "reports" / "objective_gradient_conflicts" / "epoch032_on_epoch33_large_patch.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load("r95_gradient_audit_train", ROOT / "training" / "train_r95.py")


def flatten(values: tuple[torch.Tensor | None, ...], parameters: list[torch.nn.Parameter]) -> torch.Tensor:
    return torch.cat([
        (torch.zeros_like(parameter) if value is None else value).reshape(-1)
        for parameter, value in zip(parameters, values)
    ])


def gradient(loss: torch.Tensor, parameters: list[torch.nn.Parameter]) -> torch.Tensor:
    return flatten(
        torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True),
        parameters,
    )


def relation(left: torch.Tensor, right: torch.Tensor) -> dict[str, float]:
    left_norm = left.norm()
    right_norm = right.norm()
    denominator = left_norm * right_norm
    return {
        "cosine": float(torch.dot(left, right) / denominator) if float(denominator) > 1e-12 else 0.0,
        "dot": float(torch.dot(left, right)),
        "left_norm": float(left_norm),
        "right_norm": float(right_norm),
        "right_to_left_norm_ratio": float(right_norm / left_norm.clamp_min(1e-12)),
    }


def one_index_per_role(dataset) -> list[int]:
    selected: dict[str, int] = {}
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        selected.setdefault(role, index)
    return [selected[role] for role in sorted(selected)]


def main() -> int:
    torch.set_num_threads(4)
    device = torch.device("cuda:0")
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    dataset = TRAIN.DATA.R95SceneDataset(
        SOURCE, manifest, "train", 896, 512, 33, master_seed=950041,
    )
    checkpoint = torch.load(WEIGHT, map_location="cpu", weights_only=False)
    model = TRAIN.MODEL.build_model(base=16).to(device).train()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    heads = {
        "radiometry": list(model.radiometry_head.parameters()),
        "nuisance": list(model.nuisance_head.parameters()),
        "local_contrast": list(model.local_contrast_head.parameters()),
        "boundary": list(model.boundary_head.parameters()),
        "texture": list(model.texture_head.parameters()),
    }
    rows = []
    for position, index in enumerate(one_index_per_role(dataset), 1):
        item = dataset[index]
        # One deterministic view is sufficient for the primary-objective
        # direction test and avoids conflating it with pairwise motion losses.
        batch = {
            name: (
                value[0:1].to(device)
                if torch.is_tensor(value) and value.ndim > 0 and value.shape[0] == item["source"].shape[0]
                else value.to(device) if torch.is_tensor(value) else value
            )
            for name, value in item.items()
        }
        source = batch["source"]
        stage_truth = {
            "sensor_clean_base": batch["noise_free_source"],
            "restoration_base": batch["optical_source"],
            "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
            "need_truth": batch["need_truth_s"],
            "evidence_truth": batch["evidence_truth_s"],
        }
        details = model(
            source, return_details=True,
            stage_truth=stage_truth, stage_truth_fraction=0.0,
        )
        _, branch_values = TRAIN.branch_losses(details, batch, 896, 512)
        output_total, output_values = TRAIN.full_output_losses(details, batch, 896, 512)
        row = {
            "role": item["role"],
            "scene_id": item["scene_id"],
            "dataset_index": index,
            "output_loss": float(output_total.detach()),
            "groups": {},
        }
        for name, parameters in heads.items():
            own = gradient(branch_values[name], parameters)
            output = gradient(output_total, parameters)
            combined = own + output
            row["groups"][name] = {
                "own_loss": float(branch_values[name].detach()),
                "own_vs_output": relation(own, output),
                "own_vs_applied_primary": relation(own, combined),
                "output_vs_applied_primary": relation(output, combined),
            }
        rows.append(row)
        del details, output_total, output_values, branch_values
        torch.cuda.empty_cache()
        print(json.dumps({"sample": position, "role": item["role"]}), flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "checkpoint": str(WEIGHT),
        "checkpoint_state": "model_state_dict",
        "dataset_epoch": 33,
        "patch": 896,
        "core": 512,
        "view_policy": "first deterministic view per role",
        "rows": rows,
    }, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT)
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
