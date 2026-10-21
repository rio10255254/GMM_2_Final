from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io as sio


PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = Path(__file__).resolve().parent
SUMMARY_DIR = VALIDATION_DIR / "L0_newdata"
SUMMARY_MD = SUMMARY_DIR / "L0_newdata_summary.md"
SUMMARY_JSON = SUMMARY_DIR / "L0_newdata_summary.json"

LB = np.array(
    [-0.3, -0.3, -0.1, 0.0, -0.1, -0.05, -0.05, -0.05, -0.05, -0.01, -0.01, 0.0, -0.01, -0.01, 0.8]
)
UB = np.array(
    [0.3, 0.3, 0.1, 1.0, 0.1, 0.05, 0.05, 0.05, 0.05, 0.01, 0.01, 0.3, 0.01, 0.01, 1.25]
)
LOCKED_COEF_INDICES = {0, 1}


def coef_label(idx: int) -> str:
    labels = {
        1: "x1 -> Z2 Y-tilt (locked=0)",
        2: "x2 -> Z3 X-tilt (locked=0)",
        3: "x3 -> Z4 astig 45deg",
        4: "x4 -> Z5 defocus",
        5: "x5 -> Z6 astig 0deg",
        6: "x6 -> Z7 trefoil",
        7: "x7 -> Z8 coma Y",
        8: "x8 -> Z9 coma X",
        9: "x9 -> Z10 trefoil",
        10: "x10 -> Z11 quadrafoil",
        11: "x11 -> Z12 secondary astig",
        12: "x12 -> Z13 spherical",
        13: "x13 -> Z14 secondary astig",
        14: "x14 -> Z15 quadrafoil",
        15: "x15 -> AC amplitude",
    }
    return labels.get(idx, f"x{idx}")


def fov_label(file_index: int, *, grid_cols: int) -> str:
    row = (file_index - 1) // grid_cols + 1
    col = (file_index - 1) % grid_cols + 1
    return f"#{file_index} (row {row}, col {col})"


def classify_coef(coef_idx: int, all_values: np.ndarray) -> dict[str, Any]:
    n_total = all_values.size
    unique_vals = np.unique(np.round(all_values, decimals=8))
    unique_count = len(unique_vals)
    overall_std = float(all_values.std(ddof=1)) if n_total > 1 else 0.0

    span = max(float(UB[coef_idx] - LB[coef_idx]), 1e-9)
    near_lb = np.abs(all_values - LB[coef_idx]) < 0.01 * span
    near_ub = np.abs(all_values - UB[coef_idx]) < 0.01 * span
    bound_frac = float((near_lb | near_ub).sum()) / n_total

    if coef_idx in LOCKED_COEF_INDICES:
        status = "locked"
        reason = "tilt is locked by the fitter, so this coefficient is not a useful noise-floor source"
    elif overall_std < 1e-7:
        status = "dead"
        reason = "all trials converged to nearly the same value"
    elif bound_frac > 0.8:
        status = "bound_saturated"
        reason = "most values sit on the search boundary"
    else:
        status = "trustworthy"
        reason = "values vary inside the search range"

    return {
        "status": status,
        "reason": reason,
        "bound_frac": bound_frac,
        "unique_count": int(unique_count),
        "overall_std": overall_std,
    }


def load_trial_coefs(trial_dir: Path) -> np.ndarray:
    stack_path = trial_dir / "PSF_fitted_2D_FOVstack.mat"
    if not stack_path.is_file():
        raise FileNotFoundError(f"Missing fitted stack: {stack_path}")
    data = sio.loadmat(str(stack_path), squeeze_me=False)
    coef_grid = np.asarray(data["coef_grid"])
    if coef_grid.ndim == 3:
        coef_grid = coef_grid[:, 0, :]
    if coef_grid.ndim != 2:
        raise ValueError(f"Unexpected coef_grid shape in {stack_path}: {coef_grid.shape}")
    return coef_grid


def resolve_trial_dir(trial_dir: str) -> Path:
    path = Path(trial_dir)
    if path.is_absolute():
        return path
    return (PSF_FITTING_ROOT / path).resolve()


