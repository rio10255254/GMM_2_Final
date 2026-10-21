from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from scipy.stats import rankdata, spearmanr


ROOT = Path(__file__).resolve().parents[1]
RUN_PROBE = ROOT / "scripts" / "run_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r105b_probe_admission", RUN_PROBE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {RUN_PROBE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_model(module, device):
    steps = int(module.CONFIG["training"]["steps"])
    checkpoint = torch.load(
        ROOT / "weights" / f"evidence_step{steps:04d}.pth",
        map_location=device,
        weights_only=False,
    )
    model = module.EvidenceSetNet().to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


OBSERVATION_FIELDS = ["raw", "aligned", "illumination", "sigma_index", "dx", "dy", "exposure"]


def mismatch_batch(batch):
    result = {key: value.clone() for key, value in batch.items()}
    for observation in range(1, result["raw"].shape[1]):
        for name in OBSERVATION_FIELDS:
            result[name][:, observation] = torch.roll(result[name][:, observation], shifts=observation, dims=0)
    return result


def observation_to_front(batch, observation):
    result = {key: value.clone() for key, value in batch.items()}
    if observation == 0:
        return result
    for name in OBSERVATION_FIELDS:
        first = result[name][:, 0].clone()
        result[name][:, 0] = result[name][:, observation]
        result[name][:, observation] = first
    return result


def normalized_structure(frame):
    smooth = cv2.GaussianBlur(frame.astype(np.float32), (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    local = smooth - cv2.GaussianBlur(smooth, (0, 0), 4.0, borderType=cv2.BORDER_REFLECT_101)
    crop = local[8:-8, 8:-8]
    crop = crop - float(crop.mean())
    norm = float(np.sqrt(np.sum(crop * crop)))
    return crop.reshape(-1) / max(norm, 1e-8)


def compatibility_scores(aligned):
    scores = []
    for bundle in aligned:
        signatures = [normalized_structure(frame) for frame in bundle]
        correlations = [float(np.dot(signatures[0], signatures[index])) for index in range(1, len(signatures))]
        scores.append(float(np.median(correlations)))
    return np.asarray(scores, dtype=np.float64)


def mismatch_numpy(aligned):
    value = aligned.copy()
    for observation in range(1, value.shape[1]):
        value[:, observation] = np.roll(value[:, observation], shift=observation, axis=0)
    return value


def choose_threshold(valid, mismatched):
    candidates = np.unique(np.concatenate([valid, mismatched]))
    best = None
    for threshold in candidates:
        true_positive = float(np.mean(valid >= threshold))
        true_negative = float(np.mean(mismatched < threshold))
        balanced = 0.5 * (true_positive + true_negative)
        value = (balanced, true_positive, true_negative, float(threshold))
        if best is None or value > best:
            best = value
    assert best is not None
    return {
        "threshold": best[3],
        "balanced_accuracy": best[0],
        "valid_acceptance": best[1],
        "mismatch_rejection": best[2],
    }


def auc_from_scores(valid, mismatched):
    values = np.concatenate([valid, mismatched])
    ranks = rankdata(values)
    n_pos, n_neg = len(valid), len(mismatched)
    rank_sum = float(ranks[:n_pos].sum())
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


@torch.inference_mode()
def inference_bundle(module, model, population, device, mismatch=False):
    multi_outputs, single_outputs, candidate_uncertainty = [], [], []
    per_observation_outputs = [[] for _ in range(int(module.CONFIG["data"]["observations"]))]
    batch_size = int(module.CONFIG["training"]["batch_size"])
    for start in range(0, population.target.shape[0], batch_size):
        indices = np.arange(start, min(population.target.shape[0], start + batch_size))
        batch = population.batch(indices, device)
        if mismatch:
            batch = mismatch_batch(batch)
        multi = module.infer_batch(model, batch, 4)
        single = module.infer_batch(model, batch, 1)
        multi_outputs.append(multi["output"].cpu().numpy()[:, 0])
        single_outputs.append(single["output"].cpu().numpy()[:, 0])
        candidate_uncertainty.append(multi["uncertainty"].cpu().numpy()[:, 0])
        for observation in range(4):
            selected = observation_to_front(batch, observation)
            output = module.infer_batch(model, selected, 1)["output"]
            per_observation_outputs[observation].append(output.cpu().numpy()[:, 0])
    multi_output = np.concatenate(multi_outputs)
    single_output = np.concatenate(single_outputs)
    candidate_uncertainty = np.concatenate(candidate_uncertainty)
    observation_outputs = np.stack([np.concatenate(values) for values in per_observation_outputs], axis=1)
    jackknife = observation_outputs.std(axis=1)
    return {
        "multi": multi_output,
        "single": single_output,
        "candidate_uncertainty": candidate_uncertainty,
        "jackknife_uncertainty": jackknife,
    }


def uncertainty_metrics(output, uncertainty, population):
    target = population.target.numpy()[:, 0]
    predicted = uncertainty.mean(axis=(1, 2))
    error = np.abs(output - target).mean(axis=(1, 2))
    correlation = spearmanr(predicted, error).statistic
    return {
        "median_gray": float(np.median(predicted) * 255.0),
        "p95_gray": float(np.percentile(predicted, 95) * 255.0),
        "spearman_vs_image_mae": float(correlation if np.isfinite(correlation) else 0.0),
    }


def main() -> int:
    module = load_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(module, device)
    validation = module.build_population(int(module.CONFIG["data"]["validation_samples"]), "validation")
    test = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")

    val_aligned = validation.aligned.numpy()
    val_valid_scores = compatibility_scores(val_aligned)
    val_mismatch_scores = compatibility_scores(mismatch_numpy(val_aligned))
    threshold = choose_threshold(val_valid_scores, val_mismatch_scores)

    test_aligned = test.aligned.numpy()
    test_valid_scores = compatibility_scores(test_aligned)
    test_mismatch_scores = compatibility_scores(mismatch_numpy(test_aligned))
    valid_inference = inference_bundle(module, model, test, device, mismatch=False)
    mismatch_inference = inference_bundle(module, model, test, device, mismatch=True)

    valid_accept = test_valid_scores >= threshold["threshold"]
    mismatch_accept = test_mismatch_scores >= threshold["threshold"]
    admitted_valid = np.where(
        valid_accept[:, None, None],
        valid_inference["multi"],
        valid_inference["single"],
    )
    admitted_mismatch = np.where(
        mismatch_accept[:, None, None],
        mismatch_inference["multi"],
        mismatch_inference["single"],
    )
    outputs = {
        "valid_multi": valid_inference["multi"],
        "valid_admission_fallback": admitted_valid,
        "mismatched_multi_unprotected": mismatch_inference["multi"],
        "mismatched_admission_fallback": admitted_mismatch,
        "single_fallback_reference": valid_inference["single"],
    }
    decomposition = module.summarize_outputs(outputs, test)
    uncertainty = {
        "valid_candidate_disagreement": uncertainty_metrics(
            valid_inference["multi"], valid_inference["candidate_uncertainty"], test
        ),
        "valid_observation_jackknife": uncertainty_metrics(
            valid_inference["multi"], valid_inference["jackknife_uncertainty"], test
        ),
        "mismatched_candidate_disagreement": uncertainty_metrics(
            mismatch_inference["multi"], mismatch_inference["candidate_uncertainty"], test
        ),
        "mismatched_observation_jackknife": uncertainty_metrics(
            mismatch_inference["multi"], mismatch_inference["jackknife_uncertainty"], test
        ),
    }
    compatibility = {
        "validation_threshold_selection": threshold,
        "test_auc": float(auc_from_scores(test_valid_scores, test_mismatch_scores)),
        "test_valid_acceptance": float(valid_accept.mean()),
        "test_mismatch_rejection": float((~mismatch_accept).mean()),
        "test_valid_score_median": float(np.median(test_valid_scores)),
        "test_mismatch_score_median": float(np.median(test_mismatch_scores)),
    }
    decision = {
        "compatibility_generalizes": compatibility["test_auc"] > 0.95,
        "admission_prevents_catastrophic_mismatch": (
            decomposition["mismatched_admission_fallback"]["summary"]["boundary_distance_px"]
            < decomposition["mismatched_multi_unprotected"]["summary"]["boundary_distance_px"] * 0.25
        ),
        "jackknife_detects_mismatch": (
            uncertainty["mismatched_observation_jackknife"]["median_gray"]
            > uncertainty["valid_observation_jackknife"]["median_gray"] * 1.5
        ),
        "jackknife_correlates_on_valid": uncertainty["valid_observation_jackknife"]["spearman_vs_image_mae"] > 0.20,
    }
    result = {
        "status": "complete",
        "compatibility": compatibility,
        "uncertainty": uncertainty,
        "decomposition": decomposition,
        "decision": decision,
    }
    (ROOT / "results" / "admission_uncertainty.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = []
    for name, payload in decomposition.items():
        value = payload["summary"]
        rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['transition_center_error_px']:.4f} | {value['mean_abs_error_gray']:.3f} |"
        )
    report = "\n".join(
        [
            "# R105B Admission and Observation-Jackknife Results",
            "",
            "| Output | IoU | Boundary px | Transition center px | MAE gray |",
            "|---|---:|---:|---:|---:|",
            *rows,
            "",
            "## Compatibility",
            "",
            "```json",
            json.dumps(compatibility, indent=2),
            "```",
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
    (ROOT / "reports" / "R105B_ADMISSION_UNCERTAINTY.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": decision, "compatibility": compatibility}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
