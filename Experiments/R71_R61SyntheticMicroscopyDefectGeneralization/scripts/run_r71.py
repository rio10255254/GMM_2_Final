from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from skimage.metrics import structural_similarity
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
RECON_ROOT = RESULTS / "inference_runs"
REPORT = ROOT / "reports" / "R71_RESULTS_TW.md"

FAMILY_LABELS = {
    "lines_grid": "細線格網",
    "large_regions": "大區域邊界",
    "textures": "低對比紋理",
    "edge_defects": "邊緣缺損",
    "mixed_fields": "混合缺陷",
}
METHOD_LABELS = {"raw": "Raw", "combo": "COMBO", "r61": "R61v16"}
PRIMARY_METRICS = {
    "psnr_db": "higher",
    "ssim": "higher",
    "mae": "lower",
    "edge_f1_t2": "higher",
    "edge_band_mae": "lower",
    "highpass_corr": "higher",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_paths(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".bmp")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Cannot read image: {path}")
    return image


def family_map(manifest: dict) -> dict[str, str]:
    return {str(stage): str(family) for stage, family in manifest["micro_stage_families"].items()}


def audit_inputs() -> dict:
    data_root = Path(PROJECT_ROOT / CONFIG["data"]["profile_root"])
    data_manifest_path = Path(PROJECT_ROOT / CONFIG["data"]["manifest"])
    training_manifest_path = Path(PROJECT_ROOT / CONFIG["model"]["training_manifest"])
    training_root = Path(PROJECT_ROOT / CONFIG["model"]["training_profile_root"])
    checkpoint = Path(PROJECT_ROOT / CONFIG["model"]["checkpoint"])
    inference_script = Path(PROJECT_ROOT / CONFIG["inference"]["script"])
    psf_path = Path(PROJECT_ROOT / CONFIG["model"]["psf_fitted_path"])
    for path in (data_root, data_manifest_path, training_manifest_path, training_root, checkpoint, inference_script, psf_path):
        if not path.exists():
            raise FileNotFoundError(path)

    manifest = read_json(data_manifest_path)
    train_manifest = read_json(training_manifest_path)
    families = family_map(manifest)
    expected_total = int(CONFIG["data"]["expected_total"])
    expected_per = int(CONFIG["data"]["expected_per_family"])
    if int(manifest["total_pairs"]) != expected_total:
        raise RuntimeError(f"Expected {expected_total} pairs, found {manifest['total_pairs']}")
    if set(families.values()) != set(FAMILY_LABELS):
        raise RuntimeError(f"Unexpected feature families: {sorted(families.values())}")

    records: list[dict] = []
    test_files: list[Path] = []
    for stage, family in families.items():
        src_files = image_paths(data_root / "src" / stage)
        lbl_files = image_paths(data_root / "lbl" / stage)
        if len(src_files) != expected_per or len(lbl_files) != expected_per:
            raise RuntimeError(f"{stage}: expected {expected_per}, src={len(src_files)}, lbl={len(lbl_files)}")
        if [p.name for p in src_files] != [p.name for p in lbl_files]:
            raise RuntimeError(f"{stage}: source/label filenames differ")
        for src, lbl in zip(src_files, lbl_files):
            src_img, lbl_img = read_gray(src), read_gray(lbl)
            if src_img.shape != (512, 512) or lbl_img.shape != (512, 512):
                raise RuntimeError(f"{stage}/{src.name}: unexpected shape {src_img.shape}/{lbl_img.shape}")
            records.append({
                "stage": stage,
                "feature_family": family,
                "filename": src.name,
                "src": str(src),
                "lbl": str(lbl),
                "src_mean": float(src_img.mean()),
                "lbl_mean": float(lbl_img.mean()),
                "src_std": float(src_img.std()),
                "lbl_std": float(lbl_img.std()),
            })
            test_files.extend((src, lbl))

    forbidden = ("r40", "stage_29", "stage_30", "stage_31", "stage_32", "stage_33", "microscopy_feature")
    path_reference_hits = []
    for pair_index, pair in enumerate(train_manifest["pairs"]):
        searchable = " ".join(str(value).lower() for value in pair.values() if isinstance(value, str))
        if any(token in searchable for token in forbidden):
            path_reference_hits.append(pair_index)

    test_sizes = {p.stat().st_size for p in test_files}
    training_candidates: list[Path] = []
    for pair in train_manifest["pairs"]:
        for key in ("package_src", "package_lbl"):
            candidate = training_root / pair[key]
            if candidate.stat().st_size in test_sizes:
                training_candidates.append(candidate)
    test_hashes = {sha256(path) for path in test_files}
    training_hashes = {sha256(path) for path in training_candidates}
    overlap_hashes = sorted(test_hashes & training_hashes)
    if path_reference_hits or overlap_hashes:
        raise RuntimeError(
            f"Training overlap audit failed: path_hits={len(path_reference_hits)}, hash_hits={len(overlap_hashes)}"
        )

    audit = {
        "experiment_id": CONFIG["experiment_id"],
        "dataset_profile": manifest["profile"],
        "dataset_generator": "r40_micro_v1 with separately held-out indices 80-99",
        "total_images": len(records),
        "family_counts": dict(Counter(row["feature_family"] for row in records)),
        "image_shape": [512, 512],
        "source_label_names_match": True,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "r61_training_profile": train_manifest["profile"],
        "r61_training_total_pairs": int(train_manifest["total_pairs"]),
        "r61_training_role_counts": train_manifest["role_counts"],
        "training_path_reference_hits": len(path_reference_hits),
        "same_size_training_files_hashed": len(training_candidates),
        "test_files_hashed": len(test_files),
        "exact_content_overlap_hashes": len(overlap_hashes),
        "independent_of_r61_training": True,
        "records": records,
    }
    write_json(RESULTS / "input_audit.json", audit)
    return audit


def output_name(family: str) -> str:
    return f"r61v16_psfoff_micro_val_unseen_{family}"


def find_r61_output(stage: str, family: str) -> Path | None:
    candidates: list[Path] = []
    for run_dir in RECON_ROOT.glob(f"reconstruct_progress_best_tradeoff_in_{stage}_*"):
        candidate = run_dir / output_name(family)
        if candidate.is_dir():
            candidates.append(candidate)
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def validate_reconstruction_dir(path: Path, expected_names: list[str]) -> bool:
    if not path.is_dir():
        return False
    outputs = image_paths(path)
    if [p.name for p in outputs] != expected_names:
        return False
    return all(read_gray(p).shape == (512, 512) for p in outputs)


def reconstruct() -> dict:
    audit = read_json(RESULTS / "input_audit.json") if (RESULTS / "input_audit.json").exists() else audit_inputs()
    data_manifest = read_json(Path(PROJECT_ROOT / CONFIG["data"]["manifest"]))
    data_root = Path(PROJECT_ROOT / CONFIG["data"]["profile_root"])
    commands = []
    outputs = {}
    for stage, family in family_map(data_manifest).items():
        input_dir = data_root / "src" / stage
        gt_dir = data_root / "lbl" / stage
        expected_names = [p.name for p in image_paths(gt_dir)]
        existing = find_r61_output(stage, family)
        if existing is not None and validate_reconstruction_dir(existing, expected_names):
            outputs[family] = str(existing)
            continue
        command = [
            CONFIG["inference"]["python"],
            str(PROJECT_ROOT / CONFIG["inference"]["script"]),
            "--weights", str(PROJECT_ROOT / CONFIG["model"]["checkpoint"]),
            "--input-dir", str(input_dir),
            "--gt-dir", str(gt_dir),
            "--recon-root", str(RECON_ROOT),
            "--output-name", output_name(family),
            "--device", CONFIG["inference"]["device"],
            "--select-mode", "all",
            "--exts", CONFIG["inference"]["extension"],
            "--psf-fitted-path", str(PROJECT_ROOT / CONFIG["model"]["psf_fitted_path"]),
            "--no-psf-from-ckpt",
            "--weak-psf-disable",
            "--psf-deconv-reg", str(CONFIG["model"]["psf_deconv_reg"]),
            "--psf-phys-alpha", str(CONFIG["model"]["psf_phys_alpha"]),
        ]
        print("RUN:", subprocess.list2cmdline(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        created = find_r61_output(stage, family)
        if created is None or not validate_reconstruction_dir(created, expected_names):
            raise RuntimeError(f"R61 reconstruction incomplete for {stage}")
        commands.append(command)
        outputs[family] = str(created)

    manifest = {
        "model": CONFIG["model"]["name"],
        "checkpoint": audit["checkpoint"],
        "checkpoint_sha256": audit["checkpoint_sha256"],
        "locked_mode": {
            "psf_from_checkpoint": False,
            "weak_psf": False,
            "psf_deconv_reg": CONFIG["model"]["psf_deconv_reg"],
            "psf_phys_alpha": CONFIG["model"]["psf_phys_alpha"],
        },
        "reconstructed_images": sum(len(image_paths(Path(path))) for path in outputs.values()),
        "output_dirs": outputs,
        "commands_executed_this_run": commands,
    }
    write_json(RESULTS / "inference_manifest.json", manifest)
    return manifest


def to_float(image: np.ndarray) -> np.ndarray:
    return image.astype(np.float32) / 255.0


def psnr(pred: np.ndarray, truth: np.ndarray) -> float:
    mse = float(np.mean((to_float(pred) - to_float(truth)) ** 2))
    return 99.0 if mse <= 1e-12 else float(10.0 * np.log10(1.0 / mse))


def high_frequency_ratio(image: np.ndarray, cutoff: float = 0.28) -> float:
    data = to_float(image).astype(np.float64)
    data -= float(data.mean())
    power = np.abs(np.fft.fftshift(np.fft.fft2(data))) ** 2
    total = float(power.sum())
    if total <= 1e-12:
        return 0.0
    h, w = power.shape
    yy, xx = np.mgrid[0:h, 0:w]
    radius = np.sqrt(((yy - h / 2) / (h / 2)) ** 2 + ((xx - w / 2) / (w / 2)) ** 2)
    return float(power[radius >= cutoff].sum() / total)


def edge_energy(image: np.ndarray) -> float:
    data = to_float(image)
    gx = cv2.Sobel(data, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(data, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.sqrt(gx * gx + gy * gy).mean())


def tolerant_edge_scores_at(
    pred: np.ndarray,
    truth: np.ndarray,
    *,
    low: int,
    high: int,
    tolerance: int,
) -> tuple[float, float, float, np.ndarray, np.ndarray]:
    pred_edges = cv2.Canny(pred, low, high) > 0
    truth_edges = cv2.Canny(truth, low, high) > 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tolerance + 1, 2 * tolerance + 1))
    pred_dilated = cv2.dilate(pred_edges.astype(np.uint8), kernel) > 0
    truth_dilated = cv2.dilate(truth_edges.astype(np.uint8), kernel) > 0
    pred_count = int(pred_edges.sum())
    truth_count = int(truth_edges.sum())
    precision = float((pred_edges & truth_dilated).sum() / pred_count) if pred_count else 0.0
    recall = float((truth_edges & pred_dilated).sum() / truth_count) if truth_count else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return precision, recall, f1, pred_edges, truth_edges


def tolerant_edge_scores(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float, np.ndarray, np.ndarray]:
    return tolerant_edge_scores_at(
        pred,
        truth,
        low=int(CONFIG["metrics"]["edge_low_threshold"]),
        high=int(CONFIG["metrics"]["edge_high_threshold"]),
        tolerance=int(CONFIG["metrics"]["edge_tolerance_px"]),
    )


def highpass(image: np.ndarray) -> np.ndarray:
    sigma = float(CONFIG["metrics"]["highpass_sigma_px"])
    data = to_float(image)
    return data - cv2.GaussianBlur(data, (0, 0), sigmaX=sigma)


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    av = a.ravel().astype(np.float64)
    bv = b.ravel().astype(np.float64)
    av -= av.mean()
    bv -= bv.mean()
    denominator = float(np.linalg.norm(av) * np.linalg.norm(bv))
    return float(np.dot(av, bv) / denominator) if denominator > 1e-12 else 0.0


def metric_row(pred: np.ndarray, truth: np.ndarray) -> dict:
    pred_f, truth_f = to_float(pred), to_float(truth)
    precision, recall, f1, _, truth_edges = tolerant_edge_scores(pred, truth)
    band_radius = int(CONFIG["metrics"]["edge_band_radius_px"])
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band_radius + 1, 2 * band_radius + 1))
    band = cv2.dilate(truth_edges.astype(np.uint8), kernel) > 0
    absolute_error = np.abs(pred_f - truth_f)
    pred_hf, truth_hf = high_frequency_ratio(pred), high_frequency_ratio(truth)
    pred_edge, truth_edge = edge_energy(pred), edge_energy(truth)
    pred_contrast, truth_contrast = float(pred_f.std()), float(truth_f.std())
    hp_pred, hp_truth = highpass(pred), highpass(truth)
    shift, shift_response = cv2.phaseCorrelate(hp_truth.astype(np.float32), hp_pred.astype(np.float32))
    return {
        "psnr_db": psnr(pred, truth),
        "ssim": float(structural_similarity(truth_f, pred_f, data_range=1.0)),
        "mae": float(absolute_error.mean()),
        "edge_precision_t2": precision,
        "edge_recall_t2": recall,
        "edge_f1_t2": f1,
        "edge_band_mae": float(absolute_error[band].mean()) if band.any() else float(absolute_error.mean()),
        "highpass_corr": correlation(hp_pred, hp_truth),
        "highpass_mae": float(np.mean(np.abs(hp_pred - hp_truth))),
        "high_frequency_retention": float(pred_hf / truth_hf) if truth_hf > 1e-12 else 0.0,
        "edge_retention": float(pred_edge / truth_edge) if truth_edge > 1e-12 else 0.0,
        "contrast_retention": float(pred_contrast / truth_contrast) if truth_contrast > 1e-12 else 0.0,
        "global_shift_px": float(math.hypot(float(shift[0]), float(shift[1]))),
        "shift_response": float(shift_response),
    }


