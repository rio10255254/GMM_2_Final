"""CPU/GPU contract smoke for the independent R114D selector."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from .losses import selector_loss
from .model import (
    PROBE_ROOT,
    R114DActionSelector,
    SelectorConfig,
    forward_tiled_selector,
    load_frozen_e24_proposal,
    parameter_counts,
)
from .targets import build_selector_targets


def _module_hash(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _synthetic_batch(device: torch.device, side: int = 96) -> tuple[torch.Tensor, ...]:
    yy, xx = torch.meshgrid(
        torch.arange(side, device=device, dtype=torch.float32),
        torch.arange(side, device=device, dtype=torch.float32),
        indexing="ij",
    )
    sdf = (xx - side / 2.0).reshape(1, 1, side, side)
    target = 0.47 + 0.15 * torch.tanh(sdf / 0.95)
    source = 0.47 + 0.13 * torch.tanh((sdf - 0.6) / 2.4)
    source = source + 0.008 * torch.sin(0.31 * yy).reshape(1, 1, side, side)
    identity_source = target.clone()
    return (
        torch.cat([source, identity_source], dim=0).clamp(0, 1),
        torch.cat([target, target], dim=0).clamp(0, 1),
        torch.cat([sdf, sdf], dim=0),
        torch.tensor([False, True], device=device),
    )


def run(device: str, tile: bool) -> dict[str, object]:
    device = torch.device(device)
    torch.manual_seed(1145002)
    proposal, metadata = load_frozen_e24_proposal(device=device)
    model = R114DActionSelector(proposal, SelectorConfig.from_json()).to(device).train()
    source, target, sdf, identity = _synthetic_batch(device)
    before = _module_hash(model.proposal)
    initial = model.forward_details(source)
    exact_neutral = bool(torch.equal(initial.output, initial.base_output))
    exact_zero = bool(
        torch.count_nonzero(initial.acceptance) == 0
        and torch.count_nonzero(initial.amount) == 0
        and torch.count_nonzero(initial.selected_delta) == 0
    )
    labels = build_selector_targets(initial, target, sdf, identity)
    losses = selector_loss(initial, labels)
    losses.total.backward()
    selector_gradient = float(
        sum(
            parameter.grad.detach().abs().sum()
            for parameter in model.selector.parameters()
            if parameter.grad is not None
        )
    )
    proposal_has_gradient = any(parameter.grad is not None for parameter in model.proposal.parameters())
    optimizer = torch.optim.AdamW(model.selector_parameters(), lr=3.0e-4)
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    trained = model.forward_details(source)
    gate_formula_error = float(
        (
            trained.causal_gate
            - trained.boundary_confidence
            * trained.correction_need
            * trained.recoverability
            * trained.acceptance
            * trained.amount
        )
        .abs()
        .max()
    )
    after = _module_hash(model.proposal)
    tile_error = None
    tile_diagnostic_error = None
    tile_field_errors = None
    if tile:
        # A real interior tile requires H/W > 2*halo + core.  Keep batch one to
        # bound GPU memory while still exercising the sealed full E24 model.
        core_size = 224
        side = 2 * model.minimum_halo_px + core_size + 1
        large_source, _, _, _ = _synthetic_batch(device, side=side)
        large_source = large_source[:1]
        model.eval()
        # Exercise an active selector, not only the exact-zero initialization.
        with torch.no_grad():
            model.selector.acceptance_head.bias.fill_(1.0)
            model.selector.amount_head.bias.fill_(1.0)
        with torch.inference_mode():
            full = model.forward_details(large_source)
            tiled = forward_tiled_selector(model, large_source, core_size=core_size)
        tile_field_errors = {
            item.name: float(
                (getattr(full, item.name) - getattr(tiled, item.name)).abs().max()
            )
            for item in __import__("dataclasses").fields(full)
        }
        tile_diagnostic_error = max(tile_field_errors.values())
        # The contractual stitched values are the deployed image and actual
        # selected action.  Highly nonlinear diagnostic maps (notably the
        # predicted 10--14 px band) may amplify harmless GPU roundoff.
        tile_error = max(
            tile_field_errors[name]
            for name in ("output", "causal_gate", "profile_gate", "selected_delta")
        )
    report = {
        "device": str(device),
        "proposal": metadata,
        "parameter_counts": parameter_counts(model),
        "initial_acceptance_and_amount_exact_zero": exact_zero,
        "initial_output_exactly_base": exact_neutral,
        "selector_gradient_sum": selector_gradient,
        "proposal_has_gradient": proposal_has_gradient,
        "proposal_state_unchanged": before == after,
        "gate_formula_max_abs": gate_formula_error,
        "positive_labels": int(labels.positive_mask.sum()),
        "negative_labels": int(labels.negative_mask.sum()),
        "supervised_outside_true_band_pixels": int(
            (labels.supervision_mask & ~labels.boundary_band).sum()
        ),
        "unauthorized_background_pixels": int(
            (
                labels.supervision_mask
                & ~labels.boundary_band
                & ~labels.identity_negative_mask
            ).sum()
        ),
        "tile_max_abs": tile_error,
        "tile_diagnostic_max_abs": tile_diagnostic_error,
        "tile_field_max_abs": tile_field_errors,
    }
    report["pass"] = bool(
        exact_zero
        and exact_neutral
        and selector_gradient > 0
        and not proposal_has_gradient
        and before == after
        and gate_formula_error == 0.0
        and report["unauthorized_background_pixels"] == 0
        and (tile_error is None or tile_error <= 3.0e-5)
    )
    output = PROBE_ROOT / "smoke_results" / f"{device.type}_smoke.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--tile", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(run(**vars(parse_args())), indent=2))
