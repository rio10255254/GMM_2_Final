from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
if str(PSF_FITTING_ROOT) not in sys.path:
    sys.path.insert(0, str(PSF_FITTING_ROOT))

from quick_recalibration.validation_experiments.l0_newdata_analysis import (
    VALIDATION_DIR,
    coef_label,
    collect_all_trials,
    collect_trial_fit_metrics,
    compute_noise_floor,
    fov_label,
    json_ready,
)


ROUND_NUMBERS = [1, 2, 3]
L1_DIR = VALIDATION_DIR / "L1_newdata"
SUMMARY_MD = L1_DIR / "L1_newdata_summary.md"
SUMMARY_JSON = L1_DIR / "L1_newdata_summary.json"
README_TW = L1_DIR / "README_TW.md"
EPS = 1e-12


def l1_output_paths() -> dict[str, Path]:
    return {
        "summary_dir": L1_DIR,
        "summary_md": SUMMARY_MD,
        "summary_json": SUMMARY_JSON,
        "readme_tw": README_TW,
    }


def compute_l1_capture_stats(round_tensors: np.ndarray, l0_floor: np.ndarray) -> dict[str, Any]:
    tensors = np.asarray(round_tensors, dtype=float)
    floor = np.asarray(l0_floor, dtype=float)

    if tensors.ndim != 4:
        raise ValueError(
            "round_tensors must have shape (capture_round, repeated_fit_trial, coefficient, fov)"
        )
    if floor.shape != tensors.shape[2:]:
        raise ValueError(f"l0_floor shape {floor.shape} does not match coefficient/FOV shape {tensors.shape[2:]}")

    n_rounds, n_trials, n_coef, n_fov = tensors.shape
    capture_representatives = np.median(tensors, axis=1)
    capture_center = np.median(capture_representatives, axis=0)
    capture_delta = capture_representatives - capture_center[None, :, :]
    capture_std = (
        capture_representatives.std(axis=0, ddof=1)
        if n_rounds > 1
        else np.zeros((n_coef, n_fov), dtype=float)
    )
    net_capture_std = np.sqrt(np.maximum((capture_std**2) - (floor**2), 0.0))
    abs_z_delta = np.abs(capture_delta) / np.maximum(floor[None, :, :], EPS)

    return {
        "n_capture_rounds": int(n_rounds),
        "n_trials_per_round": int(n_trials),
        "n_zernike": int(n_coef),
        "n_fov": int(n_fov),
        "capture_representatives": capture_representatives,
        "capture_center": capture_center,
        "capture_delta": capture_delta,
        "capture_std": capture_std,
        "l0_floor": floor,
        "net_capture_std": net_capture_std,
        "abs_z_delta": abs_z_delta,
    }


def decide_l1_status(median_abs_z: float, p95_abs_z: float) -> str:
    if median_abs_z < 2.0:
        return "within_L0_floor"
    if median_abs_z < 3.0 and p95_abs_z < 4.0:
        return "mostly_within_L0_floor"
    return "capture_variation_detected"


def load_round_bundle(round_number: int) -> dict[str, Any]:
    outputs_dir = VALIDATION_DIR / f"L0_newdata_round{round_number}" / "outputs"
    manifest_path = outputs_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing L0 output manifest for Circle_Round{round_number}: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tensor, used_dirs = collect_all_trials(manifest)
    l0_stats = compute_noise_floor(tensor)
    fit_metrics = collect_trial_fit_metrics(used_dirs)

    return {
        "round_number": round_number,
        "round_name": manifest.get("round_name", f"Circle_Round{round_number}"),
        "outputs_dir": outputs_dir,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "tensor": tensor,
        "used_dirs": used_dirs,
        "l0_stats": l0_stats,
        "fit_metrics": fit_metrics,
    }


def _normalized_manifest_rule(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "grid_rows": int(manifest.get("grid_rows")),
        "grid_cols": int(manifest.get("grid_cols")),
        "repeats_per_position": int(manifest.get("repeats_per_position")),
        "frame_number_used": int(manifest.get("frame_number_used")),
        "repeat_role": manifest.get("repeat_role"),
        "target_policy": manifest.get("target_policy"),
        "center_block_policy": manifest.get("center_block_policy"),
        "fov_indices": [int(value) for value in manifest.get("fov_indices", [])],
    }