def combo_dirs() -> dict[str, Path]:
    summary = read_json(Path(PROJECT_ROOT / CONFIG["secondary_reference"]["summary"]))
    return {row["feature_family"]: Path(row["output_dir"]) for row in summary["stages"]}


def collect_metrics() -> pd.DataFrame:
    data_manifest = read_json(Path(PROJECT_ROOT / CONFIG["data"]["manifest"]))
    data_root = Path(PROJECT_ROOT / CONFIG["data"]["profile_root"])
    inference_manifest = read_json(RESULTS / "inference_manifest.json")
    combo = combo_dirs()
    rows = []
    for stage, family in family_map(data_manifest).items():
        r61_dir = Path(inference_manifest["output_dirs"][family])
        combo_dir = combo[family]
        for truth_path in image_paths(data_root / "lbl" / stage):
            truth = read_gray(truth_path)
            method_paths = {
                "raw": data_root / "src" / stage / truth_path.name,
                "combo": combo_dir / truth_path.name,
                "r61": r61_dir / truth_path.name,
            }
            for method, pred_path in method_paths.items():
                if not pred_path.is_file():
                    raise FileNotFoundError(pred_path)
                pred = read_gray(pred_path)
                if pred.shape != truth.shape:
                    raise RuntimeError(f"Shape mismatch: {pred_path}")
                row = metric_row(pred, truth)
                row.update({
                    "image_id": f"{family}/{truth_path.stem}",
                    "stage": stage,
                    "feature_family": family,
                    "family_label": FAMILY_LABELS[family],
                    "defect_focus": family in set(CONFIG["data"]["defect_focus_families"]),
                    "filename": truth_path.name,
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "prediction_path": str(pred_path),
                    "truth_path": str(truth_path),
                })
                rows.append(row)
    frame = pd.DataFrame(rows)
    if len(frame) != 300 or frame["image_id"].nunique() != 100:
        raise RuntimeError(f"Unexpected metric grain: rows={len(frame)}, images={frame['image_id'].nunique()}")
    frame.to_csv(TABLES / "per_image_metrics.csv", index=False, encoding="utf-8-sig")
    return frame


