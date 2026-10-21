"""Actual sealed-source CPU/GPU contract smoke for R114E."""

from __future__ import annotations

import argparse
import json

import torch

from .losses import load_loss_config, selector_loss
from .model import PROBE_ROOT, build_hybrid, parameter_counts, source_state_hashes
from .targets import build_selector_targets, load_target_config


def _batch(device: torch.device, side: int = 96) -> tuple[torch.Tensor, ...]:
    yy, xx = torch.meshgrid(
        torch.arange(side, device=device, dtype=torch.float32),
        torch.arange(side, device=device, dtype=torch.float32),
        indexing="ij",
    )
    sdf = (xx - side / 2).reshape(1, 1, side, side)
    target = 0.47 + 0.15 * torch.tanh(sdf / 0.95)
    source = 0.47 + 0.13 * torch.tanh((sdf - 0.6) / 2.4)
    source = source + 0.008 * torch.sin(0.31 * yy).reshape(1, 1, side, side)
    return source.clamp(0, 1), target.clamp(0, 1), sdf, torch.tensor([False], device=device)


def run(device: str) -> dict[str, object]:
    selected = torch.device(device)
    torch.manual_seed(1146002)
    model = build_hybrid(selected).train()
    source, target, sdf, identity = _batch(selected)
    frozen_before = source_state_hashes(model)
    initial = model.forward_details(source)
    with torch.inference_mode():
        e20 = model.geometry_model.forward_details(source)
    labels = build_selector_targets(initial, target, sdf, identity, load_target_config())
    losses = selector_loss(initial, labels, load_loss_config())
    losses.total.backward()
    selector_gradient = float(sum(
        parameter.grad.detach().abs().sum()
        for parameter in model.selector.parameters()
        if parameter.grad is not None
    ))
    source_has_gradient = any(
        parameter.grad is not None
        for source_model in (model.geometry_model, model.profile_model)
        for parameter in source_model.parameters()
    )
    optimizer = torch.optim.AdamW(model.selector_parameters(), lr=3e-4)
    optimizer.step()
    frozen_after = source_state_hashes(model)
    trained = model.forward_details(source)
    gate_error = float((
        trained.causal_gate
        - trained.boundary_confidence
        * trained.correction_need
        * trained.recoverability
        * trained.acceptance
        * trained.amount
    ).abs().max())
    counts = parameter_counts(model)
    report = {
        "device": str(selected),
        "source_provenance": model.provenance,
        "parameter_counts": counts,
        "zero_selector_output_exactly_e20": torch.equal(initial.output, e20.output),
        "zero_selector_output_exactly_base": torch.equal(initial.output, initial.base_output),
        "zero_acceptance": int(torch.count_nonzero(initial.acceptance)) == 0,
        "zero_amount": int(torch.count_nonzero(initial.amount)) == 0,
        "selector_gradient_sum": selector_gradient,
        "source_has_gradient": source_has_gradient,
        "sources_unchanged_after_optimizer_step": frozen_before == frozen_after,
        "gate_formula_max_abs": gate_error,
        "positive_labels": int(labels.positive_mask.sum()),
        "negative_labels": int(labels.negative_mask.sum()),
        "finite_output": bool(torch.isfinite(trained.output).all()),
    }
    report["pass"] = bool(
        report["zero_selector_output_exactly_e20"]
        and report["zero_selector_output_exactly_base"]
        and report["zero_acceptance"]
        and report["zero_amount"]
        and selector_gradient > 0
        and not source_has_gradient
        and frozen_before == frozen_after
        and gate_error == 0.0
        and report["finite_output"]
        and counts["e20_trainable"] == 0
        and counts["e24_trainable"] == 0
    )
    output = PROBE_ROOT / "smoke_results" / f"{selected.type}_smoke.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    print(json.dumps(run(parser.parse_args().device), indent=2))

