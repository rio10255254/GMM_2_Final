from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
RUN_PROBE = ROOT / "scripts" / "run_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r105b_probe_controls", RUN_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {RUN_PROBE}")
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
    model = module.EvidenceSetNet().to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


def duplicate_first(batch):
    result = {key: value.clone() for key, value in batch.items()}
    for name in ["raw", "aligned", "illumination", "sigma_index", "dx", "dy", "exposure"]:
        repeats = [1] * result[name].ndim
        repeats[1] = result[name].shape[1]
        result[name] = result[name][:, 0:1].repeat(*repeats)
    return result


def mismatch_observations(batch):
    result = {key: value.clone() for key, value in batch.items()}
    for observation in range(1, result["raw"].shape[1]):
        for name in ["raw", "aligned", "illumination", "sigma_index", "dx", "dy", "exposure"]:
            result[name][:, observation] = torch.roll(result[name][:, observation], shifts=observation, dims=0)
    return result


@torch.inference_mode()
def predict_custom(module, model, population, device, transform=None, used=4):
    outputs, uncertainty = [], []
    batch_size = int(module.CONFIG["training"]["batch_size"])
    for start in range(0, population.target.shape[0], batch_size):
        indices = np.arange(start, min(population.target.shape[0], start + batch_size))
        batch = population.batch(indices, device)
        if transform is not None:
            batch = transform(batch)
        details = module.infer_batch(model, batch, used)
        outputs.append(details["output"].cpu().numpy()[:, 0])
        uncertainty.append(details["uncertainty"].cpu().numpy()[:, 0])
    return np.concatenate(outputs), np.concatenate(uncertainty)


def uncertainty_summary(output, uncertainty, population):
    target = population.target.numpy()[:, 0]
    predicted = uncertainty.mean(axis=(1, 2))
    actual = np.abs(output - target).mean(axis=(1, 2))
    correlation = spearmanr(predicted, actual).statistic
    return {
        "median_gray": float(np.median(predicted) * 255.0),
        "p95_gray": float(np.percentile(predicted, 95) * 255.0),
        "spearman_vs_image_mae": float(correlation if np.isfinite(correlation) else 0.0),
    }


def main() -> int:
    module = load_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    test = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")
    point = load_model(module, "point", device)
    evidence = load_model(module, "evidence", device)

    evidence_diverse, uncertainty_diverse = predict_custom(module, evidence, test, device, used=4)
    evidence_duplicate, uncertainty_duplicate = predict_custom(
        module, evidence, test, device, transform=duplicate_first, used=4
    )
    evidence_mismatched, uncertainty_mismatched = predict_custom(
        module, evidence, test, device, transform=mismatch_observations, used=4
    )
    point_four, _ = predict_custom(module, point, test, device, used=4)
    aligned = test.aligned.numpy()
    raw_single = aligned[:, 0]
    raw_mean_four = aligned.mean(axis=1)
    target = test.target.numpy()[:, 0]
    per_frame_error = np.abs(aligned - target[:, None]).mean(axis=(2, 3))
    oracle_frame_index = per_frame_error.argmin(axis=1)
    raw_oracle_frame = aligned[np.arange(len(aligned)), oracle_frame_index]
    outputs = {
        "raw_single": raw_single,
        "raw_mean_four": raw_mean_four,
        "raw_oracle_frame": raw_oracle_frame,
        "matched_point_four_diagnostic": point_four,
        "evidence_four_duplicate_first": evidence_duplicate,
        "evidence_four_diverse": evidence_diverse,
        "evidence_four_mismatched": evidence_mismatched,
    }
    decomposition = module.summarize_outputs(outputs, test)
    uncertainty = {
        "diverse": uncertainty_summary(evidence_diverse, uncertainty_diverse, test),
        "duplicate_first": uncertainty_summary(evidence_duplicate, uncertainty_duplicate, test),
        "mismatched": uncertainty_summary(evidence_mismatched, uncertainty_mismatched, test),
    }
    diverse = decomposition["evidence_four_diverse"]["summary"]
    duplicate = decomposition["evidence_four_duplicate_first"]["summary"]
    mean_four = decomposition["raw_mean_four"]["summary"]
    decision = {
        "new_observations_beat_repeated_frame": {
            "boundary": diverse["boundary_distance_px"] < duplicate["boundary_distance_px"],
            "transition_center": diverse["transition_center_error_px"] < duplicate["transition_center_error_px"],
            "image_mae": diverse["mean_abs_error_gray"] < duplicate["mean_abs_error_gray"],
        },
        "model_beats_simple_average": {
            "boundary": diverse["boundary_distance_px"] < mean_four["boundary_distance_px"],
            "transition_center": diverse["transition_center_error_px"] < mean_four["transition_center_error_px"],
            "image_mae": diverse["mean_abs_error_gray"] < mean_four["mean_abs_error_gray"],
        },
        "uncertainty_detects_mismatch": uncertainty["mismatched"]["median_gray"] > uncertainty["diverse"]["median_gray"],
    }
    result = {
        "status": "complete",
        "decomposition": decomposition,
        "uncertainty": uncertainty,
        "decision": decision,
    }
    (ROOT / "results" / "evidence_controls.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = []
    for name, payload in decomposition.items():
        value = payload["summary"]
        rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['transition_center_error_px']:.4f} | {value['transition_width_error_px']:.4f} | "
            f"{value['mean_abs_error_gray']:.3f} |"
        )
    report = "\n".join(
        [
            "# R105B Evidence Controls",
            "",
            "| Control | IoU | Boundary px | Transition center px | Width px | MAE gray |",
            "|---|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Uncertainty",
            "",
            "```json",
            json.dumps(uncertainty, indent=2),
            "```",
            "",
            "## Decision",
            "",
            "```json",
            json.dumps(decision, indent=2),
            "```",
        ]
    )
    (ROOT / "reports" / "R105B_EVIDENCE_CONTROLS.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": decision}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
