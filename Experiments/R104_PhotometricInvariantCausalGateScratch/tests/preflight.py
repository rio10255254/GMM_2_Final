"""Structural preflight for R104.  This does not start training."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data._utils.collate import default_collate


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "model", ROOT / "training"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from model.r104_model import build_model, count_parameters  # noqa: E402
from training.losses import loss_components, warp_tensor  # noqa: E402
from training.r104_dataset import R104Dataset  # noqa: E402
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def flatten_views(batch: dict[str, object], key: str) -> torch.Tensor:
    value = batch[key]
    assert isinstance(value, torch.Tensor)
    return value.reshape(value.shape[0] * value.shape[1], *value.shape[2:])


def main() -> None:
    started = time.perf_counter()
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / config["data"]["base_package"])
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    require(bool(audit["passed"]), "base data audit did not pass")
    require(audit["content_sha256"] == config["data"]["base_content_sha256"], "base data hash drift")
    require(not config["training"]["formal_training_authorized"], "preflight must not authorize training")
    mode_keys = set(config["data"]["online_mode_probabilities"])
    pair_keys = set(config["data"]["pair_type_probabilities"])
    for stage in config["training"]["curriculum"]:
        require(set(stage["online_mode_probabilities"]) == mode_keys, "curriculum mode keys drift")
        require(set(stage["pair_type_probabilities"]) == pair_keys, "curriculum pair keys drift")
        require(abs(sum(stage["online_mode_probabilities"].values()) - 1.0) < 1e-9, "mode probabilities do not sum to one")
        require(abs(sum(stage["pair_type_probabilities"].values()) - 1.0) < 1e-9, "pair probabilities do not sum to one")

    manifest_bytes = (package / "manifest.json").read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    dataset = R104Dataset("validation", 192, 0, validation_limit=30)
    samples = []
    coverage = set()
    generation_times = []
    for index in range(24):
        tick = time.perf_counter()
        sample = dataset[index]
        generation_times.append(time.perf_counter() - tick)
        samples.append(sample)
        coverage.add((int(sample["mode"]), int(sample["pair_type"])))
        for key in ("source", "target", "mask", "sdf", "illumination_target"):
            value = sample[key]
            require(tuple(value.shape) == (2, 1, 192, 192), f"unexpected {key} shape")
            require(bool(torch.isfinite(value).all()), f"non-finite {key}")
    require(len(coverage) == 24, "validation does not cover the full 6 x 4 matrix")
    train_dataset = R104Dataset("train", 192, 1)
    require(len(train_dataset) == 2500, "virtual training epoch is not 2,500 scene-pairs")
    repeated_a, repeated_b = train_dataset[0], train_dataset[1000]
    require(int(repeated_a["scene_index"]) == int(repeated_b["scene_index"]), "virtual repeat check selected different scenes")
    require(not torch.equal(repeated_a["source"], repeated_b["source"]), "repeated scene received duplicate augmentation")

    tile_sample = next(sample for sample in samples if int(sample["pair_type"]) == 3)
    motion = tile_sample["motion"]
    dx = motion[1:2, 0] - motion[0:1, 0]
    dy = motion[1:2, 1] - motion[0:1, 1]
    tile_alignment = {}
    crop = (..., slice(20, -20), slice(20, -20))
    for key in ("source", "target", "illumination_target"):
        value = tile_sample[key]
        aligned = warp_tensor(value[0:1], dx, dy)
        tile_alignment[key] = float((aligned[crop] - value[1:2][crop]).abs().mean())
        require(tile_alignment[key] < 1e-5, f"cross-tile {key} is not physically coherent")

    selected = [samples[index] for index in (0, 1, 2, 3, 4, 5, 6, 12, 18)]
    batch = default_collate(selected)
    batch_size, views = batch["source"].shape[:2]
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    model = build_model(base=int(config["model"]["base_channels"])).to(device)
    parameter_count = count_parameters(model)
    require(parameter_count <= int(config["model"]["target_parameter_ceiling"]), "parameter ceiling exceeded")

    source, target, mask, sdf, illumination = [
        flatten_views(batch, key).to(device)
        for key in ("source", "target", "mask", "sdf", "illumination_target")
    ]
    pair_motion = flatten_views(batch, "motion").to(device)
    identity = flatten_views(batch, "identity").to(device)
    mode = batch["mode"].repeat_interleave(views).to(device)
    pair_type = batch["pair_type"].repeat_interleave(views).to(device)

    details = model.forward_details(source)
    require(tuple(details.output.shape) == tuple(source.shape), "model changed spatial shape")
    require(bool(torch.isfinite(details.output).all()), "non-finite model output")
    initial_mean_change = float(details.total_delta.abs().mean())
    initial_max_change = float(details.total_delta.abs().max())
    require(initial_max_change < 1e-3, "fresh model is not safely near identity")
    contour_gate_mean = float(details.contour_gate.mean())
    texture_gate_mean = float(details.texture_gate.mean())
    low_gate_mean = float(details.low_gate.mean())
    illumination_gate_mean = float(details.illumination_gate.mean())
    expected_gate = 1.15 * float(config["model"]["gate_initial_probability"])
    require(abs(contour_gate_mean - expected_gate) < 1e-4, "contour gate initialization drift")
    require(abs(texture_gate_mean - expected_gate) < 1e-4, "texture gate initialization drift")
    require(abs(low_gate_mean - expected_gate) < 1e-4, "radiometry gate initialization drift")
    require(abs(illumination_gate_mean - expected_gate) < 1e-4, "illumination gate initialization drift")

    components = loss_components(
        details, source, target, mask, sdf, illumination, identity,
        mode, pair_type, pair_motion, core_size=128,
    )
    weights = config["training"]["loss_weights"]
    require(set(components) == set(weights), "configured and implemented objectives differ")
    require(all(bool(torch.isfinite(value)) for value in components.values()), "non-finite objective")
    contributions = {name: components[name] * float(weights[name]) for name in components}
    total = sum(contributions.values())
    require(bool(torch.isfinite(total)), "non-finite total objective")
    total.backward()

    groups = {
        "raw_backbone": ("e1", "d1", "e2", "d2", "e3", "d3", "mid", "u3", "p3", "u2", "p2", "u1", "p1"),
        "invariant_shape": ("invariant_body", "shape_body"),
        "proposals": ("proposal_fusion", "contour_body", "texture_body", "contour_head", "texture_head"),
        "true_gates": ("gate_context", "contour_gate_head", "texture_gate_head"),
        "signed_distance": ("sdf_body", "sdf_head"),
        "illumination": ("illumination_body", "illumination_head"),
        "radiometry": ("low_body", "low_head"),
    }
    gradient_norms = {}
    for group, tokens in groups.items():
        values = [
            float(parameter.grad.detach().norm())
            for name, parameter in model.named_parameters()
            if any(token in name for token in tokens) and parameter.grad is not None
        ]
        gradient_norms[group] = float(sum(values))
        require(values and gradient_norms[group] > 0.0, f"{group} receives no gradient")
    require(all(torch.isfinite(parameter.grad).all() for parameter in model.parameters() if parameter.grad is not None), "non-finite gradient")

    probe = torch.rand(2, 1, 192, 192, device=device) * 0.50 + 0.22
    with torch.no_grad():
        raw_a, invariant_a = model.cues(probe)
        raw_b, invariant_b = model.cues((0.65 * probe + 0.07).clamp(0.0, 1.0))
    raw_relative_change = float((raw_a - raw_b).abs().mean() / raw_a.abs().mean().clamp_min(1e-8))
    invariant_change = float((invariant_a - invariant_b).abs().mean())
    require(invariant_change < 0.015, "shape cues remain too exposure-dependent")
    require(invariant_change * 10.0 < raw_relative_change, "shape path is not materially more invariant")

    odd = torch.rand(1, 1, 191, 197, device=device)
    with torch.no_grad():
        odd_output = model(odd)
    require(tuple(odd_output.shape) == tuple(odd.shape), "automatic padding failed")

    total_value = float(total.detach())
    contribution_values = {name: float(value.detach()) for name, value in contributions.items()}
    largest_share = max(contribution_values.values()) / max(total_value, 1e-12)
    result = {
        "status": "passed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "formal_training_started": False,
        "base_data": {
            "audit_passed": True,
            "content_sha256": audit["content_sha256"],
            "manifest_sha256": manifest_sha256,
            "validation_matrix_coverage": len(coverage),
        },
        "data_generation_seconds": {
            "median": float(torch.tensor(generation_times).median()),
            "maximum": max(generation_times),
        },
        "tile_pair_alignment_mae": tile_alignment,
        "model": {
            "parameters": parameter_count,
            "parameter_ceiling": int(config["model"]["target_parameter_ceiling"]),
            "initial_mean_absolute_change": initial_mean_change,
            "initial_max_absolute_change": initial_max_change,
            "initial_contour_gate_mean": contour_gate_mean,
            "initial_texture_gate_mean": texture_gate_mean,
            "initial_radiometry_gate_mean": low_gate_mean,
            "initial_illumination_gate_mean": illumination_gate_mean,
            "raw_cue_relative_change": raw_relative_change,
            "invariant_cue_mean_absolute_change": invariant_change,
        },
        "objectives": {
            "total": total_value,
            "components": {name: float(value.detach()) for name, value in components.items()},
            "weighted_contributions": contribution_values,
            "largest_initial_contribution_share": largest_share,
            "gradient_group_norm_sums": gradient_norms,
        },
        "runtime": {
            "device": str(device),
            "cuda_peak_allocated_gib": (
                float(torch.cuda.max_memory_allocated() / 2**30) if device.type == "cuda" else 0.0
            ),
            "elapsed_seconds": time.perf_counter() - started,
        },
    }
    report = ROOT / "reports" / "design_preflight.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