def bootstrap_median_ci(values: np.ndarray, seed_offset: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    repeats = int(CONFIG["metrics"]["bootstrap_repetitions"])
    rng = np.random.default_rng(int(CONFIG["metrics"]["random_seed"]) + seed_offset)
    medians = np.empty(repeats, dtype=float)
    chunk = 1000
    for start in range(0, repeats, chunk):
        stop = min(repeats, start + chunk)
        indices = rng.integers(0, len(values), size=(stop - start, len(values)))
        medians[start:stop] = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.empty(n, dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (n - rank) * float(p_values[index]))
        running = max(running, value)
        adjusted[index] = running
    return adjusted.tolist()


def paired_stats(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    comparisons = []
    wide_parts = []
    scopes = {
        "all": frame,
        "defect_focus": frame.loc[frame["defect_focus"]],
    }
    seed_offset = 0
    for scope, scoped in scopes.items():
        for baseline in ("raw", "combo"):
            p_values = []
            scope_rows = []
            for metric, direction in PRIMARY_METRICS.items():
                pivot = scoped.pivot(index="image_id", columns="method", values=metric).dropna()
                if not {baseline, "r61"}.issubset(pivot.columns):
                    raise RuntimeError(f"Missing methods for {scope}/{baseline}/{metric}")
                improvement = (pivot["r61"] - pivot[baseline]) if direction == "higher" else (pivot[baseline] - pivot["r61"])
                seed_offset += 1
                ci_low, ci_high = bootstrap_median_ci(improvement.to_numpy(), seed_offset)
                nonzero = improvement.to_numpy()[np.abs(improvement.to_numpy()) > 1e-12]
                if len(nonzero) == 0:
                    p_value = 1.0
                else:
                    p_value = float(wilcoxon(nonzero, alternative="two-sided", method="auto").pvalue)
                p_values.append(p_value)
                scope_rows.append({
                    "scope": scope,
                    "comparison": f"r61_vs_{baseline}",
                    "metric": metric,
                    "direction": direction,
                    "n_images": len(pivot),
                    "baseline_median": float(pivot[baseline].median()),
                    "r61_median": float(pivot["r61"].median()),
                    "median_improvement": float(improvement.median()),
                    "mean_improvement": float(improvement.mean()),
                    "improved_fraction": float((improvement > 0).mean()),
                    "ci95_low": ci_low,
                    "ci95_high": ci_high,
                    "wilcoxon_p": p_value,
                })
            adjusted = holm_adjust(p_values)
            for row, corrected in zip(scope_rows, adjusted):
                row["holm_p"] = corrected
                comparisons.append(row)

    wide = frame.pivot(index=["image_id", "stage", "feature_family", "family_label", "defect_focus", "filename"], columns="method", values=list(PRIMARY_METRICS)).reset_index()
    wide.columns = ["_".join([str(part) for part in column if part != ""]).rstrip("_") if isinstance(column, tuple) else str(column) for column in wide.columns]
    for metric, direction in PRIMARY_METRICS.items():
        if direction == "higher":
            wide[f"{metric}_r61_vs_raw_improvement"] = wide[f"{metric}_r61"] - wide[f"{metric}_raw"]
            wide[f"{metric}_r61_vs_combo_improvement"] = wide[f"{metric}_r61"] - wide[f"{metric}_combo"]
        else:
            wide[f"{metric}_r61_vs_raw_improvement"] = wide[f"{metric}_raw"] - wide[f"{metric}_r61"]
            wide[f"{metric}_r61_vs_combo_improvement"] = wide[f"{metric}_combo"] - wide[f"{metric}_r61"]
    wide.to_csv(TABLES / "paired_image_comparisons.csv", index=False, encoding="utf-8-sig")
    stats = pd.DataFrame(comparisons)
    stats.to_csv(TABLES / "paired_statistics.csv", index=False, encoding="utf-8-sig")
    return stats, wide


def summaries(frame: pd.DataFrame, wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_columns = list(PRIMARY_METRICS) + [
        "edge_precision_t2", "edge_recall_t2", "highpass_mae", "high_frequency_retention",
        "edge_retention", "contrast_retention", "global_shift_px", "shift_response",
    ]
    category = frame.groupby(["feature_family", "family_label", "method", "method_label"], as_index=False)[metric_columns].median()
    category["n_images"] = 20
    category.to_csv(TABLES / "category_summary.csv", index=False, encoding="utf-8-sig")
    overall_rows = []
    for scope_name, scoped in (("all", frame), ("defect_focus", frame.loc[frame["defect_focus"]])):
        for (method, method_label), group in scoped.groupby(["method", "method_label"]):
            row = {"scope": scope_name, "method": method, "method_label": method_label, "n_images": int(group["image_id"].nunique())}
            row.update({metric: float(group[metric].median()) for metric in metric_columns})
            overall_rows.append(row)
    overall = pd.DataFrame(overall_rows)
    overall.to_csv(TABLES / "overall_summary.csv", index=False, encoding="utf-8-sig")
    return category, overall


def edge_sensitivity(frame: pd.DataFrame) -> pd.DataFrame:
    thresholds = [(10, 30), (20, 50), (30, 75), (40, 100)]
    tolerances = [1, 2, 3, 4]
    rows = []
    defect = frame.loc[frame["defect_focus"] & frame["method"].isin(["raw", "r61"])].copy()
    for _, record in defect.iterrows():
        pred = read_gray(Path(record["prediction_path"]))
        truth = read_gray(Path(record["truth_path"]))
        for low, high in thresholds:
            for tolerance in tolerances:
                precision, recall, f1, _, _ = tolerant_edge_scores_at(
                    pred, truth, low=low, high=high, tolerance=tolerance
                )
                rows.append({
                    "image_id": record["image_id"],
                    "feature_family": record["feature_family"],
                    "method": record["method"],
                    "edge_low_threshold": low,
                    "edge_high_threshold": high,
                    "edge_tolerance_px": tolerance,
                    "edge_precision": precision,
                    "edge_recall": recall,
                    "edge_f1": f1,
                })
    detailed = pd.DataFrame(rows)
    detailed.to_csv(TABLES / "edge_sensitivity_per_image.csv", index=False, encoding="utf-8-sig")
    summary = detailed.groupby(
        ["edge_low_threshold", "edge_high_threshold", "edge_tolerance_px", "method"], as_index=False
    )[["edge_precision", "edge_recall", "edge_f1"]].median()
    pivot = summary.pivot(
        index=["edge_low_threshold", "edge_high_threshold", "edge_tolerance_px"],
        columns="method",
        values=["edge_precision", "edge_recall", "edge_f1"],
    ).reset_index()
    pivot.columns = [
        "_".join(str(part) for part in column if part != "").rstrip("_")
        if isinstance(column, tuple) else str(column)
        for column in pivot.columns
    ]
    for metric in ("edge_precision", "edge_recall", "edge_f1"):
        pivot[f"{metric}_r61_minus_raw"] = pivot[f"{metric}_r61"] - pivot[f"{metric}_raw"]
    pivot.to_csv(TABLES / "edge_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    return pivot


def decide(stats: pd.DataFrame, wide: pd.DataFrame) -> dict:
    def stat(scope: str, metric: str) -> pd.Series:
        rows = stats.loc[(stats["scope"] == scope) & (stats["comparison"] == "r61_vs_raw") & (stats["metric"] == metric)]
        if len(rows) != 1:
            raise RuntimeError(f"Missing stat: {scope}/{metric}")
        return rows.iloc[0]

    overall_fraction = float(CONFIG["pilot_gate"]["overall_improvement_fraction"])
    defect_fraction = float(CONFIG["pilot_gate"]["defect_improvement_fraction"])
    gate_specs = [
        ("overall_psnr", "all", "psnr_db", overall_fraction),
        ("overall_ssim", "all", "ssim", overall_fraction),
        ("defect_edge_f1", "defect_focus", "edge_f1_t2", defect_fraction),
        ("defect_highpass_corr", "defect_focus", "highpass_corr", defect_fraction),
    ]
    gates = {}
    for name, scope, metric, fraction in gate_specs:
        row = stat(scope, metric)
        gates[name] = {
            "pass": bool(row["median_improvement"] > 0 and row["ci95_low"] > 0 and row["improved_fraction"] >= fraction),
            "metric": metric,
            "scope": scope,
            "median_improvement": float(row["median_improvement"]),
            "ci95_low": float(row["ci95_low"]),
            "ci95_high": float(row["ci95_high"]),
            "improved_fraction": float(row["improved_fraction"]),
            "required_fraction": fraction,
        }

    family_checks = []
    for family, group in wide.groupby("feature_family"):
        psnr_delta = float(group["psnr_db_r61_vs_raw_improvement"].median())
        edge_delta = float(group["edge_f1_t2_r61_vs_raw_improvement"].median())
        passed = psnr_delta >= float(CONFIG["pilot_gate"]["family_psnr_floor_db"]) and edge_delta >= float(CONFIG["pilot_gate"]["family_edge_f1_floor"])
        family_checks.append({
            "feature_family": family,
            "family_label": FAMILY_LABELS[family],
            "median_psnr_improvement_db": psnr_delta,
            "median_edge_f1_improvement": edge_delta,
            "pass": bool(passed),
        })
    aggregate_pass = all(item["pass"] for item in gates.values())
    family_pass = all(item["pass"] for item in family_checks)
    if aggregate_pass and family_pass:
        verdict = "PASS_GENERALIZATION_PILOT"
    elif aggregate_pass:
        verdict = "PARTIAL_AGGREGATE_ONLY"
    else:
        verdict = "FAIL_GENERALIZATION_PILOT"
    decision = {
        "verdict": verdict,
        "aggregate_core_pass": aggregate_pass,
        "all_family_consistency_pass": family_pass,
        "primary_comparison": "R61v16 versus Raw on 100 independent synthetic microscopy images",
        "defect_focus": "edge_defects and mixed_fields, n=40",
        "gates": gates,
        "family_checks": family_checks,
        "interpretation_boundary": "Synthetic cross-generator stress test; not a substitute for new real SEM-paired samples.",
    }
    write_json(RESULTS / "decision.json", decision)
    return decision


def chart_style() -> None:
    font_path = Path(r"C:\Windows\Fonts\msjh.ttc")
    family = "DejaVu Sans"
    if font_path.is_file():
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams.update({
        "font.family": family,
        "axes.unicode_minus": False,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.edgecolor": "#343A40",
        "axes.labelcolor": "#202428",
        "xtick.color": "#343A40",
        "ytick.color": "#343A40",
        "figure.facecolor": "white",
        "axes.facecolor": "#FBFCFD",
        "axes.grid": True,
        "grid.color": "#D9DEE3",
        "grid.alpha": 0.55,
    })


def representative_rows(wide: pd.DataFrame) -> pd.DataFrame:
    selected = []
    for _, group in wide.groupby("feature_family", sort=False):
        median = float(group["psnr_db_r61_vs_raw_improvement"].median())
        index = (group["psnr_db_r61_vs_raw_improvement"] - median).abs().idxmin()
        selected.append(wide.loc[index])
    return pd.DataFrame(selected)


def generate_figures(
    frame: pd.DataFrame,
    wide: pd.DataFrame,
    category: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    chart_style()
    reps = representative_rows(wide)
    fig, axes = plt.subplots(5, 5, figsize=(15, 15), constrained_layout=True)
    for row_index, (_, row) in enumerate(reps.iterrows()):
        family = row["feature_family"]
        truth_path = Path(frame.loc[(frame["image_id"] == row["image_id"]) & (frame["method"] == "raw"), "truth_path"].iloc[0])
        raw_path = Path(frame.loc[(frame["image_id"] == row["image_id"]) & (frame["method"] == "raw"), "prediction_path"].iloc[0])
        r61_path = Path(frame.loc[(frame["image_id"] == row["image_id"]) & (frame["method"] == "r61"), "prediction_path"].iloc[0])
        truth, raw, r61 = read_gray(truth_path), read_gray(raw_path), read_gray(r61_path)
        panels = [truth, raw, r61, cv2.absdiff(raw, truth), cv2.absdiff(r61, truth)]
        titles = ["Ground truth", "Raw", "R61v16", "Raw |error|", "R61 |error|"]
        for column, (image, title) in enumerate(zip(panels, titles)):
            vmax = 80 if "error" in title else 255
            axes[row_index, column].imshow(image, cmap="gray", vmin=0, vmax=vmax)
            axes[row_index, column].set_xticks([])
            axes[row_index, column].set_yticks([])
            if row_index == 0:
                axes[row_index, column].set_title(title)
            if column == 0:
                axes[row_index, column].set_ylabel(FAMILY_LABELS[family])
    fig.suptitle("Representative synthetic microscopy reconstructions (median case per family)", fontsize=15)
    fig.savefig(FIGURES / "01_representative_reconstructions.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    family_order = list(FAMILY_LABELS)
    method_order = ["raw", "combo", "r61"]
    colors = {"raw": "#8B949E", "combo": "#D49A2A", "r61": "#2F6B9A"}
    x = np.arange(len(family_order))
    width = 0.24
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    for method_index, method in enumerate(method_order):
        subset = category.loc[category["method"] == method].set_index("feature_family").reindex(family_order)
        axes[0].bar(x + (method_index - 1) * width, subset["psnr_db"], width, label=METHOD_LABELS[method], color=colors[method], edgecolor="#30343B")
        axes[1].bar(x + (method_index - 1) * width, subset["edge_f1_t2"], width, label=METHOD_LABELS[method], color=colors[method], edgecolor="#30343B")
    for axis, title, ylabel, ylim in (
        (axes[0], "Median PSNR by feature family", "PSNR (dB, higher is better)", (0, None)),
        (axes[1], "Median edge agreement by feature family", "Boundary F1 within 2 px", (0, 1.0)),
    ):
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.set_xticks(x, [FAMILY_LABELS[item] for item in family_order], rotation=18, ha="right")
        axis.set_ylim(*ylim)
        axis.legend(frameon=False)
        axis.grid(axis="x", visible=False)
    fig.savefig(FIGURES / "02_metric_comparison_by_family.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    metrics = [
        ("psnr_db_r61_vs_raw_improvement", "PSNR improvement", "dB"),
        ("ssim_r61_vs_raw_improvement", "SSIM improvement", "score"),
        ("edge_f1_t2_r61_vs_raw_improvement", "Boundary F1 improvement", "score"),
        ("highpass_corr_r61_vs_raw_improvement", "Fine-detail correlation improvement", "score"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    for axis, (column, title, ylabel) in zip(axes.ravel(), metrics):
        data = [wide.loc[wide["feature_family"] == family, column].to_numpy() for family in family_order]
        box = axis.boxplot(data, tick_labels=[FAMILY_LABELS[item] for item in family_order], patch_artist=True, showfliers=True)
        for patch in box["boxes"]:
            patch.set_facecolor("#8CB8D9")
            patch.set_edgecolor("#2F5068")
        axis.axhline(0, color="#30343B", linewidth=1.2)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=18)
        axis.grid(axis="x", visible=False)
    fig.savefig(FIGURES / "03_paired_improvement_distributions.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    defect = wide.loc[wide["defect_focus"]].copy()
    chosen = []
    for family in CONFIG["data"]["defect_focus_families"]:
        group = defect.loc[defect["feature_family"] == family].sort_values("edge_f1_t2_r61_vs_raw_improvement")
        chosen.extend([group.iloc[0], group.iloc[len(group) // 2]])
    fig, axes = plt.subplots(4, 4, figsize=(12, 12), constrained_layout=True)
    for row_index, row in enumerate(chosen):
        image_id = row["image_id"]
        truth_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "raw"), "truth_path"].iloc[0])
        raw_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "raw"), "prediction_path"].iloc[0])
        r61_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "r61"), "prediction_path"].iloc[0])
        truth, raw, r61 = read_gray(truth_path), read_gray(raw_path), read_gray(r61_path)
        _, _, _, raw_edges, truth_edges = tolerant_edge_scores(raw, truth)
        _, _, _, r61_edges, _ = tolerant_edge_scores(r61, truth)
        overlay = np.zeros((*truth.shape, 3), dtype=np.uint8)
        overlay[truth_edges] = (255, 255, 255)
        overlay[raw_edges] = np.maximum(overlay[raw_edges], (220, 150, 40))
        overlay[r61_edges] = np.maximum(overlay[r61_edges], (45, 130, 210))
        panels = [truth, raw, r61, overlay]
        titles = ["Ground truth", "Raw", "R61v16", "Edges: truth/Raw/R61"]
        for column, (image, title) in enumerate(zip(panels, titles)):
            axes[row_index, column].imshow(image, cmap="gray" if image.ndim == 2 else None, vmin=0 if image.ndim == 2 else None, vmax=255 if image.ndim == 2 else None)
            axes[row_index, column].set_xticks([])
            axes[row_index, column].set_yticks([])
            if row_index == 0:
                axes[row_index, column].set_title(title)
            if column == 0:
                kind = "worst" if row_index % 2 == 0 else "middle"
                axes[row_index, column].set_ylabel(f"{FAMILY_LABELS[row['feature_family']]} ({kind})")
    fig.suptitle("Defect-focused cases: worst and middle boundary response", fontsize=15)
    fig.savefig(FIGURES / "04_defect_focus_examples.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    worst = wide.nsmallest(5, "psnr_db_r61_vs_raw_improvement")
    fig, axes = plt.subplots(5, 3, figsize=(9, 14), constrained_layout=True)
    for row_index, (_, row) in enumerate(worst.iterrows()):
        image_id = row["image_id"]
        truth_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "raw"), "truth_path"].iloc[0])
        raw_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "raw"), "prediction_path"].iloc[0])
        r61_path = Path(frame.loc[(frame["image_id"] == image_id) & (frame["method"] == "r61"), "prediction_path"].iloc[0])
        for column, (image, title) in enumerate(((read_gray(truth_path), "Ground truth"), (read_gray(raw_path), "Raw"), (read_gray(r61_path), "R61v16"))):
            axes[row_index, column].imshow(image, cmap="gray", vmin=0, vmax=255)
            axes[row_index, column].set_xticks([])
            axes[row_index, column].set_yticks([])
            if row_index == 0:
                axes[row_index, column].set_title(title)
            if column == 0:
                axes[row_index, column].set_ylabel(f"{FAMILY_LABELS[row['feature_family']]}\nDelta={row['psnr_db_r61_vs_raw_improvement']:+.2f} dB")
    fig.suptitle("Five largest R61 PSNR regressions versus Raw", fontsize=15)
    fig.savefig(FIGURES / "05_worst_failure_cases.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    heatmap = sensitivity.pivot(
        index=["edge_low_threshold", "edge_high_threshold"],
        columns="edge_tolerance_px",
        values="edge_f1_r61_minus_raw",
    ).sort_index()
    fig, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    bound = max(0.01, float(np.abs(heatmap.to_numpy()).max()))
    image = axis.imshow(heatmap.to_numpy(), cmap="RdBu", vmin=-bound, vmax=bound, aspect="auto")
    axis.set_title("Defect-set median boundary F1 sensitivity")
    axis.set_xlabel("Allowed boundary distance (px)")
    axis.set_ylabel("Canny thresholds")
    axis.set_xticks(np.arange(len(heatmap.columns)), [str(int(value)) for value in heatmap.columns])
    axis.set_yticks(
        np.arange(len(heatmap.index)),
        [f"{int(low)}/{int(high)}" for low, high in heatmap.index],
    )
    for row_index in range(heatmap.shape[0]):
        for column_index in range(heatmap.shape[1]):
            value = float(heatmap.iloc[row_index, column_index])
            axis.text(column_index, row_index, f"{value:+.3f}", ha="center", va="center", color="#111827")
    colorbar = fig.colorbar(image, ax=axis)
    colorbar.set_label("R61 minus Raw median F1")
    axis.grid(False)
    fig.savefig(FIGURES / "06_edge_sensitivity_heatmap.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    write_json(
        RESULTS / "chart_map.json",
        [
            {
                "figure": "01_representative_reconstructions.png",
                "question": "What does a typical reconstruction look like in each feature family?",
                "chart_type": "image comparison grid",
                "fields": ["feature_family", "ground_truth", "raw", "r61", "absolute_error"],
                "claim": "R61 sharpens structure, while behavior varies by feature family.",
                "palette": {"image": "grayscale", "error": "grayscale clipped at 80"},
            },
            {
                "figure": "02_metric_comparison_by_family.png",
                "question": "Which feature families improve or regress?",
                "chart_type": "grouped bar chart",
                "fields": ["feature_family", "method", "median_psnr_db", "median_edge_f1_t2"],
                "claim": "Only fine-line grids improve consistently on both primary family metrics.",
                "palette": {"raw": "#8B949E", "combo": "#D49A2A", "r61": "#2F6B9A"},
            },
            {
                "figure": "03_paired_improvement_distributions.png",
                "question": "How variable is the paired R61 improvement within each family?",
                "chart_type": "box plot",
                "fields": ["feature_family", "paired_improvement"],
                "claim": "Structural similarity and fine-detail correlation improve more consistently than PSNR or weak-edge agreement.",
                "palette": {"distribution": "#8CB8D9", "zero_reference": "#30343B"},
            },
            {
                "figure": "04_defect_focus_examples.png",
                "question": "Where does the defect-boundary score succeed or fail?",
                "chart_type": "image and edge-overlay grid",
                "fields": ["feature_family", "case_rank", "truth_edge", "raw_edge", "r61_edge"],
                "claim": "R61 finds cleaner strong edges but omits part of the faint true boundary set.",
                "palette": {"truth": "white", "raw": "orange", "r61": "blue"},
            },
            {
                "figure": "05_worst_failure_cases.png",
                "question": "What are the largest PSNR regressions?",
                "chart_type": "failure-case image grid",
                "fields": ["feature_family", "ground_truth", "raw", "r61", "paired_psnr_delta"],
                "claim": "Low-contrast textures dominate the largest intensity-error regressions.",
                "palette": {"image": "grayscale"},
            },
            {
                "figure": "06_edge_sensitivity_heatmap.png",
                "question": "Does the boundary conclusion depend on edge-detection settings?",
                "chart_type": "heatmap",
                "fields": ["canny_thresholds", "tolerance_px", "median_edge_f1_r61_minus_raw"],
                "claim": "R61 gains on strong-edge settings but loses on most weak-edge settings.",
                "palette": {"negative": "red", "neutral": "white", "positive": "blue"},
            },
        ],
    )


