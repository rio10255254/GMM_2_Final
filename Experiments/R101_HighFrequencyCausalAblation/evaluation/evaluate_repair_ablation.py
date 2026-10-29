"""Compare the repaired D/E prototypes against the strongest initial arm A."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVAL = load_module("r101_repair_eval_base", ROOT / "evaluation" / "evaluate_short_ablation.py")
PROTOTYPES = load_module("r101_repair_eval_prototypes", ROOT / "model" / "prototype_models.py")
REPAIRS = load_module("r101_repair_eval_models", ROOT / "model" / "repaired_models.py")
DIAGNOSTICS = load_module("r101_repair_eval_diagnostics", ROOT / "analysis" / "diagnose_mechanisms.py")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_models(device: torch.device) -> dict[str, torch.nn.Module]:
    result = {}
    specifications = {
        "A": (PROTOTYPES.build_model("A", 16), ROOT / "weights" / "arm_A" / "latest.pth.tar"),
        "D": (REPAIRS.build_model("D", 16), ROOT / "weights" / "repair_arm_D" / "latest.pth.tar"),
        "E": (REPAIRS.build_model("E", 16), ROOT / "weights" / "repair_arm_E" / "latest.pth.tar"),
        "F": (REPAIRS.build_model("F", 16), ROOT / "weights" / "repair_arm_F" / "latest.pth.tar"),
        "G": (REPAIRS.build_model("G", 16), ROOT / "weights" / "repair_arm_G" / "latest.pth.tar"),
    }
    for arm, (model, path) in specifications.items():
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("arm") != arm or int(checkpoint.get("step", -1)) != 400:
            raise RuntimeError(f"Invalid checkpoint: {path}")
        model.load_state_dict(checkpoint["model"], strict=True)
        result[arm] = model.to(device).to(memory_format=torch.channels_last).eval()
    return result


def rename_proxy(value):
    mapping = {"A": "A", "B": "D", "C": "E"}
    if isinstance(value, dict):
        return {mapping.get(key, key): rename_proxy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rename_proxy(item) for item in value]
    return value


def synthetic(models: dict[str, torch.nn.Module], arrays: dict[str, np.ndarray], device: torch.device):
    proxy = {"A": models["A"], "B": models["D"], "C": models["E"]}
    aggregate, rows, _outputs = EVAL.synthetic_evaluation(proxy, arrays, device)
    for row in rows:
        row["arm"] = {"A": "A", "B": "D", "C": "E"}[row["arm"]]
    proxy_f = {"A": models["A"], "B": models["D"], "C": models["F"]}
    aggregate_f, rows_f, _outputs_f = EVAL.synthetic_evaluation(proxy_f, arrays, device)
    for row in rows_f:
        if row["arm"] == "C":
            row["arm"] = "F"
            rows.append(row)
    combined = rename_proxy(aggregate)
    combined["F"] = aggregate_f["C"]
    proxy_g = {"A": models["A"], "B": models["D"], "C": models["G"]}
    aggregate_g, rows_g, _outputs_g = EVAL.synthetic_evaluation(proxy_g, arrays, device)
    for row in rows_g:
        if row["arm"] == "C":
            row["arm"] = "G"
            rows.append(row)
    combined["G"] = aggregate_g["C"]
    return combined, rows


def real(models: dict[str, torch.nn.Module], directory: Path, device: torch.device):
    paths = sorted(path for path in directory.iterdir() if path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})
    per_arm = defaultdict(list)
    montage_rows = []
    for path in paths:
        raw = EVAL.read_gray(path)
        gx = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 0.8), cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(cv2.GaussianBlur(raw, (0, 0), 0.8), cv2.CV_32F, 0, 1, ksize=3)
        magnitude = np.sqrt(gx * gx + gy * gy)
        strong = magnitude >= np.quantile(magnitude, 0.90)
        outputs = {}
        for arm, model in models.items():
            output = EVAL.predict_array(model, raw[None], device, 1)[0]
            outputs[arm] = output
            per_arm[arm].append({
                "fine_ratio_to_raw": EVAL.fine_ratio(raw, output),
                "nonedge_fine_ratio_to_raw": EVAL.fine_ratio(raw, output, ~strong),
                "strong_edge_fine_ratio_to_raw": EVAL.fine_ratio(raw, output, strong),
                "mean_abs_change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
                "off_range_fraction": float(np.mean((output <= 1e-5) | (output >= 1.0 - 1e-5))),
            })
        montage_rows.append(np.concatenate([EVAL.labeled_panel(raw, f"{path.stem} Raw")] + [EVAL.labeled_panel(outputs[arm], f"Arm {arm}") for arm in models], axis=1))
    montage_name = "g_real_comparison.png" if set(models) == {"G"} else "repair_real_live_comparison.png"
    cv2.imwrite(str(ROOT / "results" / montage_name), np.concatenate(montage_rows, axis=0))
    return {arm: {**{metric: float(np.median([row[metric] for row in per_arm[arm]])) for metric in per_arm[arm][0]}, "image_count": len(per_arm[arm])} for arm in models}


def motion(models: dict[str, torch.nn.Module], directory: Path, device: torch.device):
    paths = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"})
    raw_images = [EVAL.read_gray(path) for path in paths]
    sequences = {"Raw": raw_images}
    for arm, model in models.items():
        sequences[arm] = [EVAL.predict_array(model, image[None], device, 1)[0] for image in raw_images]
    summary = {"status": "complete", "image_count": len(paths), "external_gmf_used": False, "method": "phase correlation on consecutive full frames"}
    for arm, images in sequences.items():
        steps, responses = [], []
        for left, right in zip(images[:-1], images[1:]):
            shift, response = cv2.phaseCorrelate(left, right)
            steps.append([float(shift[0]), float(shift[1])])
            responses.append(float(response))
        vectors = np.asarray(steps)
        magnitudes = np.linalg.norm(vectors, axis=1)
        summary[arm] = {
            "median_dx_px": float(np.median(vectors[:, 0])), "median_dy_px": float(np.median(vectors[:, 1])),
            "step_magnitude_median_px": float(np.median(magnitudes)), "step_magnitude_std_px": float(np.std(magnitudes, ddof=1)),
            "response_median": float(np.median(responses)), "steps": steps,
        }
    raw_vectors = np.asarray(summary["Raw"]["steps"])
    for arm in models:
        vectors = np.asarray(summary[arm]["steps"])
        summary[arm]["paired_vector_difference_from_raw_median_px"] = float(np.median(np.linalg.norm(vectors - raw_vectors, axis=1)))
    return summary


@torch.inference_mode()
def tile(models: dict[str, torch.nn.Module], image_path: Path, device: torch.device):
    raw = EVAL.read_gray(image_path)
    tensor = torch.from_numpy(raw)[None, None].to(device)
    result = {"image": str(image_path), "core_size": 128, "halo": 192}
    for arm, model in models.items():
        full = EVAL.RECONSTRUCT.reconstruct_full_reference(model, tensor, core_size=128, halo=192)
        tiled = EVAL.RECONSTRUCT.reconstruct_tensor(model, tensor, core_size=128, halo=192, tile_batch=1)
        difference = (full - tiled).abs().float()
        result[arm] = {"max_difference_gray": float(difference.max() * 255.0), "mean_difference_gray": float(difference.mean() * 255.0)}
    return result


def diagnostic(models: dict[str, torch.nn.Module], arrays: dict[str, np.ndarray], device: torch.device):
    indices = np.flatnonzero(arrays["split"] == 1)
    source = torch.from_numpy(np.asarray(arrays["source"][indices], np.float32))[:, None].to(device)
    target = torch.from_numpy(np.asarray(arrays["target"][indices], np.float32))[:, None].to(device)
    boundary = torch.from_numpy(np.asarray(arrays["boundary"][indices], np.float32))[:, None].to(device)
    return {arm: DIAGNOSTICS.checkpoint_stats(model, source, target, boundary) for arm, model in models.items()}


def plot_logs() -> str:
    figure, axes = plt.subplots(1, 4, figsize=(17, 4), dpi=160)
    for arm in ("D", "E", "F", "G"):
        path = ROOT / "runs" / "repair_seed101201" / f"arm_{arm}" / "training_log.csv"
        rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
        steps = np.asarray([int(row["step"]) for row in rows])
        for axis, metric in zip(axes, ("base_total", "branch_edge", "branch_material", "branch_highpass")):
            values = np.asarray([float(row[metric]) for row in rows])
            smooth = np.convolve(values, np.ones(15) / 15.0, mode="same")
            axis.plot(steps[7:-7], smooth[7:-7], label=arm)
            axis.set_title(metric)
            axis.grid(alpha=0.25)
    axes[0].legend()
    figure.tight_layout()
    path = ROOT / "results" / "repair_training_curves.png"
    figure.savefig(path)
    plt.close(figure)
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick-g", action="store_true")
    args = parser.parse_args()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    with np.load(ROOT / "data" / "continuous_pairs.npz") as loaded:
        arrays = {name: loaded[name] for name in loaded.files}
    models = load_models(device)
    live_dir = Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation'))
    motion_dir = Path(str(PROJECT_ROOT / '20260702_100MG_位移_50x/x_1um'))
    if args.quick_g:
        proxy = {"A": models["A"], "B": models["D"], "C": models["G"]}
        aggregate, rows, _outputs = EVAL.synthetic_evaluation(proxy, arrays, device)
        g_rows = []
        for row in rows:
            if row["arm"] == "C":
                row["arm"] = "G"
                g_rows.append(row)
        EVAL.save_rows(ROOT / "results" / "g_synthetic_per_sample.csv", [row for row in g_rows if "mae_gray" in row])
        EVAL.save_rows(ROOT / "results" / "g_synthetic_motion_pairs.csv", [row for row in g_rows if "step_error_px" in row])
        subset = {"G": models["G"]}
        result = {
            "status": "complete", "completed_at": datetime.now().isoformat(), "synthetic": {"G": aggregate["C"]},
            "identity_shortcut_diagnostic": diagnostic(subset, arrays, device), "real": real(subset, live_dir, device),
            "real_motion_sequence": motion(subset, motion_dir, device),
            "tile": tile(subset, sorted(live_dir.glob("*"))[0], device),
            "figure": str(ROOT / "results" / "g_real_comparison.png"),
        }
        write_json(ROOT / "results" / "g_capacity_summary.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    synthetic_summary, rows = synthetic(models, arrays, device)
    EVAL.save_rows(ROOT / "results" / "repair_synthetic_per_sample.csv", [row for row in rows if "mae_gray" in row])
    EVAL.save_rows(ROOT / "results" / "repair_synthetic_motion_pairs.csv", [row for row in rows if "step_error_px" in row])
    result = {
        "status": "complete", "completed_at": datetime.now().isoformat(),
        "comparison": "A baseline versus D/E repairs", "full_r101_training_started": False,
        "synthetic": synthetic_summary, "identity_shortcut_diagnostic": diagnostic(models, arrays, device),
        "real": real(models, live_dir, device), "real_motion_sequence": motion(models, motion_dir, device),
        "tile": tile(models, sorted(live_dir.glob("*"))[0], device),
        "figures": {"real": str(ROOT / "results" / "repair_real_live_comparison.png"), "training": plot_logs()},
        "limitations": ["400-step mechanism test, not a final generalization claim", "Internal phase correlation, not external GMF"],
    }
    write_json(ROOT / "results" / "repair_comparison_summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
