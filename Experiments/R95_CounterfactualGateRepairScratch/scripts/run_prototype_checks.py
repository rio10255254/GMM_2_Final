"""CPU-verifiable R95 architecture and causal-routing checks."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE_R93 = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch'))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def synthetic_triplet(size: int = 256) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    cx, cy = size * 0.49, size * 0.51
    ellipse = (((xx - cx) / (size * 0.24)) ** 2 + ((yy - cy) / (size * 0.18)) ** 2) <= 1.0
    texture = 0.045 * np.sin(xx * 0.19) + 0.025 * np.cos(yy * 0.13) + 0.018 * np.sin((xx + yy) * 0.31)
    clean = np.where(ellipse, 0.78 + texture, 0.16 + 0.45 * texture).astype(np.float32)
    clean = np.clip(clean, 0.0, 1.0)
    optical = cv2.GaussianBlur(clean, (0, 0), sigmaX=1.05, sigmaY=0.75)
    noise_free = np.clip(0.94 * optical + 0.025, 0.0, 1.0)
    rng = np.random.default_rng(950041)
    noisy = noise_free + rng.normal(0.0, 0.010, clean.shape).astype(np.float32)
    noisy += 0.004 * np.sin(xx * 2 * np.pi / 31.0)
    noisy = np.clip(noisy, 0.0, 1.0)
    tensor = lambda a: torch.from_numpy(a.copy())[None, None]
    return tensor(clean), tensor(optical), tensor(noise_free), tensor(noisy)


def gradient_norm(loss: torch.Tensor, parameters: list[torch.nn.Parameter]) -> float:
    gradients = torch.autograd.grad(loss, parameters, allow_unused=True, retain_graph=True)
    total = sum((torch.zeros_like(p) if g is None else g).square().sum() for p, g in zip(parameters, gradients))
    return float(torch.sqrt(total))


def run() -> dict[str, Any]:
    torch.manual_seed(950041)
    torch.set_num_threads(2)
    model_module = load("r95_model_check", ROOT / "model" / "r95_model.py")
    targets_module = load("r95_targets_check", ROOT / "training" / "counterfactual_targets.py")
    descent_module = load("r95_descent_check", ROOT / "training" / "common_descent.py")
    inference = load("r95_inference_check", ROOT / "inference" / "reconstruct.py")
    model = model_module.build_model(base=8).cpu().eval()
    contract = model_module.architecture_contract(model)
    clean, optical_source, noise_free, noisy = synthetic_triplet()

    details = model(noisy, return_details=True)
    identity_error = float((details["output"] - noisy).abs().max() * 255.0)
    branch_initial_max = {
        name: float(details[name].abs().max() * 255.0)
        for name in (
            "radiometry_delta", "nuisance_delta", "local_contrast_delta",
            "restoration_delta", "correction",
        )
    }
    control_differences = {
        "boundary_need_vs_evidence": float((details["need_boundary"] - details["boundary_evidence"]).abs().max()),
        "texture_need_vs_evidence": float((details["need_texture"] - details["texture_recoverability"]).abs().max()),
        "local_contrast_need_vs_evidence": float(
            (details["need_local_contrast"] - details["local_contrast_evidence"]).abs().max()
        ),
    }

    views = targets_module.build_counterfactual_views(
        clean, noise_free, noisy, optical_source=optical_source
    )
    noisy_view = views["S_noisy"]
    target_control_differences = {
        "boundary_need_vs_evidence": float((noisy_view.need_boundary - noisy_view.boundary_evidence).abs().mean()),
        "texture_need_vs_evidence": float((noisy_view.need_texture - noisy_view.texture_recoverability).abs().mean()),
        "boundary_vs_texture_need": float((noisy_view.need_boundary - noisy_view.need_texture).abs().mean()),
        "boundary_vs_texture_evidence": float((noisy_view.boundary_evidence - noisy_view.texture_recoverability).abs().mean()),
        "local_contrast_need_vs_evidence": float(
            (noisy_view.need_local_contrast - noisy_view.local_contrast_evidence).abs().mean()
        ),
    }
    clear = views["T_clear"]
    clear_zero_target_max = max(
        float(getattr(clear, name).abs().max())
        for name in (
            "radiometry_component", "nuisance_component", "local_contrast_component",
            "boundary_component", "texture_component", "radiometry_effective", "nuisance_effective",
            "local_contrast_effective", "boundary_effective", "texture_effective",
            "restoration_raw", "restoration_effective", "need_radiometry", "need_noise",
            "need_local_contrast", "need_boundary", "need_texture",
        )
    )
    clear_evidence_error = max(
        float((clear.boundary_evidence - 1.0).abs().max()),
        float((clear.texture_recoverability - 1.0).abs().max()),
        float((clear.local_contrast_evidence - 1.0).abs().max()),
    )
    target_recomposition = {}
    for name, view in views.items():
        recomposed = (view.source + view.radiometry_effective + view.nuisance_effective + view.restoration_effective).clamp(0.0, 1.0)
        target_recomposition[name] = float((recomposed - view.target).abs().max() * 255.0)

    # Reconstruction losses cannot manipulate the control or geometry maps.
    model.zero_grad(set_to_none=True)
    details = model(noisy, return_details=True)
    reconstruction_loss = F.l1_loss(details["output"], views["S_noisy"].target)
    control_parameters = (
        list(model.need_tower.parameters()) + list(model.need_head.parameters())
        + list(model.evidence_tower.parameters()) + list(model.evidence_head.parameters())
    )
    geometry_parameters = list(model.geometry_head.parameters())
    control_shortcut_gradient = gradient_norm(reconstruction_loss, control_parameters)
    geometry_shortcut_gradient = gradient_norm(reconstruction_loss, geometry_parameters)

    direct_control_loss = (
        F.mse_loss(details["need_radiometry"], views["S_noisy"].need_radiometry)
        + F.mse_loss(details["need_noise"], views["S_noisy"].need_noise)
        + F.mse_loss(details["need_local_contrast"], views["S_noisy"].need_local_contrast)
        + F.mse_loss(details["local_contrast_evidence"], views["S_noisy"].local_contrast_evidence)
        + F.mse_loss(details["need_boundary"], views["S_noisy"].need_boundary)
        + F.mse_loss(details["boundary_evidence"], views["S_noisy"].boundary_evidence)
        + F.mse_loss(details["need_texture"], views["S_noisy"].need_texture)
        + F.mse_loss(details["texture_recoverability"], views["S_noisy"].texture_recoverability)
    )
    direct_control_gradient = gradient_norm(direct_control_loss, control_parameters)

    task_gradients = [
        torch.tensor([1.0, 0.0, 0.2]),
        torch.tensor([-0.8, 0.4, 0.1]),
        torch.tensor([0.1, -0.6, 1.0]),
    ]
    common = descent_module.common_descent_direction(task_gradients, passes=12)
    common_dots = [float(torch.dot(common, gradient)) for gradient in task_gradients]

    real_initial_identity = {}
    for path in sorted((SOURCE_R93 / "data" / "live_validation").glob("*.bmp")):
        array = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        tensor = torch.from_numpy(array.astype(np.float32) / 255.0)[None, None]
        with torch.inference_mode():
            output = model(tensor)
        real_initial_identity[path.name] = float((output - tensor).abs().max() * 255.0)

    # Activate every output head after the identity/control checks.  This makes
    # parity and equivariance tests non-trivial instead of passing because the
    # initialized residual is zero.
    generator = torch.Generator().manual_seed(940094)
    with torch.no_grad():
        for head in (
            model.radiometry_head, model.nuisance_head, model.local_contrast_head,
            model.boundary_head, model.texture_head,
        ):
            head.weight.copy_(0.02 * torch.randn(head.weight.shape, generator=generator))
            head.bias.copy_(0.01 * torch.randn(head.bias.shape, generator=generator))
        model.need_head.weight.copy_(0.01 * torch.randn(model.need_head.weight.shape, generator=generator))
        model.need_head.bias.copy_(torch.tensor([-0.5, -0.4, -0.3, -0.2, -0.1]))
        model.evidence_head.weight.copy_(0.01 * torch.randn(model.evidence_head.weight.shape, generator=generator))
        model.evidence_head.bias.copy_(torch.tensor([0.2, 0.3, 0.4]))
        model.geometry_head.weight.copy_(0.01 * torch.randn(model.geometry_head.weight.shape, generator=generator))

    # Exact parity uses the same canonical padded canvas and a halo far larger
    # than the prototype receptive field.
    parity_input = torch.rand((1, 1, 197, 213), generator=torch.Generator().manual_seed(94))
    full = inference.reconstruct_full_reference(model, parity_input, core_size=64, halo=192)
    tiled = inference.reconstruct_tensor(model, parity_input, core_size=64, halo=192, tile_batch=2)
    parity_max = float((full - tiled).abs().max() * 255.0)

    # Shift equivariance is evaluated on the valid interior; border synthesis is
    # intentionally excluded.  Roll is used only to create a controlled integer
    # translation and the wrapped region is cropped away.
    shift = (8, -8)
    equivariance_input = F.pad(noisy, (96, 96, 96, 96), mode="reflect")
    original = model(equivariance_input, return_details=True)
    shifted_input = torch.roll(equivariance_input, shifts=shift, dims=(-2, -1))
    shifted = model(shifted_input, return_details=True)
    margin = 96
    equivariance = {}
    for name in (
        "output", "radiometry_delta", "nuisance_delta", "local_contrast_delta",
        "boundary_delta", "texture_delta", "need_local_contrast", "local_contrast_evidence",
        "need_boundary", "boundary_evidence", "need_texture", "texture_recoverability",
    ):
        expected = torch.roll(original[name], shifts=shift, dims=(-2, -1))
        difference = shifted[name][..., margin:-margin, margin:-margin] - expected[..., margin:-margin, margin:-margin]
        equivariance[name] = float(difference.abs().max() * 255.0)

    checks = {
        "model_is_exact_identity_at_initialization": identity_error == 0.0 and max(branch_initial_max.values()) == 0.0,
        # Neutral biases intentionally make all untrained maps equal to 0.5;
        # distinction is an architectural and supervised-target property, not
        # something a randomly initialized model should fabricate.
        "need_and_recoverability_are_distinct_maps": (
            contract["need_and_recoverability_are_distinct"] is True
            and min(target_control_differences.values()) > 1e-4
        ),
        "boundary_and_texture_paths_are_separate": contract["boundary_and_texture_learned_towers_are_distinct"] is True,
        "local_contrast_has_private_learned_tower": contract["local_contrast_has_private_learned_tower"] is True,
        "need_and_evidence_paths_are_separate": contract["need_and_evidence_learned_towers_are_distinct"] is True,
        "all_output_branches_are_controlled": contract["all_correction_paths_controlled"] is True,
        "no_independent_edge_painting_output_exists": contract["independent_edge_painting_branch"] is False,
        "counterfactual_clean_view_has_zero_branch_and_need_targets_and_unit_recoverability": clear_zero_target_max == 0.0 and clear_evidence_error == 0.0,
        "counterfactual_branch_targets_sum_to_effective_target": max(target_recomposition.values()) < 1e-5,
        "control_tower_receives_no_reconstruction_shortcut_gradient": control_shortcut_gradient == 0.0,
        "geometry_tower_receives_no_reconstruction_shortcut_gradient": geometry_shortcut_gradient == 0.0,
        "control_tower_receives_direct_supervision_gradient": direct_control_gradient > 0.0,
        "common_descent_direction_is_nonopposing_to_every_objective": min(common_dots) >= -1e-7,
        "full_and_tiled_float32_outputs_are_exact": parity_max == 0.0,
        "translated_input_produces_translated_branch_outputs_on_valid_interior": max(equivariance.values()) < 1e-4,
        "real_inputs_are_exact_identity_at_initialization": max(real_initial_identity.values(), default=0.0) == 0.0,
        "private_learned_parameter_groups_do_not_overlap": contract["learned_parameter_group_overlap"] is False,
    }
    return {
        "prototype_id": "R95_CAUSAL_ROUTING_PROTOTYPE_V2",
        "passed": all(checks.values()),
        "formal_training_started": False,
        "checks": checks,
        "architecture_contract": contract,
        "metrics": {
            "identity_max_abs_gray": identity_error,
            "initial_branch_max_abs_gray": branch_initial_max,
            "control_map_max_differences": control_differences,
            "target_control_map_mean_differences": target_control_differences,
            "clear_zero_target_max_abs": clear_zero_target_max,
            "clear_evidence_max_abs_error": clear_evidence_error,
            "target_recomposition_max_abs_gray": target_recomposition,
            "control_shortcut_gradient_norm": control_shortcut_gradient,
            "geometry_shortcut_gradient_norm": geometry_shortcut_gradient,
            "direct_control_gradient_norm": direct_control_gradient,
            "common_descent_task_dots": common_dots,
            "full_vs_tiled_max_abs_gray": parity_max,
            "translation_equivariance_max_abs_gray": equivariance,
            "real_initial_identity_max_abs_gray": real_initial_identity,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(ROOT / "reports" / "prototype_report.json"))
    args = parser.parse_args()
    report = run()
    json_write(Path(args.report), report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