def validate_l1_inputs(round_bundles: list[dict[str, Any]]) -> dict[str, Any]:
    if len(round_bundles) < 2:
        raise ValueError("L1 needs at least two capture rounds")

    reference_rule = _normalized_manifest_rule(round_bundles[0]["manifest"])
    reference_shape = round_bundles[0]["tensor"].shape

    for bundle in round_bundles[1:]:
        rule = _normalized_manifest_rule(bundle["manifest"])
        if rule != reference_rule:
            raise ValueError(
                f"L1 input rule mismatch between {round_bundles[0]['round_name']} and {bundle['round_name']}: "
                f"{reference_rule} != {rule}"
            )
        if bundle["tensor"].shape != reference_shape:
            raise ValueError(
                f"L1 tensor shape mismatch between {round_bundles[0]['round_name']} and {bundle['round_name']}: "
                f"{reference_shape} != {bundle['tensor'].shape}"
            )

    return reference_rule


def finite_summary(values: np.ndarray) -> dict[str, float | int | None]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            "count": 0,
            "median": None,
            "mean": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": int(finite.size),
        "median": float(np.median(finite)),
        "mean": float(np.mean(finite)),
        "p95": float(np.percentile(finite, 95)),
        "max": float(np.max(finite)),
    }


def _select_coef_values(values: np.ndarray, coef_indices: list[int]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not coef_indices:
        return np.empty((0,), dtype=float)
    if arr.ndim == 2:
        return arr[coef_indices, :]
    if arr.ndim == 3:
        return arr[:, coef_indices, :]
    raise ValueError(f"Unexpected values ndim: {arr.ndim}")


def trustworthy_index_sets(round_bundles: list[dict[str, Any]]) -> dict[str, list[int]]:
    all_sets = [set(bundle["l0_stats"]["trustworthy_indices"]) for bundle in round_bundles]
    intersection = sorted(set.intersection(*all_sets)) if all_sets else []
    union = sorted(set.union(*all_sets)) if all_sets else []
    majority = [
        coef_idx
        for coef_idx in union
        if sum(coef_idx in item for item in all_sets) >= max(2, (len(all_sets) // 2) + 1)
    ]
    readout = intersection if intersection else majority
    return {
        "intersection": intersection,
        "majority": majority,
        "readout": readout,
    }


def coefficient_status_table(round_bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n_coef = round_bundles[0]["l0_stats"]["n_zernike"]
    rows: list[dict[str, Any]] = []
    for coef_idx in range(n_coef):
        statuses = [
            bundle["l0_stats"]["classifications"][coef_idx]["status"]
            for bundle in round_bundles
        ]
        rows.append(
            {
                "coef_index": coef_idx,
                "coef_number": coef_idx + 1,
                "label": coef_label(coef_idx + 1),
                "statuses_by_round": statuses,
                "trustworthy_round_count": int(sum(status == "trustworthy" for status in statuses)),
            }
        )
    return rows


def summarize_l1(
    round_bundles: list[dict[str, Any]],
    input_rule: dict[str, Any],
    l1_stats: dict[str, Any],
    trusted: dict[str, list[int]],
) -> dict[str, Any]:
    readout_indices = trusted["readout"]

    all_abs_z = finite_summary(l1_stats["abs_z_delta"])
    readout_abs_z = finite_summary(_select_coef_values(l1_stats["abs_z_delta"], readout_indices))
    capture_std_summary = finite_summary(_select_coef_values(l1_stats["capture_std"], readout_indices))
    l0_floor_summary = finite_summary(_select_coef_values(l1_stats["l0_floor"], readout_indices))
    net_capture_summary = finite_summary(_select_coef_values(l1_stats["net_capture_std"], readout_indices))
    capture_abs_delta_summary = finite_summary(np.abs(_select_coef_values(l1_stats["capture_delta"], readout_indices)))

    median_abs_z = readout_abs_z["median"] if readout_abs_z["median"] is not None else all_abs_z["median"]
    p95_abs_z = readout_abs_z["p95"] if readout_abs_z["p95"] is not None else all_abs_z["p95"]
    status = decide_l1_status(float(median_abs_z or 0.0), float(p95_abs_z or 0.0))

    round_summaries = []
    for bundle in round_bundles:
        l0_stats = bundle["l0_stats"]
        fit_metrics = bundle["fit_metrics"]
        round_summaries.append(
            {
                "round_number": bundle["round_number"],
                "round_name": bundle["round_name"],
                "manifest_path": bundle["manifest_path"],
                "outputs_dir": bundle["outputs_dir"],
                "n_trials": l0_stats["n_trials"],
                "n_fov": l0_stats["n_fov"],
                "trustworthy_coef_indices": l0_stats["trustworthy_indices"],
                "l0_clean_noise_median": l0_stats["clean_std_overall_median"],
                "l0_clean_noise_mean": l0_stats["clean_std_overall_mean"],
                "l0_fov_consistency_ratio": l0_stats["fov_consistency_ratio"],
                "fval_mean": fit_metrics.get("fval_mean"),
                "fval_min": fit_metrics.get("fval_min"),
                "fval_max": fit_metrics.get("fval_max"),
                "result_rows": fit_metrics.get("result_rows"),
            }
        )

    fov_rows = []
    grid_cols = int(input_rule["grid_cols"])
    fov_indices = [int(value) for value in input_rule["fov_indices"]]
    for fov_pos, fov_index in enumerate(fov_indices):
        fov_rows.append(
            {
                "fov_index": fov_index,
                "label": fov_label(fov_index, grid_cols=grid_cols),
                "l0_floor_median": finite_summary(l1_stats["l0_floor"][readout_indices, fov_pos])["median"]
                if readout_indices
                else None,
                "capture_std_median": finite_summary(l1_stats["capture_std"][readout_indices, fov_pos])["median"]
                if readout_indices
                else None,
                "net_capture_std_median": finite_summary(l1_stats["net_capture_std"][readout_indices, fov_pos])["median"]
                if readout_indices
                else None,
                "median_abs_z": finite_summary(l1_stats["abs_z_delta"][:, readout_indices, fov_pos])["median"]
                if readout_indices
                else None,
            }
        )

    coef_rows = coefficient_status_table(round_bundles)
    for row in coef_rows:
        coef_idx = row["coef_index"]
        row["l0_floor_median"] = finite_summary(l1_stats["l0_floor"][coef_idx, :])["median"]
        row["capture_std_median"] = finite_summary(l1_stats["capture_std"][coef_idx, :])["median"]
        row["net_capture_std_median"] = finite_summary(l1_stats["net_capture_std"][coef_idx, :])["median"]
        row["median_abs_z"] = finite_summary(l1_stats["abs_z_delta"][:, coef_idx, :])["median"]
        row["used_for_main_readout"] = coef_idx in readout_indices

    return {
        "status": status,
        "status_basis": {
            "median_abs_z_readout": median_abs_z,
            "p95_abs_z_readout": p95_abs_z,
            "rule": "within if median < 2; mostly within if median < 3 and p95 < 4; otherwise capture variation detected",
        },
        "input_rule": input_rule,
        "rounds": round_summaries,
        "trustworthy_indices": trusted,
        "metrics": {
            "all_abs_z": all_abs_z,
            "readout_abs_z": readout_abs_z,
            "readout_capture_abs_delta": capture_abs_delta_summary,
            "readout_capture_std": capture_std_summary,
            "readout_l0_floor": l0_floor_summary,
            "readout_net_capture_std": net_capture_summary,
        },
        "fov_rows": fov_rows,
        "coef_rows": coef_rows,
    }


def build_l1_payload(round_numbers: list[int]) -> dict[str, Any]:
    round_bundles = [load_round_bundle(round_number) for round_number in round_numbers]
    input_rule = validate_l1_inputs(round_bundles)

    round_tensors = np.stack([bundle["tensor"] for bundle in round_bundles], axis=0)
    l0_floors = np.stack(
        [bundle["l0_stats"]["std_per_coef_per_fov"] for bundle in round_bundles],
        axis=0,
    )
    pooled_l0_floor = np.median(l0_floors, axis=0)
    l1_stats = compute_l1_capture_stats(round_tensors, pooled_l0_floor)
    trusted = trustworthy_index_sets(round_bundles)
    summary = summarize_l1(round_bundles, input_rule, l1_stats, trusted)

    return {
        "experiment": "L1_newdata_capture_repeatability",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "method": {
            "capture_repeat_axis": "Circle_Round1/2/3",
            "within_capture_fit_repeats": "15 fitting repeats per capture round",
            "representative_rule": "median coefficient value across the 15 repeated fits in each capture round",
            "formal_l0_anchor": "Circle_Round1",
            "repeat_fit_floor_rule": "median of per-round repeated-fit standard deviations at each coefficient/FOV",
            "net_l1_rule": "sqrt(max(capture_std^2 - L0_floor^2, 0))",
            "paired_frame_role": "second frame at each position is preserved as an acquisition duplicate, not used as the main L1 repeat axis",
            "baseline_guardrail": "this is a validation-layer readout, not a baseline promotion",
        },
        "summary": summary,
        "arrays": {
            "capture_representatives": l1_stats["capture_representatives"],
            "capture_center": l1_stats["capture_center"],
            "capture_delta": l1_stats["capture_delta"],
            "capture_std": l1_stats["capture_std"],
            "pooled_l0_floor": l1_stats["l0_floor"],
            "net_capture_std": l1_stats["net_capture_std"],
            "abs_z_delta": l1_stats["abs_z_delta"],
        },
    }


def _format_float(value: Any, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def status_sentence(status: str) -> str:
    if status == "within_L0_floor":
        return "The three capture rounds stay inside the repeated-fit floor by the main readout."
    if status == "mostly_within_L0_floor":
        return "The three capture rounds are mostly close to the repeated-fit floor, with some visible spread."
    return "The three capture rounds show a measurable capture-to-capture spread above the repeated-fit floor."


def tw_status_sentence(status: str) -> str:
    if status == "within_L0_floor":
        return "三次拍攝之間的差異沒有高過同一批資料自己重跑造成的波動。"
    if status == "mostly_within_L0_floor":
        return "三次拍攝大致接近同一批資料自己重跑造成的波動，但有少量可見差異。"
    return "三次拍攝之間已經可以看到高於同一批資料自己重跑的差異。"


def write_l1_report(payload: dict[str, Any]) -> tuple[Path, Path, Path]:
    L1_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(json_ready(payload), indent=2, ensure_ascii=False), encoding="utf-8")

    summary = payload["summary"]
    metrics = summary["metrics"]
    input_rule = summary["input_rule"]
    fov_indices = [str(value) for value in input_rule["fov_indices"]]
    readout_indices = summary["trustworthy_indices"]["readout"]
    readout_labels = [coef_label(coef_idx + 1) for coef_idx in readout_indices]

    lines: list[str] = []
    lines.append("# L1 New-Data Capture Repeatability Summary")
    lines.append("")
    lines.append(f"- Generated: {payload['generated_at']}")
    lines.append(f"- Result: {summary['status']} - {status_sentence(summary['status'])}")
    lines.append("- Capture repeat axis: Circle_Round1, Circle_Round2, Circle_Round3.")
    lines.append("- Formal L0 anchor: Circle_Round1 only.")
    lines.append("- Within each capture round: 15 repeated fits are collapsed by median before cross-round comparison.")
    lines.append("- Frame policy: uses frame 1 from each two-frame position pair; the second frame is not treated as a fourth/fifth/sixth L1 repeat.")
    lines.append("- Fit target: circle boundary only; the center square blocks are masked.")
    lines.append("- Guardrail: this is an L1 validation readout, not a formal baseline promotion.")
    lines.append("")
    lines.append("## Main Readout")
    lines.append("")
    lines.append(f"- Readout coefficients: {len(readout_indices)} ({', '.join(readout_labels)})")
    lines.append(f"- Repeat-fit floor median: {_format_float(metrics['readout_l0_floor']['median'])}")
    lines.append(f"- L1 capture spread median: {_format_float(metrics['readout_capture_std']['median'])}")
    lines.append(f"- Net L1 spread after repeat-fit floor: {_format_float(metrics['readout_net_capture_std']['median'])}")
    lines.append(f"- Median capture/repeat-fit ratio: {_format_float(metrics['readout_abs_z']['median'], digits=3)}")
    lines.append(f"- 95th percentile capture/repeat-fit ratio: {_format_float(metrics['readout_abs_z']['p95'], digits=3)}")
    lines.append(f"- Max capture/repeat-fit ratio: {_format_float(metrics['readout_abs_z']['max'], digits=3)}")
    lines.append("")
    lines.append("## Input Check")
    lines.append("")
    lines.append(f"- Grid: {input_rule['grid_rows']}x{input_rule['grid_cols']}")
    lines.append(f"- FOV points: {', '.join(fov_indices)}")
    lines.append(f"- Frames per position in source captures: {input_rule['repeats_per_position']}")
    lines.append(f"- Main frame used for this L1 readout: frame {input_rule['frame_number_used']}")
    lines.append(f"- Target policy: {input_rule['target_policy']}")
    lines.append(f"- Center block policy: {input_rule['center_block_policy']}")
    lines.append("")
    lines.append("## Source Rounds")
    lines.append("")
    lines.append("| Round | Repeated fits | Role | Repeat-fit median | Repeat-fit mean | Mean fit value | Result rows |")
    lines.append("|---|---:|---|---:|---:|---:|---:|")
    for item in summary["rounds"]:
        role = "formal_L0_anchor" if item["round_name"] == "Circle_Round1" else "L1_source_diagnostic"
        lines.append(
            f"| {item['round_name']} "
            f"| {item['n_trials']} "
            f"| {role} "
            f"| {_format_float(item['l0_clean_noise_median'])} "
            f"| {_format_float(item['l0_clean_noise_mean'])} "
            f"| {_format_float(item['fval_mean'], digits=2)} "
            f"| {item['result_rows']} |"
        )
    lines.append("")
    lines.append("## FOV Readout")
    lines.append("")
    lines.append("| FOV | Repeat-fit floor median | L1 spread median | Net L1 spread | Median capture/repeat-fit ratio |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in summary["fov_rows"]:
        lines.append(
            f"| {item['label']} "
            f"| {_format_float(item['l0_floor_median'])} "
            f"| {_format_float(item['capture_std_median'])} "
            f"| {_format_float(item['net_capture_std_median'])} "
            f"| {_format_float(item['median_abs_z'], digits=3)} |"
        )
    lines.append("")
    lines.append("## Coefficient Readout")
    lines.append("")
    lines.append("| Coefficient | Used | Trustworthy rounds | Repeat-fit floor median | L1 spread median | Net L1 spread | Median capture/repeat-fit ratio |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for item in summary["coef_rows"]:
        lines.append(
            f"| {item['label']} "
            f"| {'yes' if item['used_for_main_readout'] else 'no'} "
            f"| {item['trustworthy_round_count']}/3 "
            f"| {_format_float(item['l0_floor_median'])} "
            f"| {_format_float(item['capture_std_median'])} "
            f"| {_format_float(item['net_capture_std_median'])} "
            f"| {_format_float(item['median_abs_z'], digits=3)} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(f"- {status_sentence(summary['status'])}")
    lines.append("- Because there are only three capture rounds, this should be treated as an L1 measurement of this sample/capture condition.")
    lines.append("- The paired second image at each position is available for a separate paired-frame check, but it is not part of the main L1 repeat axis used here.")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    tw_lines = [
        "# L1 新資料摘要",
        "",
        f"- 產生時間：{payload['generated_at']}",
        "- 這次 L1 把 Circle_Round1、Circle_Round2、Circle_Round3 當成三次相同條件拍攝。",
        "- 每一輪已經各自做完 15 次擬合，這裡先取每輪自己的代表值，再比較三輪之間的差異。",
        "- 正式 L0 錨點只採用 Circle_Round1；Round2/3 是 L1 的來源診斷。",
        "- 同一位置的第二張影像沒有被當成額外重複；它另有 paired-frame 影像層補充檢查。",
        f"- 判讀結果：{tw_status_sentence(summary['status'])}",
        f"- 重複擬合底噪的中位波動：{_format_float(metrics['readout_l0_floor']['median'])}。",
        f"- 三輪拍攝之間的中位波動：{_format_float(metrics['readout_capture_std']['median'])}。",
        f"- 扣掉重複擬合底噪後仍可看到的中位 L1 波動：{_format_float(metrics['readout_net_capture_std']['median'])}。",
    ]
    README_TW.write_text("\n".join(tw_lines), encoding="utf-8")

    return SUMMARY_MD, SUMMARY_JSON, README_TW


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze new-data L1 capture repeatability from completed L0 runs.")
    parser.add_argument("--rounds", nargs="+", type=int, default=ROUND_NUMBERS)
    args = parser.parse_args()

    payload = build_l1_payload(args.rounds)
    report_path, json_path, readme_path = write_l1_report(payload)

    summary = payload["summary"]
    metrics = summary["metrics"]
    print(f"L1 status: {summary['status']}")
    print(f"Readout repeat-fit floor median: {_format_float(metrics['readout_l0_floor']['median'])}")
    print(f"Readout L1 spread median: {_format_float(metrics['readout_capture_std']['median'])}")
    print(f"Readout net L1 spread median: {_format_float(metrics['readout_net_capture_std']['median'])}")
    print(f"Report written: {report_path}")
    print(f"JSON written: {json_path}")
    print(f"README written: {readme_path}")


if __name__ == "__main__":
    main()