def fmt(value: float, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def build_report(
    decision: dict,
    stats: pd.DataFrame,
    category: pd.DataFrame,
    overall: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    def overall_value(scope: str, method: str, metric: str) -> float:
        return float(overall.loc[(overall["scope"] == scope) & (overall["method"] == method), metric].iloc[0])

    overall_psnr = stats.loc[(stats["scope"] == "all") & (stats["comparison"] == "r61_vs_raw") & (stats["metric"] == "psnr_db")].iloc[0]
    overall_ssim = stats.loc[(stats["scope"] == "all") & (stats["comparison"] == "r61_vs_raw") & (stats["metric"] == "ssim")].iloc[0]
    defect_edge = stats.loc[(stats["scope"] == "defect_focus") & (stats["comparison"] == "r61_vs_raw") & (stats["metric"] == "edge_f1_t2")].iloc[0]
    defect_hp = stats.loc[(stats["scope"] == "defect_focus") & (stats["comparison"] == "r61_vs_raw") & (stats["metric"] == "highpass_corr")].iloc[0]
    defect_precision_raw = overall_value("defect_focus", "raw", "edge_precision_t2")
    defect_precision_r61 = overall_value("defect_focus", "r61", "edge_precision_t2")
    defect_recall_raw = overall_value("defect_focus", "raw", "edge_recall_t2")
    defect_recall_r61 = overall_value("defect_focus", "r61", "edge_recall_t2")
    failed_families = [item["family_label"] for item in decision["family_checks"] if not item["pass"]]
    sensitivity_wins = int((sensitivity["edge_f1_r61_minus_raw"] > 0).sum())
    sensitivity_total = len(sensitivity)
    verdict_text = {
        "PASS_GENERALIZATION_PILOT": "通過這輪合成顯微泛化測試",
        "PARTIAL_AGGREGATE_ONLY": "整體改善，但沒有做到五類都一致",
        "FAIL_GENERALIZATION_PILOT": "未通過這輪合成顯微泛化測試",
    }[decision["verdict"]]

    category_rows = []
    for family in FAMILY_LABELS:
        raw_row = category.loc[(category["feature_family"] == family) & (category["method"] == "raw")].iloc[0]
        combo_row = category.loc[(category["feature_family"] == family) & (category["method"] == "combo")].iloc[0]
        r61_row = category.loc[(category["feature_family"] == family) & (category["method"] == "r61")].iloc[0]
        category_rows.append(
            f"| {FAMILY_LABELS[family]} | {raw_row['psnr_db']:.2f} | {combo_row['psnr_db']:.2f} | {r61_row['psnr_db']:.2f} | "
            f"{raw_row['edge_f1_t2']:.3f} | {combo_row['edge_f1_t2']:.3f} | {r61_row['edge_f1_t2']:.3f} |"
        )

    report = f"""# R71：R61 合成顯微缺陷泛化測試

## 技術摘要

**結論：{verdict_text}。** 本輪使用 100 張沒有出現在 R61 訓練資料中的合成顯微影像，其中 40 張是邊緣缺損與混合缺陷核心組。主要比較是同一張模糊輸入在重建前後，誰更接近已知的乾淨影像。

- 全部影像的 PSNR 中位數由 {overall_value('all', 'raw', 'psnr_db'):.2f} dB 變為 {overall_value('all', 'r61', 'psnr_db'):.2f} dB；每張影像配對後的中位改善為 {overall_psnr['median_improvement']:+.2f} dB，{overall_psnr['improved_fraction']:.0%} 影像改善。
- 全部影像的 SSIM 中位數由 {overall_value('all', 'raw', 'ssim'):.3f} 變為 {overall_value('all', 'r61', 'ssim'):.3f}；{overall_ssim['improved_fraction']:.0%} 影像改善。
- 缺陷核心組的輪廓 F1 中位改善為 {defect_edge['median_improvement']:+.3f}，{defect_edge['improved_fraction']:.0%} 影像改善；細節相關性中位改善為 {defect_hp['median_improvement']:+.3f}。
- 輪廓失分的主因不是亂生假邊，而是漏掉淡邊：缺陷組的輪廓精確度由 {defect_precision_raw:.3f} 升到 {defect_precision_r61:.3f}，但找回率由 {defect_recall_raw:.3f} 降到 {defect_recall_r61:.3f}。
- 後續 R72 已改用 ACM 比較 20 張有明確封閉外框的邊緣缺損影像：R61 的主要外框在 19/20 張改善，但周長與細部鋸齒誤差增加。因此本段輪廓 F1 應解讀為「淡邊是否留下」，不是完整形狀是否準確。
- 五類一致性：{'通過' if decision['all_family_consistency_pass'] else '未通過'}。{'退步類別：' + '、'.join(failed_families) if failed_families else '沒有類別同時在 PSNR 與輪廓 F1 的中位結果退步。'}

## 五類影像的結果

下表列出各類別的中位數。PSNR 與輪廓 F1 都是越高越好；COMBO 只作為同一測試集上的舊基準參考，不參與 R61 是否改善 Raw 的主要判定。

| 類別 | Raw PSNR | COMBO PSNR | R61 PSNR | Raw 輪廓 F1 | COMBO 輪廓 F1 | R61 輪廓 F1 |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(category_rows)}

![各類別分數比較](../results/figures/02_metric_comparison_by_family.png)

## 實際重建影像

每一列是該類別中最接近其中位表現的案例，因此不是刻意挑最好看的影像。最後兩欄顯示與乾淨答案的絕對差異。

![代表性重建結果](../results/figures/01_representative_reconstructions.png)

## 缺陷核心組與失敗案例

缺陷核心組固定由「邊緣缺損」和「混合缺陷」組成，共 40 張。下圖同時顯示每類的中間案例和最差輪廓案例；白色是正確輪廓、橘色是 Raw、藍色是 R61。

![缺陷核心案例](../results/figures/04_defect_focus_examples.png)

為避免整體平均掩蓋局部失敗，另列出 R61 相對 Raw 退步最大的五張影像。

![最差案例](../results/figures/05_worst_failure_cases.png)

輪廓判定另外改用 4 組強弱門檻與 1–4 像素容許距離，共 16 種設定。R61 在其中 {sensitivity_wins}/{sensitivity_total} 種設定的缺陷組輪廓 F1 中位數高於 Raw，因此主要輪廓結論{'穩定' if sensitivity_wins in (0, sensitivity_total) else '會受設定影響'}：重視強邊時 R61 多半較好，連淡邊也要求找回時則多半較差。這表示不能只用單一輪廓門檻宣稱模型全面成功或全面失敗。

![輪廓設定敏感度](../results/figures/06_edge_sensitivity_heatmap.png)

## ACM 完整輪廓追蹤驗證

R72 針對其中 20 張有單一封閉、不規則外框的邊緣缺損影像，改用與先前 SEM 比較同類的 ACM 做完整形狀驗證。只允許平移、不縮放也不旋轉後，R61 的輪廓重疊率由 Raw 的 0.9902 提升到 0.9920，平均邊界距離由 0.757px 降到 0.541px，兩項都是 19/20 張改善；三組預先固定的 ACM 設定也都保持正向結果。

但 R61 的周長誤差由 1.85% 增加到 6.55%，圓整程度誤差也由 0.033 增加到 0.081。合併兩種測試後，正確結論是：**R61 讓主要外框位置更準，但淡邊與細小鋸齒仍可能被平滑掉。** 完整結果見 [R72 ACM 報告](../../R72_R61SyntheticDefectACMContourValidation/reports/R72_RESULTS_TW.md)。

## 資料與評分定義

- 測試資料：R40 過去保留的 unseen 合成顯微驗證組，五類各 20 張，總共 100 張，影像大小 512×512。
- 正確答案：每張模糊來源都有像素對齊的乾淨合成影像；不需要額外估計縮放或位置。
- 缺陷核心組：邊緣缺損與混合缺陷兩類，共 40 張。
- 影像相似度：PSNR、SSIM 與平均絕對誤差。
- 形狀與細節：允許 2 像素誤差的輪廓 F1、正確輪廓附近的誤差，以及去除低頻背景後的細節相關性。
- 統計單位：每張獨立生成的影像；所有比較都在同一張影像內做 Raw 對 R61 配對。

## 方法與資料隔離

R61 使用正式的 best-tradeoff 模型及與真實樣品測試相同的 PSF 關閉設定。測試前檢查了 R61 的 20,296 組訓練清單，沒有引用這批 R40 顯微資料的路徑；另外對所有 200 個測試檔案，以及訓練集中尺寸相同的 1,400 個檔案做完整內容比對，沒有任何完全相同的影像。

判定門檻在重建前固定：整體 PSNR 與 SSIM 至少 70% 影像改善，缺陷核心組的輪廓 F1 與細節相關性至少 60% 改善，而且改善幅度的 95% 範圍下限必須高於零；五個類別的 PSNR 與輪廓 F1 中位數都不能退步。

## 限制與可靠度

這是一個跨資料產生器、跨模糊條件的合成壓力測試，能檢查 R61 是否保留未見過的格網、紋理、缺角、刮痕與混合結構。它的優點是正確答案完全已知；限制是合成模糊不等於新的真實顯微拍攝，因此不能單獨證明所有真實樣品都能泛化。

## 下一步

1. 將本輪失敗最多的類別轉成新的真實拍攝清單，優先補拍相同形狀特徵。
2. 若 R61 在某類出現固定退步，下一輪只補該缺陷族，不重新大範圍訓練。
3. 最終基準升級仍應同時要求真實 SEM 輪廓、真實多位置影像與位移量測都通過。

## 仍待回答的問題

- 合成測試中的退步類別，在新的真實 HS100MG 位置是否也會發生？
- 模糊程度與亮度進一步改變時，R61 的失效邊界在哪裡？
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")


def analyze() -> dict:
    TABLES.mkdir(parents=True, exist_ok=True)
    frame = collect_metrics()
    stats, wide = paired_stats(frame)
    category, overall = summaries(frame, wide)
    sensitivity = edge_sensitivity(frame)
    decision = decide(stats, wide)
    generate_figures(frame, wide, category, sensitivity)
    build_report(decision, stats, category, overall, sensitivity)
    return decision


def run_tests() -> None:
    command = [
        CONFIG["inference"]["python"], "-m", "unittest", "discover",
        "-s", str(ROOT / "tests"), "-p", "test_*.py", "-v",
    ]
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run R71 R61 synthetic microscopy defect generalization validation.")
    parser.add_argument("--stage", choices=["audit", "reconstruct", "analysis", "test", "all"], default="all")
    args = parser.parse_args()
    if args.stage in {"audit", "all"}:
        audit = audit_inputs()
        print(json.dumps({key: audit[key] for key in audit if key != "records"}, indent=2, ensure_ascii=False))
    if args.stage in {"reconstruct", "all"}:
        print(json.dumps(reconstruct(), indent=2, ensure_ascii=False))
    if args.stage in {"analysis", "all"}:
        print(json.dumps(analyze(), indent=2, ensure_ascii=False))
    if args.stage in {"test", "all"}:
        run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
