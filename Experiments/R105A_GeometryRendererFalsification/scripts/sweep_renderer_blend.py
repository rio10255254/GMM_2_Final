from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_PATH = ROOT / "scripts" / "run_all.py"


def load_probe_module():
    spec = importlib.util.spec_from_file_location("r105a_run_all_blend", RUN_ALL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {RUN_ALL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_model(module, mode: str, device: torch.device):
    steps = int(module.CONFIG["training"]["steps"])
    checkpoint = torch.load(
        ROOT / "weights" / f"{mode}_step{steps:04d}.pth",
        map_location=device,
        weights_only=False,
    )
    model = module.ProbeModel(mode).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


def score_directions(candidate: dict[str, float], baseline: dict[str, float]) -> dict[str, bool]:
    return {
        "boundary_distance": candidate["boundary_distance_px"] < baseline["boundary_distance_px"],
        "centroid_error": candidate["centroid_error_px"] < baseline["centroid_error_px"],
        "transition_center": candidate["transition_center_error_px"] < baseline["transition_center_error_px"],
        "transition_width": candidate["transition_width_error_px"] < baseline["transition_width_error_px"],
        "halo": candidate["halo_overshoot_fraction"] <= baseline["halo_overshoot_fraction"],
        "identity": candidate["identity_mae_gray"] <= baseline["identity_mae_gray"],
    }


def evaluate_split(module, renderer, residual, population, device, alphas):
    outputs = module.predict_population(renderer, residual, population, device)
    source = population.source.numpy()[:, 0]
    direct = outputs["full_learned_renderer"]
    baseline_summary = module.summarize_outputs(
        {"matched_residual": outputs["matched_residual"]}, population
    )["matched_residual"]["summary"]
    anchors = {
        "source_anchor": source,
        "residual_anchor": outputs["matched_residual"],
    }
    result = {"baseline": baseline_summary}
    for anchor_name, anchor in anchors.items():
        rows = []
        for alpha in alphas:
            blended = np.clip(anchor + alpha * (direct - anchor), 0.0, 1.0)
            metrics = module.summarize_outputs({"candidate": blended}, population)["candidate"]["summary"]
            directions = score_directions(metrics, baseline_summary)
            core_wins = sum(
                int(directions[key])
                for key in [
                    "boundary_distance",
                    "centroid_error",
                    "transition_center",
                    "transition_width",
                    "halo",
                ]
            )
            eligible = core_wins >= 4 and directions["transition_center"] and directions["halo"]
            rows.append(
                {
                    "alpha": float(alpha),
                    "metrics": metrics,
                    "directions": directions,
                    "core_wins": core_wins,
                    "eligible": bool(eligible),
                }
            )
        result[anchor_name] = rows
    return result


def render_table(rows):
    lines = [
        "| Blend | IoU | Boundary px | Centroid px | Center px | Width px | Halo | Identity gray | Wins | Eligible |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in rows:
        m = row["metrics"]
        lines.append(
            f"| {row['alpha']:.3f} | {m['iou']:.5f} | {m['boundary_distance_px']:.4f} | "
            f"{m['centroid_error_px']:.4f} | {m['transition_center_error_px']:.4f} | "
            f"{m['transition_width_error_px']:.4f} | {m['halo_overshoot_fraction']:.5f} | "
            f"{m['identity_mae_gray']:.3f} | {row['core_wins']} | {'yes' if row['eligible'] else 'no'} |"
        )
    return lines


def main() -> int:
    module = load_probe_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    renderer = load_model(module, "renderer", device)
    residual = load_model(module, "residual", device)
    validation = module.build_population(int(module.CONFIG["data"]["validation_samples"]), "validation")
    test = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")
    alphas = np.round(np.linspace(0.0, 1.0, 41), 3)
    validation_result = evaluate_split(module, renderer, residual, validation, device, alphas)
    test_result = evaluate_split(module, renderer, residual, test, device, alphas)

    eligibility = {}
    for anchor_name in ["source_anchor", "residual_anchor"]:
        eligibility[anchor_name] = {
            "validation": [row["alpha"] for row in validation_result[anchor_name] if row["eligible"]],
            "heldout_test": [row["alpha"] for row in test_result[anchor_name] if row["eligible"]],
        }
    rescued_anchors = [
        name
        for name, value in eligibility.items()
        if value["validation"] and value["heldout_test"]
    ]
    result = {
        "status": "complete",
        "alphas": [float(value) for value in alphas],
        "validation": validation_result,
        "heldout_test": test_result,
        "decision": {
            "eligibility": eligibility,
            "rescued_anchors": rescued_anchors,
            "fixed_blend_rescues_renderer": bool(rescued_anchors),
        },
    }
    results_dir = ROOT / "results"
    reports_dir = ROOT / "reports"
    results_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "renderer_blend_sweep.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = [
        "# R105A Fixed Renderer Blend Sweep",
        "",
        "A fixed blend is considered eligible only if it wins at least four of five core directions and also wins transition-center and halo.",
        "",
        f"Fixed blend rescues renderer: {'yes' if result['decision']['fixed_blend_rescues_renderer'] else 'no'}",
        "",
    ]
    for anchor_name in ["source_anchor", "residual_anchor"]:
        report.extend(
            [
                f"## {anchor_name}",
                "",
                f"Validation eligible blends: {eligibility[anchor_name]['validation'] or 'none'}",
                "",
                f"Held-out eligible blends: {eligibility[anchor_name]['heldout_test'] or 'none'}",
                "",
                "### Validation",
                "",
                *render_table(validation_result[anchor_name]),
                "",
                "### Held-out geometry",
                "",
                *render_table(test_result[anchor_name]),
                "",
            ]
        )
    (reports_dir / "R105A_BLEND_SWEEP.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(result["decision"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
