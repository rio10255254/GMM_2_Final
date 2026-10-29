"""Measure whether R100's detail, regular restoration, geometry and safety gradients conflict."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import default_collate
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R100 = Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch'))
PACKAGE = Path(str(PROJECT_ROOT / 'Experiments/R92_PhysicalTransitionBalancedScratch/data/r92_formal'))
OUTPUT = ROOT / "results" / "gradient_conflicts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load_module("r101_train_module", R100 / "training" / "train_r100.py")
MODEL = load_module("r101_model_module", R100 / "model" / "r100_model.py")


def weighted_mean(error: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return (error * weight).sum() / weight.sum().clamp_min(1.0)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    dataset = TRAIN.R100SceneDataset(PACKAGE, manifest, "train", 256, 128, 16)
    detail_indices = [i for i in range(len(dataset)) if dataset.detail_recovery_at(i)][:2]
    regular_indices = [i for i in range(len(dataset)) if dataset.role_at(i) in {"textured_general_geometry", "difficult_contour"} and not dataset.detail_recovery_at(i)][:1]
    identity_indices = [i for i in range(len(dataset)) if dataset.role_at(i) == "identity_and_detail_guard"][:1]
    motion_indices = [i for i in range(len(dataset)) if dataset.role_at(i) == "signed_subpixel_motion" and dataset.motion_kind_at(i) == "signed"][:1]
    clean_indices = [i for i in range(len(dataset)) if dataset.role_at(i) == "clean_contour_anchor" and not dataset.detail_recovery_at(i)][:1]
    indices = detail_indices + regular_indices + identity_indices + motion_indices + clean_indices
    if len(indices) != 6:
        raise RuntimeError(f"Unable to construct diagnostic batch: {indices}")
    batch = default_collate([dataset[i] for i in indices])
    selected = [{"index": int(i), "role": dataset.role_at(i), "detail_recovery": bool(dataset.detail_recovery_at(i)), "motion_kind": dataset.motion_kind_at(i)} for i in indices]

    design = json.loads((R100 / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    protocol = json.loads((R100 / "config" / "posttraining_validation_protocol.json").read_text(encoding="utf-8"))
    checkpoint = torch.load(Path(PROJECT_ROOT / protocol["checkpoint"]), map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.train().to(device)
    source = batch["source"].to(device)
    target = batch["target"].to(device)
    mask = batch["mask"].to(device)
    sdf = batch["sdf"].to(device)
    scenes, views = source.shape[:2]
    details = model(source.reshape(-1, 1, 256, 256), return_details=True)
    core = slice(64, 192)
    prediction = details["output"][..., core, core]
    target_core = target[..., core, core].reshape(-1, 1, 128, 128)
    source_core = source[..., core, core].reshape(-1, 1, 128, 128)
    mask_core = mask[..., core, core].reshape(-1, 1, 128, 128)
    sdf_core = sdf[..., core, core].reshape(-1, 1, 128, 128)
    material = torch.sigmoid((sdf_core.abs() - 4.0) / 2.0)
    predicted_fine = prediction - TRAIN.lowpass(prediction, 3)
    target_fine = target_core - TRAIN.lowpass(target_core, 3)
    high_error = F.smooth_l1_loss(predicted_fine, target_fine, beta=1.0 / 255.0, reduction="none")
    detail_selector = batch["detail_recovery_view"].to(device).reshape(-1)
    identity_selector = batch["identity"].to(device).reshape(-1)
    regular_selector = (~detail_selector) & (~identity_selector)
    detail_loss = weighted_mean(high_error[detail_selector], material[detail_selector])
    regular_high_loss = weighted_mean(high_error[regular_selector], material[regular_selector])

    boundary_level = batch["boundary_level"].to(device).repeat_interleave(views)
    polarity = batch["polarity"].to(device).repeat_interleave(views)
    probability = TRAIN.foreground_probability(prediction, boundary_level, polarity)
    geometry_loss = F.l1_loss(TRAIN.soft_boundary(probability), TRAIN.soft_boundary(mask_core))
    pixel_loss = F.smooth_l1_loss(prediction, target_core, beta=1.0 / 255.0)
    identity_loss = F.l1_loss(prediction[identity_selector], source_core[identity_selector])

    scene_probability = probability.reshape(scenes, views, 1, 128, 128)
    scene_mask = mask_core.reshape(scenes, views, 1, 128, 128)
    motion_scene = batch["pair_kind"].to(device) == 1
    selected_probability = scene_probability[motion_scene]
    selected_mask = scene_mask[motion_scene]
    support = F.max_pool2d(selected_mask.reshape(-1, 1, 128, 128), 49, stride=1, padding=24)
    pred_centers = TRAIN.supported_edge_centroid(selected_probability.reshape(-1, 1, 128, 128), support).reshape(-1, 2, 2)
    target_centers = TRAIN.supported_edge_centroid(selected_mask.reshape(-1, 1, 128, 128), support).reshape(-1, 2, 2)
    motion_loss = F.smooth_l1_loss(pred_centers[:, 1] - pred_centers[:, 0], target_centers[:, 1] - target_centers[:, 0], beta=0.05)

    objectives = {
        "detail_recovery": detail_loss,
        "regular_high_frequency": regular_high_loss,
        "geometry": geometry_loss,
        "motion": motion_loss,
        "identity": identity_loss,
        "pixel_all": pixel_loss,
    }
    shared = [parameter for name, parameter in model.named_parameters() if parameter.requires_grad and "_head" not in name]
    vectors: dict[str, torch.Tensor] = {}
    norms: dict[str, float] = {}
    for name, objective in objectives.items():
        grads = torch.autograd.grad(objective, shared, retain_graph=True, allow_unused=True)
        vector = torch.cat([(torch.zeros_like(parameter) if grad is None else grad).reshape(-1) for parameter, grad in zip(shared, grads)])
        vectors[name] = vector
        norms[name] = float(torch.linalg.vector_norm(vector))
    cosine: dict[str, dict[str, float]] = {}
    for left, left_vector in vectors.items():
        cosine[left] = {}
        for right, right_vector in vectors.items():
            denominator = torch.linalg.vector_norm(left_vector) * torch.linalg.vector_norm(right_vector)
            cosine[left][right] = float(torch.dot(left_vector, right_vector) / denominator.clamp_min(1e-12))
    conflicts = []
    names = list(objectives)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            if cosine[left][right] < 0.0:
                conflicts.append({"left": left, "right": right, "cosine": cosine[left][right]})
    result = {
        "status": "complete",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "diagnostic_batch": selected,
        "objective_values": {name: float(value.detach()) for name, value in objectives.items()},
        "shared_gradient_norms": norms,
        "shared_gradient_cosine": cosine,
        "conflicting_pairs": sorted(conflicts, key=lambda row: row["cosine"]),
        "scope": "One deterministic mixed diagnostic batch; use as a directional test, not a population estimate.",
    }
    (OUTPUT / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
