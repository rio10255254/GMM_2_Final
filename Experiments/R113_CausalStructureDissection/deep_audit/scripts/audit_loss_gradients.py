"""Measure actual R109 loss routing, gradient magnitudes, and conflicts."""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(PROJECT_ROOT / CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "loss_gradients"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R109 / "model"))
sys.path.insert(0, str(R109 / "training"))
from r109_model import build_model
from r109_dataset import R109Dataset
from losses import detector_components, renderer_components
import train as training_module


DEVICE = torch.device("cpu")
torch.set_num_threads(min(8, max(1, torch.get_num_threads())))
R109_CONFIG = json.loads((R109 / "config" / "experiment.json").read_text(encoding="utf-8"))
WEIGHTS = {key: float(value) for key, value in R109_CONFIG["training"]["renderer_loss_weights"].items()}
FREQUENCIES = {
    "translation": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["translation_every_steps"]),
    "exposure": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["exposure_every_steps"]),
    "tile": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["tile_every_steps"]),
}


def choose_records() -> dict[str, list[tuple[int, int]]]:
    datasets = {epoch: R109Dataset("validation", epoch=epoch) for epoch in range(6)}
    desired = ["standard", "low_contrast", "uneven_illumination", "asymmetric_blur_halo", "boundary_fade", "mixed_hard"]
    selected: dict[str, list[tuple[int, int]]] = {name: [] for name in desired}
    selected["identity_role"] = []
    selected["flat_negative"] = []
    for epoch, dataset in datasets.items():
        for index, record in enumerate(dataset.records):
            role = str(record["role"])
            if role == "identity" and len(selected["identity_role"]) < 2:
                selected["identity_role"].append((epoch, index))
            elif role == "flat_negative" and len(selected["flat_negative"]) < 2:
                selected["flat_negative"].append((epoch, index))
            elif role in {"edge", "textured_edge"}:
                challenge = str(dataset[index]["challenge"])
                if challenge in selected and len(selected[challenge]) < 2:
                    selected[challenge].append((epoch, index))
        if all(len(value) >= 2 for value in selected.values()):
            break
    if not all(len(value) == 2 for value in selected.values()):
        raise RuntimeError(f"Could not build gradient strata: {selected}")
    return selected


def flatten_items(pairs: list[tuple[int, int]], observation: str = "both") -> dict[str, torch.Tensor]:
    rows = []
    for epoch, index in pairs:
        item = R109Dataset("validation", epoch=epoch)[index]
        indices = (0, 1) if observation == "both" else ((0,) if observation == "degraded" else (1,))
        for observation_index in indices:
            rows.append({
                name: item[name][observation_index : observation_index + 1]
                for name in ("source", "target", "mask", "sdf", "edge", "identity", "midpoint", "polarity", "width_gain_target")
            })
    batch = {}
    for name in rows[0]:
        batch[name] = torch.cat([row[name] for row in rows], dim=0).to(DEVICE)
    return batch


def parameter_groups(model) -> dict[str, list[torch.nn.Parameter]]:
    return {
        "detector_backbone": [*model.detector_stem.parameters(), *model.detector_tower.parameters()],
        "boundary_head": list(model.boundary_head.parameters()),
        "renderer_backbone": [*model.renderer_stem.parameters(), *model.renderer_tower.parameters()],
        "width_head": list(model.width_head.parameters()),
        "shift_head": list(model.shift_head.parameters()),
    }


def gradient_vectors(value: torch.Tensor, groups: dict[str, list[torch.nn.Parameter]], retain_graph: bool) -> dict[str, torch.Tensor]:
    params = [parameter for values in groups.values() for parameter in values]
    gradients = torch.autograd.grad(value, params, retain_graph=retain_graph, allow_unused=True)
    result = {}
    offset = 0
    for name, values in groups.items():
        pieces = []
        for parameter, gradient in zip(values, gradients[offset : offset + len(values)]):
            pieces.append(torch.zeros_like(parameter).flatten() if gradient is None else gradient.detach().flatten())
        result[name] = torch.cat(pieces) if pieces else torch.zeros(1)
        offset += len(values)
    return result


def loss_components(model, batch: dict, include_auxiliary: bool) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    details = model.forward_details(batch["source"])
    detector = detector_components(details, batch["source"], batch["target"], batch["edge"], batch["identity"])
    renderer = renderer_components(
        details, batch["source"], batch["target"], batch["mask"], batch["edge"], batch["identity"],
        batch["midpoint"], batch["polarity"], batch["width_gain_target"],
    )
    if include_auxiliary:
        renderer["translation"] = training_module.translation_loss(model, batch["source"], details.output, 8)
        renderer["exposure"] = training_module.exposure_loss(model, batch["source"], details.output, 8)
        renderer["tile"] = training_module.tile_loss(model, batch["source"], details.output)
    return detector, renderer