def collect_all_trials(manifest: dict[str, Any]) -> tuple[np.ndarray, list[Path]]:
    trial_dirs = manifest["trial_dirs"]
    if isinstance(trial_dirs, str):
        trial_dirs = [trial_dirs]

    tensors = []
    used_dirs = []
    for trial_dir in trial_dirs:
        resolved = resolve_trial_dir(trial_dir)
        tensors.append(load_trial_coefs(resolved))
        used_dirs.append(resolved)

    if not tensors:
        raise RuntimeError("No trial directories listed in manifest")

    shapes = {tensor.shape for tensor in tensors}
    if len(shapes) != 1:
        raise ValueError(f"Trial coef_grid shapes do not match: {shapes}")

    return np.stack(tensors, axis=0), used_dirs


def fov_consistency_ratio(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    return float(values.max() / max(values.min(), 1e-12))


def compute_noise_floor(tensor: np.ndarray) -> dict[str, Any]:
    n_trials, n_zernike, n_fov = tensor.shape
    mean_pcf = tensor.mean(axis=0)
    std_pcf = tensor.std(axis=0, ddof=1) if n_trials > 1 else np.zeros((n_zernike, n_fov))
    median_pcf = np.median(tensor, axis=0)
    mad_pcf = np.median(np.abs(tensor - median_pcf[None, :, :]), axis=0)

    classifications = [
        classify_coef(coef_idx, tensor[:, coef_idx, :].flatten())
        for coef_idx in range(n_zernike)
    ]
    trustworthy_idx = [
        coef_idx for coef_idx, item in enumerate(classifications) if item["status"] == "trustworthy"
    ]

    if trustworthy_idx:
        clean_std_per_fov = std_pcf[trustworthy_idx, :].mean(axis=0)
        clean_std_overall_median = float(np.median(std_pcf[trustworthy_idx, :]))
        clean_std_overall_mean = float(std_pcf[trustworthy_idx, :].mean())
    else:
        clean_std_per_fov = np.full(n_fov, np.nan)
        clean_std_overall_median = float("nan")
        clean_std_overall_mean = float("nan")

    std_per_coef = std_pcf.mean(axis=1)
    std_per_fov = std_pcf.mean(axis=0)

    return {
        "n_trials": int(n_trials),
        "n_zernike": int(n_zernike),
        "n_fov": int(n_fov),
        "mean_per_coef_per_fov": mean_pcf,
        "std_per_coef_per_fov": std_pcf,
        "mad_per_coef_per_fov": mad_pcf,
        "median_per_coef_per_fov": median_pcf,
        "std_per_coef": std_per_coef,
        "mad_per_coef": mad_pcf.mean(axis=1),
        "std_per_fov": std_per_fov,
        "classifications": classifications,
        "trustworthy_indices": trustworthy_idx,
        "clean_std_per_fov": clean_std_per_fov,
        "clean_std_overall_median": clean_std_overall_median,
        "clean_std_overall_mean": clean_std_overall_mean,
        "fov_consistency_ratio": fov_consistency_ratio(clean_std_per_fov)
        if trustworthy_idx
        else float("nan"),
    }


def collect_trial_fit_metrics(used_dirs: list[Path]) -> dict[str, float | int | None]:
    fvals: list[float] = []
    iterations: list[float] = []
    for trial_dir in used_dirs:
        csv_path = trial_dir / "batch_results.csv"
        if not csv_path.is_file():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("fval"):
                    fvals.append(float(row["fval"]))
                if row.get("iterations"):
                    iterations.append(float(row["iterations"]))

    return {
        "result_rows": len(fvals),
        "fval_mean": float(np.mean(fvals)) if fvals else None,
        "fval_min": float(np.min(fvals)) if fvals else None,
        "fval_max": float(np.max(fvals)) if fvals else None,
        "iterations_mean": float(np.mean(iterations)) if iterations else None,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_round_json(
    outputs_dir: Path,
    manifest: dict[str, Any],
    stats: dict[str, Any],
    fit_metrics: dict[str, Any],
) -> Path:
    payload = {
        "experiment": "within_capture_repeat_fit_circle_edge",
        "round_name": manifest.get("round_name"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest_path": str(outputs_dir / "manifest.json"),
        "data_rule": {
            "grid_rows": manifest.get("grid_rows"),
            "grid_cols": manifest.get("grid_cols"),
            "repeats_per_position": manifest.get("repeats_per_position"),
            "frame_number_used": manifest.get("frame_number_used"),
            "repeat_role": manifest.get("repeat_role"),
            "target_policy": manifest.get("target_policy"),
            "center_block_policy": manifest.get("center_block_policy"),
        },
        "fov_indices": manifest.get("fov_indices"),
        "coef_labels": [coef_label(idx + 1) for idx in range(stats["n_zernike"])],
        "fit_metrics": fit_metrics,
        "noise_floor": {
            "n_trials": stats["n_trials"],
            "n_zernike": stats["n_zernike"],
            "n_fov": stats["n_fov"],
            "std_per_coef_per_fov": stats["std_per_coef_per_fov"],
            "mad_per_coef_per_fov": stats["mad_per_coef_per_fov"],
            "median_per_coef_per_fov": stats["median_per_coef_per_fov"],
            "mean_per_coef_per_fov": stats["mean_per_coef_per_fov"],
            "std_per_coef_avg_over_fov": stats["std_per_coef"],
            "mad_per_coef_avg_over_fov": stats["mad_per_coef"],
            "std_per_fov_avg_over_coef": stats["std_per_fov"],
            "coef_classifications": stats["classifications"],
            "trustworthy_coef_indices": stats["trustworthy_indices"],
            "clean": {
                "trustworthy_count": len(stats["trustworthy_indices"]),
                "std_per_fov_avg_over_trustworthy_coefs": stats["clean_std_per_fov"],
                "overall_median_std": stats["clean_std_overall_median"],
                "overall_mean_std": stats["clean_std_overall_mean"],
                "fov_consistency_ratio_max_over_min": stats["fov_consistency_ratio"],
            },
        },
    }
    out_path = outputs_dir / "L0_newdata_noise_floor.json"
    out_path.write_text(json.dumps(json_ready(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def write_round_report(
    outputs_dir: Path,
    manifest: dict[str, Any],
    stats: dict[str, Any],
    fit_metrics: dict[str, Any],
    json_path: Path,
) -> Path:
    fov_indices = [int(value) for value in manifest["fov_indices"]]
    grid_cols = int(manifest.get("grid_cols", 11))
    report_path = outputs_dir / "L0_newdata_noise_floor_report.md"

    lines: list[str] = []
    lines.append(f"# L0 New-Data Noise Floor Report - {manifest.get('round_name')}")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Trials: {stats['n_trials']}")
    lines.append(f"- FOV points: {stats['n_fov']} ({', '.join(str(i) for i in fov_indices)})")
    lines.append(
        f"- Data rule: {manifest.get('grid_rows')}x{manifest.get('grid_cols')}, "
        f"{manifest.get('repeats_per_position')} frames/position, using frame {manifest.get('frame_number_used')}"
    )
    lines.append(f"- Repeat rule: {manifest.get('repeat_role')}")
    lines.append(f"- Target: {manifest.get('target_policy')}")
    lines.append(f"- Center block handling: {manifest.get('center_block_policy')}")
    lines.append(f"- Source JSON: {json_path.name}")
    lines.append("")
    lines.append("## Main Readout")
    lines.append("")
    lines.append(
        f"- Clean noise floor median: {stats['clean_std_overall_median']:.6f} "
        f"(mean {stats['clean_std_overall_mean']:.6f})"
    )
    lines.append(f"- Trustworthy coefficients: {len(stats['trustworthy_indices'])}/{stats['n_zernike']}")
    lines.append(f"- FOV clean-noise consistency max/min: {stats['fov_consistency_ratio']:.3f}")
    if fit_metrics.get("fval_mean") is not None:
        lines.append(
            f"- Fit value range: {fit_metrics['fval_min']:.2f} to {fit_metrics['fval_max']:.2f}; "
            f"mean {fit_metrics['fval_mean']:.2f}"
        )
    lines.append("")
    lines.append("## FOV Clean Noise")
    lines.append("")
    lines.append("| FOV | Clean std | Full mean std |")
    lines.append("|---|---:|---:|")
    for idx, fov_index in enumerate(fov_indices):
        lines.append(
            f"| {fov_label(fov_index, grid_cols=grid_cols)} "
            f"| {stats['clean_std_per_fov'][idx]:.6f} "
            f"| {stats['std_per_fov'][idx]:.6f} |"
        )
    lines.append("")
    lines.append("## Coefficient Classification")
    lines.append("")
    lines.append("| Coefficient | Status | Overall std | Bound % | Reason |")
    lines.append("|---|---|---:|---:|---|")
    for coef_idx, classif in enumerate(stats["classifications"]):
        lines.append(
            f"| {coef_label(coef_idx + 1)} "
            f"| {classif['status']} "
            f"| {classif['overall_std']:.6f} "
            f"| {classif['bound_frac'] * 100:.1f}% "
            f"| {classif['reason']} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This is a within-capture repeated-fit readout on one capture round.")
    lines.append("- For the corrected experiment definition, Circle_Round1 is the formal L0 anchor; Circle_Round2/3 are L1 source diagnostics.")
    lines.append("- Circle_Round1/2/3 are handled as the three capture repeats; the paired frames inside each position are not the main repeat axis here.")
    lines.append("- The square blocks at the center are excluded by the fitting mask, so the circle boundary controls the fit.")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def analyze_round(round_number: int) -> dict[str, Any]:
    outputs_dir = VALIDATION_DIR / f"L0_newdata_round{round_number}" / "outputs"
    manifest_path = outputs_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest for Round{round_number}: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tensor, used_dirs = collect_all_trials(manifest)
    stats = compute_noise_floor(tensor)
    fit_metrics = collect_trial_fit_metrics(used_dirs)
    json_path = write_round_json(outputs_dir, manifest, stats, fit_metrics)
    report_path = write_round_report(outputs_dir, manifest, stats, fit_metrics, json_path)

    return {
        "round_number": round_number,
        "round_name": manifest.get("round_name", f"Round{round_number}"),
        "outputs_dir": str(outputs_dir),
        "report_path": str(report_path),
        "json_path": str(json_path),
        "n_trials": stats["n_trials"],
        "n_fov": stats["n_fov"],
        "trustworthy_count": len(stats["trustworthy_indices"]),
        "clean_noise_floor_median": stats["clean_std_overall_median"],
        "clean_noise_floor_mean": stats["clean_std_overall_mean"],
        "fov_consistency_ratio": stats["fov_consistency_ratio"],
        "fval_mean": fit_metrics.get("fval_mean"),
        "fval_min": fit_metrics.get("fval_min"),
        "fval_max": fit_metrics.get("fval_max"),
    }


def build_l0_summary_payload(
    round_summaries: list[dict[str, Any]],
    *,
    formal_round_number: int = 1,
) -> dict[str, Any]:
    if not round_summaries:
        raise ValueError("No round summaries supplied")

    formal_matches = [
        item for item in round_summaries if int(item["round_number"]) == formal_round_number
    ]
    if len(formal_matches) != 1:
        raise ValueError(f"Expected exactly one formal L0 round {formal_round_number}")

    formal_l0 = dict(formal_matches[0])
    formal_l0["role"] = "formal_L0"

    source_inventory: list[dict[str, Any]] = []
    all_completed_rounds: list[dict[str, Any]] = []
    for item in round_summaries:
        row = dict(item)
        if int(item["round_number"]) == formal_round_number:
            row["role"] = "formal_L0"
        else:
            row["role"] = "L1_source_only"
            source_inventory.append(row)
        all_completed_rounds.append(row)

    medians = np.array([item["clean_noise_floor_median"] for item in round_summaries], dtype=float)
    means = np.array([item["clean_noise_floor_mean"] for item in round_summaries], dtype=float)

    return {
        "experiment": "L0_newdata_formal_single_capture",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "definition": {
            "l0_rule": "one capture set repeated through the fitter",
            "formal_l0_capture": f"Circle_Round{formal_round_number}",
            "l1_rule": "separate capture rounds compared after each has its own repeated-fit representative",
            "correction_note": "Circle_Round2/3 are retained as L1 source diagnostics, not aggregated into the formal L0 readout",
        },
        "formal_l0": formal_l0,
        "l1_source_inventory": source_inventory,
        "all_completed_repeat_fit_runs": all_completed_rounds,
        "source_inventory_diagnostic": {
            "round_count": len(round_summaries),
            "median_of_round_medians": float(np.median(medians)) if len(medians) else None,
            "mean_of_round_medians": float(np.mean(medians)) if len(medians) else None,
            "std_of_round_medians": float(np.std(medians, ddof=1)) if len(medians) > 1 else 0.0,
            "mean_of_round_means": float(np.mean(means)) if len(means) else None,
            "not_formal_l0": True,
        },
        "data_rule": {
            "grid": "11x11",
            "positions": "old L0 nine-point pattern for 11x11: 1, 6, 11, 56, 61, 66, 111, 116, 121",
            "formal_l0_capture": f"Circle_Round{formal_round_number}",
            "l1_capture_repeats": "Circle_Round1/2/3",
            "frame_policy": "frame 1 of each two-frame position pair",
            "fit_target": "circle boundary only; center square blocks masked",
        },
    }


def write_summary(round_summaries: list[dict[str, Any]]) -> tuple[Path, Path]:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    summary_payload = build_l0_summary_payload(round_summaries, formal_round_number=1)
    SUMMARY_JSON.write_text(
        json.dumps(json_ready(summary_payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    formal = summary_payload["formal_l0"]
    inventory = summary_payload["l1_source_inventory"]
    lines: list[str] = []
    lines.append("# L0 New-Data Formal Summary")
    lines.append("")
    lines.append(f"- Generated: {summary_payload['generated_at']}")
    lines.append("- Formal L0 rule: one capture set repeated through the fitter.")
    lines.append("- Formal L0 capture: Circle_Round1.")
    lines.append("- L1 source rule: Circle_Round1/2/3 are separate capture repeats.")
    lines.append("- Round2/Round3 are retained as L1 source diagnostics, not aggregated into the formal L0 readout.")
    lines.append("- Data rule: 11x11 grid, old nine-point pattern, frame 1 from each two-frame position pair.")
    lines.append("- Fit target: circle boundary only; center square blocks are masked.")
    lines.append("- Legacy L0 outputs were archived under `archive_L0_legacy_20260616`.")
    lines.append("")
    lines.append("## Formal L0 Result")
    lines.append("")
    lines.append("| Round | Trials | Clean median | Clean mean | FOV max/min | Mean fit value | Report |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    fval = formal["fval_mean"]
    fval_text = f"{fval:.2f}" if fval is not None else "n/a"
    lines.append(
        f"| {formal['round_name']} "
        f"| {formal['n_trials']} "
        f"| {formal['clean_noise_floor_median']:.6f} "
        f"| {formal['clean_noise_floor_mean']:.6f} "
        f"| {formal['fov_consistency_ratio']:.3f} "
        f"| {fval_text} "
        f"| {Path(formal['report_path']).name} |"
    )
    lines.append("")
    lines.append("## L1 Source Fit Inventory")
    lines.append("")
    lines.append("These completed repeated-fit runs are useful for L1, but they are not part of the formal L0 aggregate.")
    lines.append("")
    lines.append("| Round | Role | Trials | Repeat-fit median | Repeat-fit mean | FOV max/min | Mean fit value |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for item in inventory:
        fval = item["fval_mean"]
        fval_text = f"{fval:.2f}" if fval is not None else "n/a"
        lines.append(
            f"| {item['round_name']} "
            f"| {item['role']} "
            f"| {item['n_trials']} "
            f"| {item['clean_noise_floor_median']:.6f} "
            f"| {item['clean_noise_floor_mean']:.6f} "
            f"| {item['fov_consistency_ratio']:.3f} "
            f"| {fval_text} |"
        )
    lines.append("")
    lines.append("## Source Inventory Diagnostic")
    lines.append("")
    diagnostic = summary_payload["source_inventory_diagnostic"]
    lines.append(f"- Median of all completed round medians: {diagnostic['median_of_round_medians']:.6f}")
    lines.append(f"- Mean of all completed round medians: {diagnostic['mean_of_round_medians']:.6f}")
    lines.append(f"- Std of all completed round medians: {diagnostic['std_of_round_medians']:.6f}")
    lines.append(f"- Mean of all completed round means: {diagnostic['mean_of_round_means']:.6f}")
    lines.append("- This section is only a source-inventory sanity check, not the formal L0 definition.")
    lines.append("")
    lines.append("## Interpretation Guardrails")
    lines.append("")
    lines.append("- Formal L0 is Circle_Round1 repeated through the fitter 15 times.")
    lines.append("- Circle_Round2/3 are separate captures and belong to the L1 comparison layer.")
    lines.append("- The two same-position frames are acquisition duplicates; frame 2 is handled by the paired-frame supplemental check.")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    return SUMMARY_MD, SUMMARY_JSON


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze new-data L0 circle-edge outputs.")
    parser.add_argument("--rounds", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    summaries: list[dict[str, Any]] = []
    for round_number in args.rounds:
        try:
            summary = analyze_round(round_number)
        except FileNotFoundError:
            if args.allow_missing:
                continue
            raise
        print(
            f"Round{round_number}: clean median={summary['clean_noise_floor_median']:.6f}, "
            f"trials={summary['n_trials']}"
        )
        summaries.append(summary)

    if not summaries:
        raise RuntimeError("No completed rounds were analyzed")
    summary_md, summary_json = write_summary(summaries)
    print(f"Summary written: {summary_md}")
    print(f"Summary JSON written: {summary_json}")


if __name__ == "__main__":
    main()
