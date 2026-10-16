from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
RUN_PROBE = ROOT / "scripts" / "run_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r105b_probe_count_alignment", RUN_PROBE)
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


def normalized_structure(frame):
    smooth = cv2.GaussianBlur(frame.astype(np.float32), (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    local = smooth - cv2.GaussianBlur(smooth, (0, 0), 4.0, borderType=cv2.BORDER_REFLECT_101)
    crop = local[8:-8, 8:-8]
    crop -= float(crop.mean())
    return crop.reshape(-1) / max(float(np.sqrt(np.sum(crop * crop))), 1e-8)


def compatibility(bundle):
    signatures = [normalized_structure(frame) for frame in bundle]
    return float(np.median([np.dot(signatures[0], signatures[index]) for index in range(1, len(signatures))]))


def add_alignment_error(module, batch, amplitude):
    result = {key: value.clone() for key, value in batch.items()}
    aligned = result["aligned"].cpu().numpy()
    directions = [0.0, 0.35 * math.pi, 1.05 * math.pi, 1.70 * math.pi]
    for observation in range(1, aligned.shape[1]):
        error_dx = amplitude * math.cos(directions[observation])
        error_dy = amplitude * math.sin(directions[observation])
        for index in range(aligned.shape[0]):
            aligned[index, observation] = module.warp_np(aligned[index, observation], -error_dx, -error_dy)
        result["dx"][:, observation] += error_dx
        result["dy"][:, observation] += error_dy
    result["aligned"] = torch.from_numpy(aligned).to(batch["aligned"].device)
    return result


@torch.inference_mode()
def predict_alignment(module, model, population, device, amplitude):
    outputs, scores = [], []
    batch_size = int(module.CONFIG["training"]["batch_size"])
    for start in range(0, population.target.shape[0], batch_size):
        indices = np.arange(start, min(population.target.shape[0], start + batch_size))
        batch = population.batch(indices, device)
        changed = add_alignment_error(module, batch, amplitude)
        details = module.infer_batch(model, changed, 4)
        outputs.append(details["output"].cpu().numpy()[:, 0])
        scores.extend([compatibility(bundle) for bundle in changed["aligned"].cpu().numpy()])
    return np.concatenate(outputs), np.asarray(scores)


def main() -> int:
    module = load_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(module, device)
    test = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")
    count_outputs = {}
    for used in [1, 2, 4]:
        count_outputs[f"evidence_n{used}"] = module.predict_population(model, test, used, device)["output"]
    count_summary = module.summarize_outputs(count_outputs, test)

    admission = json.loads((ROOT / "results" / "admission_uncertainty.json").read_text(encoding="utf-8"))
    threshold = float(admission["compatibility"]["validation_threshold_selection"]["threshold"])
    amplitudes = [0.0, 0.15, 0.30, 0.50, 0.75, 1.00, 1.50]
    alignment_outputs = {}
    acceptance = {}
    for amplitude in amplitudes:
        output, scores = predict_alignment(module, model, test, device, amplitude)
        name = f"residual_alignment_{amplitude:.2f}px"
        alignment_outputs[name] = output
        acceptance[name] = {
            "acceptance_fraction": float(np.mean(scores >= threshold)),
            "compatibility_median": float(np.median(scores)),
            "compatibility_p05": float(np.percentile(scores, 5)),
        }
    alignment_summary = module.summarize_outputs(alignment_outputs, test)
    single_boundary = count_summary["evidence_n1"]["summary"]["boundary_distance_px"]
    tolerance = []
    for name, payload in alignment_summary.items():
        amplitude = float(name.split("_")[-1].replace("px", ""))
        if payload["summary"]["boundary_distance_px"] < single_boundary:
            tolerance.append(amplitude)
    result = {
        "status": "complete",
        "observation_count": count_summary,
        "alignment": alignment_summary,
        "compatibility_acceptance": acceptance,
        "decision": {
            "best_observation_count": min(
                [1, 2, 4],
                key=lambda used: count_summary[f"evidence_n{used}"]["summary"]["boundary_distance_px"],
            ),
            "largest_tested_alignment_error_still_better_than_single_px": max(tolerance) if tolerance else 0.0,
        },
    }
    (ROOT / "results" / "count_alignment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    count_rows = []
    for name, payload in count_summary.items():
        value = payload["summary"]
        count_rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['transition_center_error_px']:.4f} | {value['mean_abs_error_gray']:.3f} |"
        )
    alignment_rows = []
    for name, payload in alignment_summary.items():
        value = payload["summary"]
        alignment_rows.append(
            f"| {name} | {value['iou']:.5f} | {value['boundary_distance_px']:.4f} | "
            f"{value['transition_center_error_px']:.4f} | {value['mean_abs_error_gray']:.3f} | "
            f"{acceptance[name]['acceptance_fraction']:.3f} |"
        )
    report = "\n".join(
        [
            "# R105B Observation Count and Alignment Tolerance",
            "",
            "## Observation count",
            "",
            "| Mode | IoU | Boundary px | Transition center px | MAE gray |",
            "|---|---:|---:|---:|---:|",
            *count_rows,
            "",
            "## Residual alignment error",
            "",
            "| Error | IoU | Boundary px | Transition center px | MAE gray | Accepted |",
            "|---|---:|---:|---:|---:|---:|",
            *alignment_rows,
            "",
            "## Decision",
            "",
            "```json",
            json.dumps(result["decision"], indent=2),
            "```",
        ]
    )
    (ROOT / "reports" / "R105B_COUNT_ALIGNMENT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": result["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
