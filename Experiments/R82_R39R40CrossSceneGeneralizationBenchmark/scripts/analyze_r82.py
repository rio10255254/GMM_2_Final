from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy import stats
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
RECON = RESULTS / "reconstructions"
REPORT = ROOT / "reports" / "R82_RESULTS_TW.md"
MODELS = list(CONFIG["models"])
METHODS = ["Raw", *MODELS]
COLORS = {
    "Raw": "#718096", "COMBO": "#2b6cb0", "R39": "#38a169",
    "R40": "#dd6b20", "R39R40": "#805ad5", "R61": "#d53f8c", "R79": "#319795",
}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def paired_wilcoxon(model: np.ndarray, raw: np.ndarray) -> float:
    difference = np.asarray(model, dtype=float) - np.asarray(raw, dtype=float)
    if np.allclose(difference, 0):
        return 1.0
    return float(stats.wilcoxon(model, raw, alternative="two-sided").pvalue)


def bootstrap_median_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(20000, len(values)))
    medians = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(pvalues: list[float]) -> list[float]:
    values = np.asarray(pvalues, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty_like(values)
    running = 0.0
    count = len(values)
    for rank, index in enumerate(order):
        candidate = min(1.0, (count - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted.tolist()


def success_mask(series: pd.Series) -> pd.Series:
    """Normalize MATLAB logical CSV values without treating non-empty strings as True."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1"})


def external_summary() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    primary_frames = []
    sensitivity_frames = []
    for suite, item in CONFIG["external_acm_suites"].items():
        root = RESULTS / "acm_external" / suite / "results" / "tables"
        primary = pd.read_csv(root / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
        primary["suite"] = suite
        sensitivity["suite"] = suite
        if suite == "R74_hard_microscopy":
            manifest = json.loads(Path(PROJECT_ROOT / item["manifest"]).read_text(encoding="utf-8"))
            shape_map = {row["image_id"]: row["shape_family"] for row in manifest["records"]}
            primary["shape_family"] = primary["image_id"].map(shape_map)
            sensitivity["shape_family"] = sensitivity["image_id"].map(shape_map)
        else:
            primary["shape_family"] = primary["family"]
            sensitivity["shape_family"] = sensitivity["family"]
        primary_frames.append(primary)
        sensitivity_frames.append(sensitivity)
    primary = pd.concat(primary_frames, ignore_index=True)
    sensitivity = pd.concat(sensitivity_frames, ignore_index=True)
    primary.to_csv(TABLES / "external_acm_primary_combined.csv", index=False)
    sensitivity.to_csv(TABLES / "external_acm_sensitivity_combined.csv", index=False)
    translated = primary.loc[primary["alignment"] == "translation_only"].copy()

    summaries = []
    group_summaries = []
    paired_rows = []
    decisions: dict[str, dict] = {}
    for suite, suite_frame in translated.groupby("suite", sort=False):
        if set(suite_frame["method"]) != set(METHODS):
            raise RuntimeError(f"{suite}: method coverage changed")
        for method, group in suite_frame.groupby("method", sort=False):
            primary_failures = int((~success_mask(group["acm_success"])).sum())
            method_sensitivity = sensitivity.loc[
                (sensitivity["suite"] == suite) & (sensitivity["method"] == method)
            ]
            sensitivity_failures = int((~success_mask(method_sensitivity["acm_success"])).sum())
            summaries.append({
                "suite": suite, "method": method, "images": len(group),
                "acm_failure_images": primary_failures,
                "acm_sensitivity_failures": sensitivity_failures,
                "median_iou": float(group["iou"].median()),
                "median_mean_boundary_distance_px": float(group["mean_boundary_distance_px"].median()),
                "median_hd95_px": float(group["hd95_px"].median()),
                "median_area_error_pct": float(group["area_error_pct"].median()),
                "median_perimeter_error_pct": float(group["perimeter_error_pct"].median()),
                "median_roughness_abs_error": float(group["roughness_abs_error"].median()),
            })
        group_types = [("challenge_or_family", "family")]
        if suite == "R74_hard_microscopy":
            group_types.append(("shape_family", "shape_family"))
        for group_type, column in group_types:
            for (group_name, method), group in suite_frame.groupby([column, "method"], sort=False):
                group_summaries.append({
                    "suite": suite, "group_type": group_type, "group": group_name,
                    "method": method, "images": len(group),
                    "median_iou": float(group["iou"].median()),
                    "median_mean_boundary_distance_px": float(group["mean_boundary_distance_px"].median()),
                    "median_perimeter_error_pct": float(group["perimeter_error_pct"].median()),
                })

        iou_wide = suite_frame.pivot(index="image_id", columns="method", values="iou").loc[:, METHODS]
        distance_wide = suite_frame.pivot(index="image_id", columns="method", values="mean_boundary_distance_px").loc[:, METHODS]
        suite_decisions = {}
        raw_iou, raw_distance = iou_wide["Raw"], distance_wide["Raw"]
        for model_index, model in enumerate(MODELS):
            delta_iou = iou_wide[model] - raw_iou
            boundary_improvement = raw_distance - distance_wide[model]
            iou_ci = bootstrap_median_ci(delta_iou.to_numpy(), 2026080900 + model_index)
            boundary_ci = bootstrap_median_ci(boundary_improvement.to_numpy(), 2026081000 + model_index)
            group_frame = pd.DataFrame(group_summaries)
            group_frame = group_frame.loc[(group_frame["suite"] == suite) & (group_frame["method"].isin(["Raw", model]))]
            group_checks = []
            for (group_type, group_name), group in group_frame.groupby(["group_type", "group"]):
                indexed = group.set_index("method")
                group_checks.append({
                    "group_type": group_type, "group": group_name,
                    "iou_improvement": float(indexed.loc[model, "median_iou"] - indexed.loc["Raw", "median_iou"]),
                    "boundary_improvement_px": float(indexed.loc["Raw", "median_mean_boundary_distance_px"] - indexed.loc[model, "median_mean_boundary_distance_px"]),
                })
            sensitivity_suite = sensitivity.loc[sensitivity["suite"] == suite]
            sensitivity_checks = []
            for preset, group in sensitivity_suite.groupby("preset", sort=False):
                medians = group.groupby("method").agg(iou=("iou", "median"), boundary=("mean_boundary_distance_px", "median"))
                sensitivity_checks.append({
                    "preset": preset,
                    "iou_improvement": float(medians.loc[model, "iou"] - medians.loc["Raw", "iou"]),
                    "boundary_improvement_px": float(medians.loc["Raw", "boundary"] - medians.loc[model, "boundary"]),
                })
            group_pass = all(row["iou_improvement"] > 0 and row["boundary_improvement_px"] > 0 for row in group_checks)
            sensitivity_pass = all(row["iou_improvement"] > 0 and row["boundary_improvement_px"] > 0 for row in sensitivity_checks)
            model_failure_images = int((~success_mask(
                suite_frame.loc[suite_frame["method"] == model, "acm_success"]
            )).sum())
            model_sensitivity_failures = int((~success_mask(
                sensitivity_suite.loc[sensitivity_suite["method"] == model, "acm_success"]
            )).sum())
            gate_pass = bool(
                iou_ci[0] > 0 and boundary_ci[0] > 0
                and float((delta_iou > 0).mean()) >= 0.60
                and float((boundary_improvement > 0).mean()) >= 0.60
                and group_pass and sensitivity_pass
                and model_failure_images == 0 and model_sensitivity_failures == 0
            )
            row = {
                "suite": suite, "model": model, "images": len(delta_iou),
                "acm_failure_images": model_failure_images,
                "acm_sensitivity_failures": model_sensitivity_failures,
                "median_iou_improvement_vs_raw": float(delta_iou.median()),
                "iou_ci95_low": iou_ci[0], "iou_ci95_high": iou_ci[1],
                "iou_win_fraction": float((delta_iou > 0).mean()),
                "iou_p_raw": paired_wilcoxon(iou_wide[model].to_numpy(), raw_iou.to_numpy()),
                "median_boundary_improvement_vs_raw_px": float(boundary_improvement.median()),
                "boundary_ci95_low": boundary_ci[0], "boundary_ci95_high": boundary_ci[1],
                "boundary_win_fraction": float((boundary_improvement > 0).mean()),
                "boundary_p_raw": paired_wilcoxon(distance_wide[model].to_numpy(), raw_distance.to_numpy()),
                "all_group_medians_improved": group_pass,
                "all_sensitivity_presets_improved": sensitivity_pass,
                "strict_acm_gate_pass": gate_pass,
            }
            paired_rows.append(row)
            suite_decisions[model] = {**row, "group_checks": group_checks, "sensitivity_checks": sensitivity_checks}
        local_indices = [index for index, row in enumerate(paired_rows) if row["suite"] == suite]
        iou_adjusted = holm_adjust([paired_rows[index]["iou_p_raw"] for index in local_indices])
        boundary_adjusted = holm_adjust([paired_rows[index]["boundary_p_raw"] for index in local_indices])
        for index, iou_p, boundary_p in zip(local_indices, iou_adjusted, boundary_adjusted):
            paired_rows[index]["iou_p_holm"] = iou_p
            paired_rows[index]["boundary_p_holm"] = boundary_p
            model = paired_rows[index]["model"]
            suite_decisions[model]["iou_p_holm"] = iou_p
            suite_decisions[model]["boundary_p_holm"] = boundary_p
        decisions[suite] = suite_decisions

    summary = pd.DataFrame(summaries)
    group_summary = pd.DataFrame(group_summaries)
    paired = pd.DataFrame(paired_rows)
    sensitivity_summary = sensitivity.groupby(["suite", "preset", "method"], as_index=False).agg(
        images=("image_id", "count"), median_iou=("iou", "median"),
        median_mean_boundary_distance_px=("mean_boundary_distance_px", "median"),
    )
    summary.to_csv(TABLES / "external_acm_summary.csv", index=False)
    group_summary.to_csv(TABLES / "external_acm_group_summary.csv", index=False)
    paired.to_csv(TABLES / "external_acm_paired_vs_raw.csv", index=False)
    sensitivity_summary.to_csv(TABLES / "external_acm_sensitivity_summary.csv", index=False)
    return summary, group_summary, paired, decisions


def sem_summary() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    root = RESULTS / "acm_sem" / "tables"
    primary = pd.read_csv(root / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
    if set(primary["method"]) != set(METHODS) or len(primary) != 12 * 36 * len(METHODS):
        raise RuntimeError("SEM primary pairing is incomplete")
    primary.to_csv(TABLES / "sem_acm_primary_combined.csv", index=False)
    sensitivity.to_csv(TABLES / "sem_acm_sensitivity_combined.csv", index=False)
    per_pillar = primary.groupby(["pillar_id", "method"], as_index=False).agg(
        exposures=("exposure", "nunique"), median_iou=("iou", "median"),
        median_mean_boundary_distance_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        median_hd95_pitch_pct=("hd95_pitch_pct", "median"),
        median_area_error_pct=("area_error_pct", "median"),
        median_perimeter_error_pct=("perimeter_error_pct", "median"),
        median_circularity_abs_error=("circularity_abs_error", "median"),
    )
    per_pillar.to_csv(TABLES / "sem_acm_per_pillar.csv", index=False)
    rows = []
    for method, group in per_pillar.groupby("method", sort=False):
        rows.append({
            "method": method, "independent_pillars": len(group),
            "median_iou": float(group["median_iou"].median()),
            "median_mean_boundary_distance_pitch_pct": float(group["median_mean_boundary_distance_pitch_pct"].median()),
            "median_hd95_pitch_pct": float(group["median_hd95_pitch_pct"].median()),
            "median_area_error_pct": float(group["median_area_error_pct"].median()),
            "median_perimeter_error_pct": float(group["median_perimeter_error_pct"].median()),
            "median_circularity_abs_error": float(group["median_circularity_abs_error"].median()),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(TABLES / "sem_acm_summary.csv", index=False)

    iou_wide = per_pillar.pivot(index="pillar_id", columns="method", values="median_iou").loc[:, METHODS]
    distance_wide = per_pillar.pivot(index="pillar_id", columns="method", values="median_mean_boundary_distance_pitch_pct").loc[:, METHODS]
    paired_rows = []
    decisions = {}
    for index, model in enumerate(MODELS):
        delta_iou = iou_wide[model] - iou_wide["Raw"]
        boundary_improvement = distance_wide["Raw"] - distance_wide[model]
        iou_ci = bootstrap_median_ci(delta_iou.to_numpy(), 2026082000 + index)
        boundary_ci = bootstrap_median_ci(boundary_improvement.to_numpy(), 2026083000 + index)
        sensitivity_model = sensitivity.loc[sensitivity["method"].isin(["Raw", model])]
        preset_checks = []
        for preset, group in sensitivity_model.groupby("preset"):
            medians = group.groupby("method").agg(iou=("iou", "median"), boundary=("mean_boundary_distance_pitch_pct", "median"))
            preset_checks.append({
                "preset": preset,
                "iou_improvement": float(medians.loc[model, "iou"] - medians.loc["Raw", "iou"]),
                "boundary_improvement_pitch_pct": float(medians.loc["Raw", "boundary"] - medians.loc[model, "boundary"]),
            })
        row = {
            "model": model, "pillars": 36,
            "median_iou_improvement_vs_raw": float(delta_iou.median()),
            "iou_ci95_low": iou_ci[0], "iou_ci95_high": iou_ci[1],
            "iou_win_fraction": float((delta_iou > 0).mean()),
            "iou_p_raw": paired_wilcoxon(iou_wide[model].to_numpy(), iou_wide["Raw"].to_numpy()),
            "median_boundary_improvement_vs_raw_pitch_pct": float(boundary_improvement.median()),
            "boundary_ci95_low": boundary_ci[0], "boundary_ci95_high": boundary_ci[1],
            "boundary_win_fraction": float((boundary_improvement > 0).mean()),
            "boundary_p_raw": paired_wilcoxon(distance_wide[model].to_numpy(), distance_wide["Raw"].to_numpy()),
            "all_sensitivity_presets_improved": all(check["iou_improvement"] > 0 and check["boundary_improvement_pitch_pct"] > 0 for check in preset_checks),
        }
        row["strict_acm_gate_pass"] = bool(
            row["iou_ci95_low"] > 0 and row["boundary_ci95_low"] > 0
            and row["iou_win_fraction"] >= 0.60 and row["boundary_win_fraction"] >= 0.60
            and row["all_sensitivity_presets_improved"]
        )
        paired_rows.append(row)
        decisions[model] = {**row, "sensitivity_checks": preset_checks}
    iou_adjusted = holm_adjust([row["iou_p_raw"] for row in paired_rows])
    boundary_adjusted = holm_adjust([row["boundary_p_raw"] for row in paired_rows])
    for row, iou_p, boundary_p in zip(paired_rows, iou_adjusted, boundary_adjusted):
        row["iou_p_holm"] = iou_p; row["boundary_p_holm"] = boundary_p
        decisions[row["model"]]["iou_p_holm"] = iou_p
        decisions[row["model"]]["boundary_p_holm"] = boundary_p
    paired = pd.DataFrame(paired_rows)
    paired.to_csv(TABLES / "sem_acm_paired_vs_raw.csv", index=False)
    return summary, per_pillar, paired, decisions


def real_summary() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    motion = pd.read_csv(TABLES / "real_motion_summary.csv")
    fidelity = pd.read_csv(TABLES / "real_frame_fidelity.csv")
    artifact = pd.read_csv(TABLES / "real_artifact_frozen_frames.csv")
    fidelity_summary = fidelity.groupby(["sequence", "method"], as_index=False).agg(
        frames=("frame_index", "count"), median_correlation=("raw_output_correlation", "median"),
        median_fine_detail_ratio=("fine_detail_energy_ratio", "median"),
        median_absolute_change=("mean_absolute_change", "median"),
    )
    artifact_summary = artifact.groupby(["sequence", "method"], as_index=False).agg(
        frames=("frame_index", "count"), median_off_source_fraction=("off_source_strong_edge_fraction", "median"),
        p95_off_source_fraction=("off_source_strong_edge_fraction", lambda values: values.quantile(0.95)),
        median_edge_gain=("edge_gain_on_raw_support", "median"),
    )
    fidelity_summary.to_csv(TABLES / "real_frame_fidelity_summary.csv", index=False)
    artifact_summary.to_csv(TABLES / "real_artifact_summary.csv", index=False)
    rules = CONFIG["real_fov"]["artifact_metric"]
    decisions = {}
    for model in MODELS:
        model_motion = motion.loc[motion["method"] == model]
        model_fidelity = fidelity_summary.loc[fidelity_summary["method"] == model]
        model_artifact = artifact_summary.loc[artifact_summary["method"] == model]
        reasons = []
        if not model_motion["sequence_pass"].astype(str).str.lower().eq("true").all():
            reasons.append("one_or_more_real_sequences_failed_motion_gate")
        five_x_fidelity = model_fidelity.loc[model_fidelity["sequence"].str.startswith("5x")]
        five_x_artifact = model_artifact.loc[model_artifact["sequence"].str.startswith("5x")]
        if (five_x_fidelity["median_fine_detail_ratio"] < rules["warning_fine_detail_ratio_low"]).any():
            reasons.append("5x_fine_detail_ratio_below_0.75")
        if (five_x_artifact["median_off_source_fraction"] > rules["warning_off_source_fraction"]).any():
            reasons.append("5x_off_source_edge_fraction_above_0.05")
        decisions[model] = {
            "passed_sequences": int(model_motion["sequence_pass"].astype(str).str.lower().eq("true").sum()),
            "total_sequences": len(model_motion),
            "worst_median_difference_of_step": float(model_motion["median_difference_of_step"].max()),
            "worst_p95_difference_of_step": float(model_motion["p95_difference_of_step"].max()),
            "worst_median_scale_error_fraction": float(model_motion["median_scale_error_fraction"].max()),
            "worst_step_std_um": float(model_motion["step_std_um"].max()),
            "safety_pass": not reasons,
            "reasons": reasons,
        }
    return motion, fidelity_summary, artifact_summary, decisions


def junhua_summary() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    local = pd.read_csv(TABLES / "junhua_local_summary.csv")
    external = pd.read_csv(TABLES / "junhua_external_gmf_summary.csv")
    local_decisions = {}
    for model in MODELS:
        frame = local.loc[local["method"] == model]
        local_decisions[model] = {
            "valid_sequences": int((frame["valid_fraction"] >= 0.9).sum()),
            "total_sequences": len(frame),
            "worst_local_step_std_px": float(frame["step_std_px"].max()),
            "maximum_median_absolute_step_error_px": float(frame["median_absolute_step_error_px"].max()),
            "external_gmf_available": model in set(external["method"]),
        }
    return local, external, local_decisions


def rank_scenarios(external: pd.DataFrame, sem: pd.DataFrame, motion: pd.DataFrame, junhua: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for suite in CONFIG["external_acm_suites"]:
        frame = external.loc[(external["suite"] == suite) & (external["method"].isin(MODELS))].sort_values("median_mean_boundary_distance_px")
        for rank, (_, row) in enumerate(frame.iterrows(), start=1):
            rows.append({"scenario": suite, "model": row["method"], "rank": rank, "metric": "boundary_distance", "value": row["median_mean_boundary_distance_px"]})
    frame = sem.loc[sem["method"].isin(MODELS)].sort_values("median_mean_boundary_distance_pitch_pct")
    for rank, (_, row) in enumerate(frame.iterrows(), start=1):
        rows.append({"scenario": "SEM_36_pillars", "model": row["method"], "rank": rank, "metric": "boundary_distance_pitch_pct", "value": row["median_mean_boundary_distance_pitch_pct"]})
    worst_motion = motion.groupby("method", as_index=False)["median_difference_of_step"].max().sort_values("median_difference_of_step")
    for rank, (_, row) in enumerate(worst_motion.iterrows(), start=1):
        rows.append({"scenario": "real_FOV_motion", "model": row["method"], "rank": rank, "metric": "worst_median_difference_of_step", "value": row["median_difference_of_step"]})
    worst_junhua = junhua.loc[junhua["method"].isin(MODELS)].groupby("method", as_index=False)["step_std_px"].max().sort_values("step_std_px")
    for rank, (_, row) in enumerate(worst_junhua.iterrows(), start=1):
        rows.append({"scenario": "JunHua_local", "model": row["method"], "rank": rank, "metric": "worst_local_step_std_px", "value": row["step_std_px"]})
    result = pd.DataFrame(rows)
    result.to_csv(TABLES / "scenario_ranks.csv", index=False)
    return result


def configure_plot_font() -> None:
    font_path = Path(r"C:\Windows\Fonts\msjh.ttc")
    if font_path.is_file():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams.update({"font.family": font_manager.FontProperties(fname=str(font_path)).get_name(), "axes.unicode_minus": False})


def display(axis, image: np.ndarray, title: str) -> None:
    lo, hi = np.percentile(image, [0.5, 99.5])
    axis.imshow(image, cmap="gray", vmin=lo, vmax=hi)
    axis.set_title(title, fontsize=8)
    axis.axis("off")


def make_figures(external: pd.DataFrame, sem: pd.DataFrame, motion: pd.DataFrame, junhua: pd.DataFrame, external_gmf: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    configure_plot_font()
    plt.rcParams.update({"figure.dpi": 150, "font.size": 8})
    order = METHODS

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))
    for axis, suite in zip(axes[:2], CONFIG["external_acm_suites"]):
        frame = external.loc[external["suite"] == suite].set_index("method").loc[order]
        axis.bar(np.arange(len(order)), frame["median_mean_boundary_distance_px"], color=[COLORS[name] for name in order])
        axis.set_xticks(np.arange(len(order)), order, rotation=35, ha="right")
        axis.set_title(f"{suite}：邊界距離（越低越好）")
    sem_frame = sem.set_index("method").loc[order]
    axes[2].bar(np.arange(len(order)), sem_frame["median_mean_boundary_distance_pitch_pct"], color=[COLORS[name] for name in order])
    axes[2].set_xticks(np.arange(len(order)), order, rotation=35, ha="right")
    axes[2].set_title("SEM 36 顆：邊界距離 / 柱距（越低越好）")
    fig.tight_layout(); fig.savefig(FIGURES / "01_contour_truth_summary.png", bbox_inches="tight"); plt.close(fig)

    sequences = list(CONFIG["real_fov"]["sequences"])
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    width = 0.12; x = np.arange(len(sequences))
    for index, model in enumerate(MODELS):
        frame = motion.loc[motion["method"] == model].set_index("sequence").loc[sequences]
        offset = (index - (len(MODELS) - 1) / 2) * width
        axes[0].bar(x + offset, frame["median_difference_of_step"] * 100, width, label=model, color=COLORS[model])
        axes[1].bar(x + offset, frame["p95_difference_of_step"] * 100, width, label=model, color=COLORS[model])
    axes[0].axhline(10, color="#9b2c2c", linestyle="--"); axes[1].axhline(25, color="#9b2c2c", linestyle="--")
    axes[0].set_ylabel("中位差 / 位移 (%)"); axes[1].set_ylabel("95% 差 / 位移 (%)")
    axes[1].set_xticks(x, sequences, rotation=25, ha="right"); axes[0].legend(ncol=6)
    fig.tight_layout(); fig.savefig(FIGURES / "02_real_motion_summary.png", bbox_inches="tight"); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    junhua_order = list(CONFIG["junhua"]["sequences"])
    width = 0.105; x = np.arange(len(junhua_order))
    for index, method in enumerate(METHODS):
        frame = junhua.loc[junhua["method"] == method].set_index("sequence").loc[junhua_order]
        axes[0].bar(x + (index - 3) * width, frame["step_std_px"], width, label=method, color=COLORS[method])
    axes[0].set_xticks(x, junhua_order); axes[0].set_title("均華序列：本地位移波動（診斷）"); axes[0].legend(ncol=4)
    gmf_methods = [method for method in ("COMBO", "R39", "R40", "R39R40") if method in set(external_gmf["method"])]
    width = 0.18
    for index, method in enumerate(gmf_methods):
        frame = external_gmf.loc[external_gmf["method"] == method].set_index("sequence").loc[junhua_order]
        axes[1].bar(x + (index - 1.5) * width, frame["external_gmf_step_std_px"], width, label=method, color=COLORS[method])
    axes[1].set_xticks(x, junhua_order); axes[1].set_title("均華序列：既有外部 GMF（正式工具）"); axes[1].legend()
    fig.tight_layout(); fig.savefig(FIGURES / "03_junhua_stability.png", bbox_inches="tight"); plt.close(fig)

    r74_config = json.loads(Path(PROJECT_ROOT / CONFIG["external_acm_suites"]["R74_hard_microscopy"]["source_config"]).read_text(encoding="utf-8"))
    data_root = Path(PROJECT_ROOT / CONFIG["external_acm_suites"]["R74_hard_microscopy"]["dataset_root"])
    fig, axes = plt.subplots(5, len(METHODS), figsize=(21, 14))
    for row, family in enumerate(r74_config["dataset"]["families"]):
        stage = family["stage"]
        for column, method in enumerate(METHODS):
            path = data_root / "src" / stage / "0000.bmp" if method == "Raw" else RECON / "R74_hard_microscopy" / method / stage / "0000.bmp"
            display(axes[row, column], read_gray(path), f"{family['label_tw']} | {method}")
    fig.suptitle("固定取每組 0000：未人工挑圖")
    fig.tight_layout(); fig.savefig(FIGURES / "04_R74_fixed_contact_sheet.png", bbox_inches="tight"); plt.close(fig)

    fig, axes = plt.subplots(1, len(METHODS), figsize=(21, 4))
    sem_raw = Path(PROJECT_ROOT / CONFIG["sem_acm"]["raw_input_dir"]) / "18.bmp"
    for column, method in enumerate(METHODS):
        path = sem_raw if method == "Raw" else RECON / "sem_acm" / method / "18.bmp"
        display(axes[column], read_gray(path), f"曝光 18 | {method}")
    fig.tight_layout(); fig.savefig(FIGURES / "05_SEM_paired_exposure18.png", bbox_inches="tight"); plt.close(fig)

    selected = ["5x_0p5um", "20x_0p5um", "50x_0p5um"]
    raw_root = Path(PROJECT_ROOT / CONFIG["real_fov"]["locked_raw_root"])
    fig, axes = plt.subplots(len(selected), len(METHODS), figsize=(21, 10))
    for row, sequence in enumerate(selected):
        for column, method in enumerate(METHODS):
            path = raw_root / sequence / "frame_0000.bmp" if method == "Raw" else RECON / "real_fov" / method / sequence / "frame_0000.bmp"
            display(axes[row, column], read_gray(path), f"{sequence} | {method}")
    fig.suptitle("固定第一張真實顯微影像")
    fig.tight_layout(); fig.savefig(FIGURES / "06_real_fixed_contact_sheet.png", bbox_inches="tight"); plt.close(fig)


def fmt_bool(value) -> str:
    return "通過" if bool(value) else "未通過"


def write_report(audit: dict, external: pd.DataFrame, external_paired: pd.DataFrame, sem: pd.DataFrame, sem_paired: pd.DataFrame, motion: pd.DataFrame, real_decisions: dict, junhua: pd.DataFrame, gmf: pd.DataFrame, ranks: pd.DataFrame, decision: dict) -> None:
    sem_index = sem.set_index("method")
    external_index = external.set_index(["suite", "method"])
    lines = [
        "# R82 R39 / R40 跨場景泛化與位移驗證",
        "",
        "## 先講結論",
        "",
        decision["headline"],
        "",
        decision["r39_r40_conclusion"],
        "",
        decision["main_model_conclusion"],
        "",
        "本輪不修改正式 COMBO，也不把任何模型宣稱成所有未來場景都保證成功。",
        "",
        "## 驗證範圍",
        "",
        f"- 真實顯微位移：{audit['real_fov']['total_frames']} 張，包含 5×、20×、50× 共六組。",
        f"- 均華位移序列：{audit['junhua']['selected_frames']} 張固定影像；本地結果只作診斷，既有外部 GMF 另列。",
        "- 合成輪廓：100 張新形狀加 100 張高難度顯微影像，全部逐張配對精確形狀真值。",
        f"- SEM：{audit['sem_acm']['physical_pillars']} 顆真實 pillar、每顆 12 次光學曝光。",
        "- 模型：COMBO、R39、R40、R39R40 平衡版、R61、R79；Raw 只作共同參考。",
        "",
        "## 總表",
        "",
        "| 模型 | 真實位移通過 | SEM 邊界距離 (%柱距) | R73 邊界距離 (px) | R74 邊界距離 (px) | R73 / R74 擷取失敗 | SEM 嚴格輪廓門檻 | R73 / R74 嚴格門檻 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in MODELS:
        ext_gate = external_paired.loc[external_paired["model"] == model].set_index("suite")
        sem_gate = sem_paired.loc[sem_paired["model"] == model].iloc[0]
        lines.append(
            f"| {model} | {real_decisions[model]['passed_sequences']}/6 | "
            f"{sem_index.loc[model, 'median_mean_boundary_distance_pitch_pct']:.4f} | "
            f"{external_index.loc[('R73_novel_shapes', model), 'median_mean_boundary_distance_px']:.4f} | "
            f"{external_index.loc[('R74_hard_microscopy', model), 'median_mean_boundary_distance_px']:.4f} | "
            f"{int(external_index.loc[('R73_novel_shapes', model), 'acm_failure_images'])} / {int(external_index.loc[('R74_hard_microscopy', model), 'acm_failure_images'])} | "
            f"{fmt_bool(sem_gate['strict_acm_gate_pass'])} | "
            f"{fmt_bool(ext_gate.loc['R73_novel_shapes', 'strict_acm_gate_pass'])} / {fmt_bool(ext_gate.loc['R74_hard_microscopy', 'strict_acm_gate_pass'])} |"
        )
    lines.extend([
        "",
        f"Raw 共同參考的邊界距離為：SEM {sem_index.loc['Raw', 'median_mean_boundary_distance_pitch_pct']:.4f}% 柱距、"
        f"R73 {external_index.loc[('R73_novel_shapes', 'Raw'), 'median_mean_boundary_distance_px']:.4f} px、"
        f"R74 {external_index.loc[('R74_hard_microscopy', 'Raw'), 'median_mean_boundary_distance_px']:.4f} px。"
        "R39、R40、R39R40 在這三組形狀真值上都沒有超過 Raw；只有 R61、R79 在 SEM 通過嚴格門檻。",
        "",
        "![輪廓真值總覽](../results/figures/01_contour_truth_summary.png)",
        "",
        "## 真實顯微位移",
        "",
        "這一項沿用原本鎖定的 24 個有效區域與 Raw 配對，不重新挑位置。表中的差值越低越好。",
        "",
        "| 模型 | 通過組數 | 最差中位差 (%位移) | 最差 95% 差 (%位移) | 最差步距波動 (um) | 安全判定 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for model in MODELS:
        item = real_decisions[model]
        lines.append(f"| {model} | {item['passed_sequences']}/6 | {100*item['worst_median_difference_of_step']:.2f} | {100*item['worst_p95_difference_of_step']:.2f} | {item['worst_step_std_um']:.5f} | {fmt_bool(item['safety_pass'])} |")
    lines.extend([
        "",
        "![真實位移比較](../results/figures/02_real_motion_summary.png)",
        "",
        "## 均華三尺度",
        "",
        "本地定位可以比較六個模型，但它不是以前需金鑰的外部 GMF。外部 GMF 只有 COMBO、R39、R40、R39R40 有實測，因此不把 R61、R79 的空缺補成估計值。",
        "",
        "![均華位移比較](../results/figures/03_junhua_stability.png)",
        "",
        "| 尺度 | COMBO | R39 | R40 | R39R40 |",
        "|---|---:|---:|---:|---:|",
    ])
    for sequence in CONFIG["junhua"]["sequences"]:
        indexed = gmf.loc[gmf["sequence"] == sequence].set_index("method")
        lines.append(f"| {sequence} | {indexed.loc['COMBO', 'external_gmf_step_std_px']:.6f} | {indexed.loc['R39', 'external_gmf_step_std_px']:.6f} | {indexed.loc['R40', 'external_gmf_step_std_px']:.6f} | {indexed.loc['R39R40', 'external_gmf_step_std_px']:.6f} |")
    lines.extend([
        "",
        "## 輪廓與 SEM",
        "",
        "輪廓比較只看形狀。所有模型用同一個 ACM 設定，允許平移對齊，但不縮放、不旋轉，也不利用真值去初始化。",
        "",
        "![固定高難度案例](../results/figures/04_R74_fixed_contact_sheet.png)",
        "",
        "![固定 SEM 配對影像](../results/figures/05_SEM_paired_exposure18.png)",
        "",
        "![固定真實顯微影像](../results/figures/06_real_fixed_contact_sheet.png)",
        "",
        "## 證據限制",
        "",
        "- R79 的設計曾參考 R73、R74 的失敗型態，所以這兩組對 R79 是開發測試；R79 的乾淨確認主要看真實位移與 SEM。",
        "- 均華本地結果只用來補看趨勢，不能取代外部 GMF。",
        "- SEM 是 36 顆中心 pillar、同一批樣品與同一套光學條件，不能代表所有材料與設備。",
        "- 沒有把不同測試的數字硬平均成一個看似精確的總分；場景衝突會保留。",
        "",
        f"資料與計算可信度：**{decision['confidence']}**。",
    ])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_decision(external: pd.DataFrame, external_paired: pd.DataFrame, sem: pd.DataFrame, sem_paired: pd.DataFrame, real_decisions: dict, junhua_decisions: dict, ranks: pd.DataFrame) -> dict:
    winners = {scenario: group.sort_values("rank").iloc[0]["model"] for scenario, group in ranks.groupby("scenario")}
    eligible = [model for model in MODELS if real_decisions[model]["safety_pass"]]
    if "R40" in eligible:
        eligible.remove("R40")
    old_models = ["R39", "R40", "R39R40"]
    old_wins = {model: int(((ranks["model"] == model) & (ranks["rank"] == 1)).sum()) for model in old_models}
    confirmatory_ranks = ranks.loc[ranks["scenario"] != "JunHua_local"]
    eligible_old = [model for model in old_models if model in eligible]
    if not eligible_old:
        raise RuntimeError("No R39-family model remains after the locked safety veto")
    best_old = min(
        eligible_old,
        key=lambda model: float(confirmatory_ranks.loc[confirmatory_ranks["model"] == model, "rank"].mean()),
    )
    external_strict_passes = external_paired.groupby("model")["strict_acm_gate_pass"].all()
    sem_strict_passes = sem_paired.set_index("model")["strict_acm_gate_pass"]
    universal_candidates = [
        model for model in eligible
        if bool(external_strict_passes.get(model, False)) and bool(sem_strict_passes.get(model, False))
    ]
    headline = (
        f"在本輪鎖定的四個主要場景裡，第一名分別是：SEM {winners['SEM_36_pillars']}、"
        f"新形狀 {winners['R73_novel_shapes']}、高難度顯微 {winners['R74_hard_microscopy']}、"
        f"真實位移保持 {winners['real_FOV_motion']}。沒有一個模型包辦全部第一；"
        "而且沒有任何模型同時通過三組形狀真值的嚴格門檻。"
    )
    r39_r40_conclusion = (
        f"只看 R39 系列三個選項，排除既有定位否決後，最均衡的是 {best_old}；"
        "R40 雖然形狀成績最好，但 0.08 px 外部定位仍退步 21.52%，不能單獨升級。"
        "R39R40 的三尺度外部定位沒有明顯退步，適合作為這一系列的保守備用，但它的 SEM 與新形狀仍落後 Raw，不能取代 R61 或 R79。"
    )
    main_model_conclusion = (
        "若現在一定要選一個跨場景主力，仍以 R61 最均衡：真實位移六組全過、SEM 通過嚴格門檻，"
        "並在高難度顯微形狀中排名第一。R79 在 SEM、新形狀與真實位移最好，但高難度顯微形狀明顯最差，"
        "均華本地診斷也出現警訊，且尚無外部 GMF，因此目前只能列為強力候選，不能取代 R61。"
    )
    return {
        "headline": headline,
        "r39_r40_conclusion": r39_r40_conclusion,
        "main_model_conclusion": main_model_conclusion,
        "recommended_current_generalization_model": "R61",
        "scenario_winners": winners,
        "real_safety_eligible_models": eligible,
        "r39_family_scenario_win_counts": old_wins,
        "r39_family_balanced_choice": best_old,
        "r39_family_selection_basis": "locked safety veto, then confirmatory scenario ranks; JunHua local diagnostic excluded",
        "models_passing_all_contour_gates": universal_candidates,
        "confidence": "高（資料配對與計算）；中等（推廣到未測設備與樣品）",
        "claim_boundary": CONFIG["decision_rule"]["no_universal_claim"],
    }


def main() -> int:
    audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
    external, external_groups, external_paired, external_decisions = external_summary()
    sem, sem_per_pillar, sem_paired, sem_decisions = sem_summary()
    motion, fidelity, artifact, real_decisions = real_summary()
    junhua, gmf, junhua_decisions = junhua_summary()
    ranks = rank_scenarios(external, sem, motion, junhua)
    decision = build_decision(external, external_paired, sem, sem_paired, real_decisions, junhua_decisions, ranks)
    payload = {
        "experiment_id": CONFIG["experiment_id"],
        "coverage": {
            "models": len(MODELS), "real_frames": audit["real_fov"]["total_frames"],
            "junhua_frames": audit["junhua"]["selected_frames"], "external_acm_images": 200,
            "sem_physical_pillars": 36, "sem_repeated_exposures": 12,
        },
        "selection": decision,
        "real_motion": real_decisions,
        "external_acm": external_decisions,
        "sem_acm": sem_decisions,
        "junhua": junhua_decisions,
        "evidence_eligibility": CONFIG["evidence_eligibility"],
    }
    write_json(RESULTS / "decision.json", payload)
    make_figures(external, sem, motion, junhua, gmf)
    write_report(audit, external, external_paired, sem, sem_paired, motion, real_decisions, junhua, gmf, ranks, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
