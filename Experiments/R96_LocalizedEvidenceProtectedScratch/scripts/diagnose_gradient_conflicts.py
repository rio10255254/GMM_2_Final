"""Read-only E44 gradient geometry audit on fixed validation roles."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import torch
from torch.utils.data._utils.collate import default_collate
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "deep_diagnosis" / "gradient_conflicts.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load("r96_grad_model", ROOT / "model" / "r96_model.py")
DATA = load("r96_grad_data", ROOT / "training" / "r96_dataset.py")
TRAINER = load("r96_grad_trainer", ROOT / "training" / "train_r96.py")
COMMON = load("r96_grad_common", ROOT / "training" / "common_descent.py")


def flatten_grad(loss: torch.Tensor, parameters: list[torch.nn.Parameter], *, group_ids: set[int] | None = None) -> torch.Tensor:
    selected = [p for p in parameters if group_ids is None or id(p) in group_ids]
    gradients = torch.autograd.grad(loss, selected, allow_unused=True)
    lookup = {id(p): g for p, g in zip(selected, gradients)}
    return torch.cat([
        (torch.zeros_like(p) if lookup.get(id(p)) is None else lookup[id(p)]).reshape(-1)
        if group_ids is None or id(p) in group_ids else torch.zeros_like(p).reshape(-1)
        for p in parameters
    ]).detach()


def cosine(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(torch.dot(a, b) / (a.norm() * b.norm()).clamp_min(1e-12))


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / design["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(
        ROOT / "weights" / "formal" / "seed_960041" / "R96_scratch_seed960041_20260813_131438" / "weights" / "epoch_044.pth.tar",
        map_location="cpu", weights_only=False,
    )
    dataset = DATA.R96SceneDataset(package, manifest, "validation", 256, 128, 0,
                                   all_observations=True, master_seed=960041)
    chosen: dict[str, int] = {}
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role in {"persistent_detail_bundle", "signed_subpixel_motion"} and role not in chosen:
            chosen[role] = index
    reports = []
    for role, index in chosen.items():
        model = MODEL.build_model(base=16).to(device)
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
        model.train()
        parameters = [p for p in model.parameters() if p.requires_grad]
        groups = model.parameter_groups()
        raw = default_collate([dataset[index]])
        batch, scenes, views = TRAINER.flatten_batch(raw, device)
        source = batch["source"]
        stage_truth = {
            "sensor_clean_base": batch["noise_free_source"],
            "restoration_base": batch["optical_source"],
            "contrast_restored_base": batch["optical_source"] + batch["local_contrast_target"],
            "need_truth": batch["need_truth_s"], "evidence_truth": batch["evidence_truth_s"],
        }

        def main_grads():
            details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=0.0)
            branch_total, values = TRAINER.branch_losses(details, batch, 256, 128)
            output_total, _ = TRAINER.full_output_losses(details, batch, 256, 128)
            primary = flatten_grad(branch_total + output_total, parameters)
            protected = {}
            for name in ("nuisance", "radiometry", "local_contrast", "boundary", "texture"):
                details_i = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=0.0)
                _, values_i = TRAINER.branch_losses(details_i, batch, 256, 128)
                protected[name] = flatten_grad(values_i[name], parameters, group_ids={id(p) for p in groups[name]})
            return primary, protected

        primary, protected = main_grads()
        control, _ = TRAINER.control_triplet(model, batch, 256, 128)
        control_grad = flatten_grad(0.55 * control, parameters)
        primary = primary + control_grad
        task_vectors = {"primary_plus_control": primary, **{f"protect_{k}": v for k, v in protected.items()}}

        details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=0.0)
        motion = TRAINER.motion_loss(details, batch, 256, 128, scenes, views)
        if float(motion.detach()) > 0:
            task_vectors["motion"] = flatten_grad(0.30 * motion, parameters)
        details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=0.0)
        cross = TRAINER.cross_noise_consistency(details, batch, 256, 128, scenes, views)
        if float(cross.detach()) > 0:
            task_vectors["cross_noise"] = flatten_grad(0.25 * cross, parameters)

        names = list(task_vectors)
        vectors = [task_vectors[name] for name in names]
        direction = COMMON.common_descent_direction(vectors, passes=8)
        reports.append({
            "role": role, "scene_id": str(batch["scene_id"][0]), "task_names": names,
            "task_norms": {name: float(vector.norm()) for name, vector in task_vectors.items()},
            "cosine_to_primary": {name: cosine(primary, vector) for name, vector in task_vectors.items()},
            "common_direction_norm": float(direction.norm()),
            "primary_norm": float(primary.norm()),
            "common_over_primary_norm": float(direction.norm() / primary.norm().clamp_min(1e-12)),
            "common_cosine_to_tasks": {name: cosine(direction, vector) for name, vector in task_vectors.items()},
        })
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"checkpoint_epoch": 44, "reports": reports}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "reports": reports}, indent=2))


if __name__ == "__main__":
    main()