def cosine(first: torch.Tensor, second: torch.Tensor) -> float:
    denominator = float(first.norm() * second.norm())
    return 0.0 if denominator <= 1e-20 else float(torch.dot(first, second) / denominator)


def pooled_conflicts(model, batch: dict, groups: dict[str, list[torch.nn.Parameter]]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    _detector, renderer = loss_components(model, batch, include_auxiliary=True)
    names = [name for name in renderer if name in WEIGHTS and WEIGHTS[name] > 0 and torch.isfinite(renderer[name])]
    vectors: dict[str, dict[str, torch.Tensor]] = {}
    values = {}
    for index, name in enumerate(names):
        weighted = renderer[name] * WEIGHTS[name]
        values[name] = float(renderer[name].detach())
        vectors[name] = gradient_vectors(weighted, groups, retain_graph=index < len(names) - 1)
    pair_rows = []
    for group_name in ("renderer_backbone", "width_head", "shift_head"):
        for left_index, left in enumerate(names):
            for right in names[left_index + 1 :]:
                pair_rows.append({"parameter_group": group_name, "loss_left": left, "loss_right": right, "cosine": cosine(vectors[left][group_name], vectors[right][group_name])})
    summary_rows = []
    totals = {}
    for group_name in groups:
        total = torch.zeros_like(next(iter(vectors.values()))[group_name])
        for name in names:
            frequency = FREQUENCIES.get(name, 1.0)
            total = total + frequency * vectors[name][group_name]
        totals[group_name] = total
        total_norm = float(total.norm())
        for name in names:
            frequency = FREQUENCIES.get(name, 1.0)
            vector = frequency * vectors[name][group_name]
            summary_rows.append({
                "parameter_group": group_name,
                "loss": name,
                "raw_loss_value": values[name],
                "configured_weight": WEIGHTS[name],
                "effective_frequency": frequency,
                "effective_gradient_norm": float(vector.norm()),
                "gradient_norm_over_total": float(vector.norm()) / max(total_norm, 1e-20),
                "alignment_with_expected_total": cosine(vector, total),
            })
    most_negative = sorted(pair_rows, key=lambda row: row["cosine"])[:15]
    return pd.DataFrame(summary_rows), pd.DataFrame(pair_rows), {"losses": names, "most_negative_pairs": most_negative}


def stratum_norms(model, selected: dict[str, list[tuple[int, int]]], groups: dict[str, list[torch.nn.Parameter]]) -> pd.DataFrame:
    rows = []
    for stratum, pairs in selected.items():
        batch = flatten_items(pairs[:1], "both")
        detector, renderer = loss_components(model, batch, include_auxiliary=False)
        components = {f"detector_{name}": value for name, value in detector.items() if torch.isfinite(value)}
        components.update({name: value for name, value in renderer.items() if torch.isfinite(value) and name in WEIGHTS and WEIGHTS[name] > 0})
        keep = {"detector_boundary_bce", "detector_boundary_dice", "contour", "direct", "gradient", "identity", "width_target"}
        names = [name for name in components if name in keep]
        for index, name in enumerate(names):
            if name == "detector_boundary_bce":
                weighted = .55 * components[name]
            elif name == "detector_boundary_dice":
                weighted = .45 * components[name]
            elif name.startswith("detector_"):
                continue
            else:
                weighted = WEIGHTS[name] * components[name]
            vectors = gradient_vectors(weighted, groups, retain_graph=index < len(names) - 1)
            for group_name, vector in vectors.items():
                rows.append({
                    "stratum": stratum,
                    "loss": name,
                    "parameter_group": group_name,
                    "loss_value": float(components[name].detach()),
                    "weighted_gradient_norm": float(vector.norm()),
                })
    return pd.DataFrame(rows)


def clear_degraded_comparison(model, selected: dict[str, list[tuple[int, int]]], groups: dict[str, list[torch.nn.Parameter]]) -> pd.DataFrame:
    rows = []
    renderer_groups = {name: groups[name] for name in ("renderer_backbone", "width_head", "shift_head")}
    pairs = [selected["mixed_hard"][0], selected["boundary_fade"][0], selected["standard"][0]]
    for observation in ("degraded", "clear"):
        batch = flatten_items(pairs, observation)
        _detector, renderer = loss_components(model, batch, include_auxiliary=False)
        names = ["direct", "reconstruction", "gradient"]
        for index, name in enumerate(names):
            vector = gradient_vectors(WEIGHTS[name] * renderer[name], renderer_groups, retain_graph=index < len(names) - 1)
            for group_name, value in vector.items():
                rows.append({"observation": observation, "loss": name, "parameter_group": group_name, "weighted_gradient_norm": float(value.norm()), "loss_value": float(renderer[name].detach())})
    return pd.DataFrame(rows)


def detector_constant_analysis(model, batch: dict) -> dict[str, object]:
    with torch.no_grad():
        details = model.forward_details(batch["source"])
        boundary = torch.nn.functional.max_pool2d(batch["edge"], 5, 1, 2).clamp(0, 1)
        fraction = float(boundary.mean())
        positive = (1 - boundary.mean()) / boundary.mean().clamp_min(1e-4)
        candidates = {}
        for probability in (.1, .25, .5, .75, .9):
            logit = math.log(probability / (1 - probability))
            logits = torch.full_like(boundary, logit)
            bce = torch.nn.functional.binary_cross_entropy_with_logits(logits, boundary, pos_weight=positive)
            candidates[str(probability)] = float(bce)
        prediction = details.boundary
        return {
            "boundary_target_mean": fraction,
            "balanced_pos_weight": float(positive),
            "actual_boundary_mean": float(prediction.mean()),
            "actual_boundary_spatial_std": float(prediction.flatten(1).std(dim=1).mean()),
            "actual_boundary_p05": float(torch.quantile(prediction, .05)),
            "actual_boundary_p95": float(torch.quantile(prediction, .95)),
            "constant_probability_bce": candidates,
        }


def main() -> int:
    torch.manual_seed(113900)
    selected = choose_records()
    model = build_model().to(DEVICE)
    payload = torch.load(Path(PROJECT_ROOT / CONFIG["sources"]["r109_checkpoint"]), map_location=DEVICE, weights_only=False)
    model.load_state_dict(payload["model"])
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    groups = parameter_groups(model)
    pooled_pairs = [values[0] for values in selected.values()]
    pooled = flatten_items(pooled_pairs, "both")
    pooled_summary_path = OUTPUT / "pooled_loss_gradient_summary.csv"
    pooled_pairwise_path = OUTPUT / "pooled_pairwise_gradient_cosines.csv"
    if pooled_summary_path.is_file() and pooled_pairwise_path.is_file():
        gradient_summary = pd.read_csv(pooled_summary_path)
        pairwise = pd.read_csv(pooled_pairwise_path)
        conflict_summary = {
            "losses": sorted(pd.concat([pairwise.loss_left, pairwise.loss_right], ignore_index=True).unique().tolist()),
            "most_negative_pairs": pairwise.sort_values("cosine").head(15).to_dict(orient="records"),
            "pooled_results_reused_after_complete_write": True,
        }
    else:
        gradient_summary, pairwise, conflict_summary = pooled_conflicts(model, pooled, groups)
        gradient_summary.to_csv(pooled_summary_path, index=False, encoding="utf-8-sig")
        pairwise.to_csv(pooled_pairwise_path, index=False, encoding="utf-8-sig")
    representative = {name: selected[name] for name in ("standard", "mixed_hard", "identity_role", "flat_negative")}
    strata = stratum_norms(model, representative, groups)
    strata.to_csv(OUTPUT / "stratum_gradient_norms.csv", index=False, encoding="utf-8-sig")
    clear_degraded = clear_degraded_comparison(model, selected, groups)
    clear_degraded.to_csv(OUTPUT / "clear_vs_degraded_gradients.csv", index=False, encoding="utf-8-sig")
    detector = detector_constant_analysis(model, pooled)

    identity_fraction = 0.5 + 0.5 * (515 / 5512)
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "checkpoint_epoch": 48,
        "device": str(DEVICE),
        "selected_records": {name: [{"epoch": epoch, "index": index} for epoch, index in values] for name, values in selected.items()},
        "effective_clear_identity_fraction": identity_fraction,
        "detector_frozen_during_renderer_epochs": True,
        "detector_constant_analysis": detector,
        "gradient_conflicts": conflict_summary,
        "top_expected_gradient_routes": gradient_summary.sort_values(["parameter_group", "effective_gradient_norm"], ascending=[True, False]).groupby("parameter_group").head(5).to_dict(orient="records"),
        "clear_vs_degraded": clear_degraded.to_dict(orient="records"),
        "interpretation_boundary": "Gradient-frequency scaling approximates long-run expected contribution; optimizer moments, clipping and changing batches make it diagnostic rather than an exact attribution of final weights.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
