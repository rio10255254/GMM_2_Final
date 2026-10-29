from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy import stats
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
RECON = RESULTS / "reconstructions"
REPORT = ROOT / "reports" / "R80_RESULTS_TW.md"
MODELS = ["R79E23", "R79E100"]
COLORS = {"Raw": "#718096", "R79E23": "#2b6cb0", "R79E100": "#dd6b20"}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def paired_wilcoxon(a: np.ndarray, b: np.ndarray) -> float:
    difference = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if np.allclose(difference, 0):
        return 1.0
    return float(stats.wilcoxon(a, b, alternative="two-sided").pvalue)


def bootstrap_median_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(20000, len(values)))
    medians = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def external_summary() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    primary_frames = []
    sensitivity_frames = []
    for suite in CONFIG["external_acm_suites"]:
        root = RESULTS / "acm_external" / suite / "results" / "tables"
        primary = pd.read_csv(root / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
        primary["suite"] = suite
        sensitivity["suite"] = suite
        primary_frames.append(primary)
        sensitivity_frames.append(sensitivity)
    primary = pd.concat(primary_frames, ignore_index=True)
    sensitivity = pd.concat(sensitivity_frames, ignore_index=True)
    primary.to_csv(TABLES / "external_acm_primary_combined.csv", index=False)
    sensitivity.to_csv(TABLES / "external_acm_sensitivity_combined.csv", index=False)

    translated = primary.loc[primary["alignment"] == "translation_only"].copy()
    summaries = []
    family_summaries = []
    decisions = {}
    for suite, suite_frame in translated.groupby("suite"):
        for method, group in suite_frame.groupby("method"):
            summaries.append({
                "suite": suite,
                "method": method,
                "images": len(group),
                "median_iou": float(group["iou"].median()),
                "median_mean_boundary_distance_px": float(group["mean_boundary_distance_px"].median()),
                "median_hd95_px": float(group["hd95_px"].median()),
                "median_area_error_pct": float(group["area_error_pct"].median()),
                "median_perimeter_error_pct": float(group["perimeter_error_pct"].median()),
                "median_roughness_abs_error": float(group["roughness_abs_error"].median()),
            })
        for (family, method), group in suite_frame.groupby(["family", "method"]):
            family_summaries.append({
                "suite": suite,
                "family": family,
                "family_label_tw": group["family_label_tw"].iloc[0],
                "method": method,
                "images": len(group),
                "median_iou": float(group["iou"].median()),
                "median_mean_boundary_distance_px": float(group["mean_boundary_distance_px"].median()),
                "median_perimeter_error_pct": float(group["perimeter_error_pct"].median()),
            })
        wide_iou = suite_frame.pivot(index="image_id", columns="method", values="iou")
        wide_distance = suite_frame.pivot(index="image_id", columns="method", values="mean_boundary_distance_px")
        delta_iou = wide_iou["R79E100"] - wide_iou["R79E23"]
        delta_distance = wide_distance["R79E23"] - wide_distance["R79E100"]
        iou_ci = bootstrap_median_ci(delta_iou.to_numpy(), 2026080601)
        distance_ci = bootstrap_median_ci(delta_distance.to_numpy(), 2026080602)
        family_table = pd.DataFrame(family_summaries)
        family_table = family_table.loc[family_table["suite"] == suite]
        worst = {}
        for model in MODELS:
            candidate = family_table.loc[family_table["method"] == model]
            worst[model] = float(candidate["median_mean_boundary_distance_px"].max())
        if worst["R79E23"] < worst["R79E100"]:
            winner = "R79E23"
        elif worst["R79E100"] < worst["R79E23"]:
            winner = "R79E100"
        else:
            winner = "tie"
        decisions[suite] = {
            "winner_by_worst_family_boundary_distance": winner,
            "worst_family_boundary_distance_px": worst,
            "median_iou_e100_minus_e23": float(delta_iou.median()),
            "median_iou_difference_ci95": list(iou_ci),
            "iou_wilcoxon_p": paired_wilcoxon(wide_iou["R79E100"], wide_iou["R79E23"]),
            "median_boundary_improvement_e100_over_e23_px": float(delta_distance.median()),
            "median_boundary_improvement_ci95": list(distance_ci),
            "boundary_wilcoxon_p": paired_wilcoxon(wide_distance["R79E100"], wide_distance["R79E23"]),
            "e100_better_iou_fraction": float((delta_iou > 0).mean()),
            "e100_better_boundary_fraction": float((delta_distance > 0).mean()),
        }
    summary = pd.DataFrame(summaries)
    family_summary = pd.DataFrame(family_summaries)
    summary.to_csv(TABLES / "external_acm_summary.csv", index=False)
    family_summary.to_csv(TABLES / "external_acm_family_summary.csv", index=False)

    sensitivity_summary = sensitivity.groupby(["suite", "preset", "method"], as_index=False).agg(
        images=("image_id", "count"),
        median_iou=("iou", "median"),
        median_mean_boundary_distance_px=("mean_boundary_distance_px", "median"),
    )
    sensitivity_summary.to_csv(TABLES / "external_acm_sensitivity_summary.csv", index=False)
    return summary, family_summary, decisions


def sem_summary() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    candidate_frames = []
    raw_reference = None
    sensitivity_frames = []
    for label in MODELS:
        root = RESULTS / "acm_sem" / label / "results" / "tables"
        primary = pd.read_csv(root / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
        raw = primary.loc[primary["method"] == "Raw"].sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
        if raw_reference is None:
            raw_reference = raw
        else:
            columns = ["exposure", "pillar_id", "iou", "mean_boundary_distance_pitch_pct", "area_error_pct", "perimeter_error_pct"]
            if not np.allclose(raw_reference[columns[2:]], raw[columns[2:]], rtol=0, atol=1e-12):
                raise RuntimeError("Raw SEM ACM extraction differs between checkpoint arms")
        candidate_frames.append(primary.loc[primary["method"] == label].copy())
        sensitivity_frames.append(sensitivity.loc[sensitivity["method"] == label].copy())
    combined = pd.concat([raw_reference, *candidate_frames], ignore_index=True)
    combined.to_csv(TABLES / "sem_acm_primary_combined.csv", index=False)
    pd.concat(sensitivity_frames, ignore_index=True).to_csv(TABLES / "sem_acm_sensitivity_candidates.csv", index=False)

    per_pillar = combined.groupby(["pillar_id", "method"], as_index=False).agg(
        exposures=("exposure", "nunique"),
        median_iou=("iou", "median"),
        median_mean_boundary_distance_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        median_hd95_pitch_pct=("hd95_pitch_pct", "median"),
        median_area_error_pct=("area_error_pct", "median"),
        median_perimeter_error_pct=("perimeter_error_pct", "median"),
        median_circularity_abs_error=("circularity_abs_error", "median"),
    )
    per_pillar.to_csv(TABLES / "sem_acm_per_pillar.csv", index=False)
    summaries = []
    for method, group in per_pillar.groupby("method"):
        summaries.append({
            "method": method,
            "independent_pillars": len(group),
            "median_iou": float(group["median_iou"].median()),
            "median_mean_boundary_distance_pitch_pct": float(group["median_mean_boundary_distance_pitch_pct"].median()),
            "median_hd95_pitch_pct": float(group["median_hd95_pitch_pct"].median()),
            "median_area_error_pct": float(group["median_area_error_pct"].median()),
            "median_perimeter_error_pct": float(group["median_perimeter_error_pct"].median()),
            "median_circularity_abs_error": float(group["median_circularity_abs_error"].median()),
        })
    summary = pd.DataFrame(summaries)
    summary.to_csv(TABLES / "sem_acm_summary.csv", index=False)

    iou_wide = per_pillar.pivot(index="pillar_id", columns="method", values="median_iou")
    distance_wide = per_pillar.pivot(index="pillar_id", columns="method", values="median_mean_boundary_distance_pitch_pct")
    delta_iou = iou_wide["R79E100"] - iou_wide["R79E23"]
    delta_distance = distance_wide["R79E23"] - distance_wide["R79E100"]
    if delta_distance.median() > 0 and delta_iou.median() >= 0:
        winner = "R79E100"
    elif delta_distance.median() < 0 and delta_iou.median() <= 0:
        winner = "R79E23"
    else:
        winner = "tie"
    decision = {
        "winner": winner,
        "median_iou_e100_minus_e23": float(delta_iou.median()),
        "median_iou_difference_ci95": list(bootstrap_median_ci(delta_iou.to_numpy(), 2026080603)),
        "iou_wilcoxon_p": paired_wilcoxon(iou_wide["R79E100"], iou_wide["R79E23"]),
        "median_boundary_improvement_e100_over_e23_pitch_pct": float(delta_distance.median()),
        "median_boundary_improvement_ci95": list(bootstrap_median_ci(delta_distance.to_numpy(), 2026080604)),
        "boundary_wilcoxon_p": paired_wilcoxon(distance_wide["R79E100"], distance_wide["R79E23"]),
        "e100_better_iou_fraction": float((delta_iou > 0).mean()),
        "e100_better_boundary_fraction": float((delta_distance > 0).mean()),
    }
    return summary, per_pillar, decision


def internal_decision() -> tuple[pd.DataFrame, dict]:
    summary = pd.read_csv(TABLES / "internal_test_summary.csv")
    roles = summary.loc[summary["training_role"] != "ALL"]
    worst = {}
    for model in MODELS:
        group = roles.loc[roles["model"] == model]
        worst[model] = {
            "worst_role_median_mae": float(group["median_mae"].max()),
            "worst_role_median_edge_f1": float(group["median_edge_f1"].min()),
            "role_mae_wins": 0,
            "role_edge_f1_wins": 0,
        }
    for role, group in roles.groupby("training_role"):
        indexed = group.set_index("model")
        mae_winner = indexed["median_mae"].idxmin()
        edge_winner = indexed["median_edge_f1"].idxmax()
        worst[mae_winner]["role_mae_wins"] += 1
        worst[edge_winner]["role_edge_f1_wins"] += 1
    if worst["R79E23"]["worst_role_median_mae"] < worst["R79E100"]["worst_role_median_mae"]:
        winner = "R79E23"
    elif worst["R79E100"]["worst_role_median_mae"] < worst["R79E23"]["worst_role_median_mae"]:
        winner = "R79E100"
    else:
        winner = "tie"
    return summary, {"winner_by_worst_role_mae": winner, "models": worst}


def real_decision() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    motion = pd.read_csv(TABLES / "real_motion_summary.csv")
    fidelity = pd.read_csv(TABLES / "real_frame_fidelity.csv")
    tile = pd.read_csv(TABLES / "real_5x_tile_sensitivity.csv")
    artifact = pd.read_csv(TABLES / "real_artifact_frozen_frames.csv")
    tile_summary = tile.groupby(["sequence", "method", "tile_size"], as_index=False).agg(
        frames=("frame_index", "count"),
        median_correlation=("raw_output_correlation", "median"),
        median_fine_detail_ratio=("fine_detail_energy_ratio", "median"),
        median_off_source_fraction=("off_source_strong_edge_fraction", "median"),
        p95_off_source_fraction=("off_source_strong_edge_fraction", lambda values: values.quantile(0.95)),
        median_edge_gain=("edge_gain_on_raw_support", "median"),
    )
    tile_summary.to_csv(TABLES / "real_5x_tile_sensitivity_summary.csv", index=False)
    fidelity_summary = fidelity.groupby(["sequence", "method"], as_index=False).agg(
        frames=("frame_index", "count"),
        median_correlation=("raw_output_correlation", "median"),
        median_fine_detail_ratio=("fine_detail_energy_ratio", "median"),
        median_absolute_change=("mean_absolute_change", "median"),
    )
    fidelity_summary.to_csv(TABLES / "real_frame_fidelity_summary.csv", index=False)
    artifact_summary = artifact.groupby(["sequence", "method"], as_index=False).agg(
        frames=("frame_index", "count"),
        median_off_source_fraction=("off_source_strong_edge_fraction", "median"),
        median_edge_gain=("edge_gain_on_raw_support", "median"),
    )
    artifact_summary.to_csv(TABLES / "real_artifact_summary.csv", index=False)

    rules = CONFIG["real_fov"]["artifact_metric"]
    models = {}
    for model in MODELS:
        model_motion = motion.loc[motion["method"] == model]
        model_5x = tile_summary.loc[(tile_summary["method"] == model) & (tile_summary["tile_size"] == 1024)]
        safety_reasons = []
        if not model_motion["sequence_pass"].astype(str).str.lower().eq("true").all():
            safety_reasons.append("one_or_more_real_sequences_failed_motion_gate")
        if (model_5x["median_fine_detail_ratio"] < rules["warning_fine_detail_ratio_low"]).any():
            safety_reasons.append("5x_fine_detail_ratio_below_0.75")
        if (model_5x["median_off_source_fraction"] > rules["warning_off_source_fraction"]).any():
            safety_reasons.append("5x_off_source_edge_fraction_above_0.05")
        models[model] = {
            "passed_sequences": int(model_motion["sequence_pass"].astype(str).str.lower().eq("true").sum()),
            "total_sequences": len(model_motion),
            "worst_median_difference_of_step": float(model_motion["median_difference_of_step"].max()),
            "worst_p95_difference_of_step": float(model_motion["p95_difference_of_step"].max()),
            "worst_median_scale_error_fraction": float(model_motion["median_scale_error_fraction"].max()),
            "eligible": not safety_reasons,
            "safety_reasons": safety_reasons,
        }
    return motion, tile_summary, fidelity_summary, {"models": models}


def choose_checkpoint(sem: dict, external: dict, internal: dict, real: dict) -> dict:
    eligible = [model for model in MODELS if real["models"][model]["eligible"]]
    truth_winners = {
        "SEM": sem["winner"],
        "R74_hard_microscopy": external["R74_hard_microscopy"]["winner_by_worst_family_boundary_distance"],
        "R73_expanded_shapes": external["R73_expanded_shapes"]["winner_by_worst_family_boundary_distance"],
        "internal_test": internal["winner_by_worst_role_mae"],
    }
    if len(eligible) == 1:
        recommendation = eligible[0]
        reason = "只有這個權重通過全部已鎖定的真實影像安全檢查。"
    elif len(eligible) == 0:
        recommendation = "unresolved"
        reason = "兩個權重都沒有通過全部已鎖定的真實影像安全檢查。"
    else:
        sem_winner = truth_winners["SEM"]
        hard_winner = truth_winners["R74_hard_microscopy"]
        if sem_winner in eligible and sem_winner == hard_winner:
            recommendation = sem_winner
            reason = "SEM 真實輪廓與高難度顯微影像測試都指向同一個權重，而且兩個權重都通過真實影像安全檢查。"
        else:
            remaining = [winner for winner in truth_winners.values() if winner in eligible]
            counts = Counter(remaining)
            if counts and max(counts.values()) >= 3:
                recommendation = counts.most_common(1)[0][0]
                reason = "四組有真值的測試中至少三組指向同一個權重，而且兩個權重都通過真實影像安全檢查。"
            else:
                recommendation = "unresolved"
                reason = "高優先測試的結果互相衝突，依事先規則不能只憑看起來比較漂亮就選擇。"
    return {
        "eligible_checkpoints": eligible,
        "truth_arm_winners": truth_winners,
        "recommended_r79_checkpoint": recommendation,
        "selection_reason": reason,
        "selection_rule": CONFIG["selection_rule"],
    }


def display_image(axis: plt.Axes, image: np.ndarray, title: str) -> None:
    lo, hi = np.percentile(image, [0.5, 99.5])
    axis.imshow(image, cmap="gray", vmin=lo, vmax=hi)
    axis.set_title(title)
    axis.axis("off")


def configure_plot_font() -> None:
    font_path = Path(r"C:\Windows\Fonts\msjh.ttc")
    if font_path.is_file():
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
        plt.rcParams.update({"font.family": family, "axes.unicode_minus": False})


def overlay_contours(axis: plt.Axes, truth: np.ndarray, measured: np.ndarray) -> None:
    axis.contour(truth.astype(float), levels=[0.5], colors=["white"], linewidths=1.2)
    axis.contour(measured.astype(float), levels=[0.5], colors=["#ff3b30"], linewidths=0.9)


def make_figures(
    external: pd.DataFrame,
    external_family: pd.DataFrame,
    sem: pd.DataFrame,
    motion: pd.DataFrame,
    tile: pd.DataFrame,
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    configure_plot_font()
    plt.rcParams.update({"figure.dpi": 150, "font.size": 9})

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for axis, suite in zip(axes[0], CONFIG["external_acm_suites"]):
        frame = external.loc[external["suite"] == suite].set_index("method").loc[["Raw", *MODELS]]
        axis.bar(np.arange(3), frame["median_mean_boundary_distance_px"], color=[COLORS[name] for name in frame.index])
        axis.set_xticks(np.arange(3), frame.index)
        axis.set_title(f"{suite}: boundary distance (lower is better)")
    sem_frame = sem.set_index("method").loc[["Raw", *MODELS]]
    axes[1, 0].bar(np.arange(3), sem_frame["median_mean_boundary_distance_pitch_pct"], color=[COLORS[name] for name in sem_frame.index])
    axes[1, 0].set_xticks(np.arange(3), sem_frame.index)
    axes[1, 0].set_title("SEM 36 pillars: boundary distance (% pitch)")
    axes[1, 1].bar(np.arange(3), sem_frame["median_iou"], color=[COLORS[name] for name in sem_frame.index])
    axes[1, 1].set_xticks(np.arange(3), sem_frame.index)
    axes[1, 1].set_title("SEM 36 pillars: contour overlap (higher is better)")
    fig.suptitle("Truth-based contour comparison")
    fig.tight_layout()
    fig.savefig(FIGURES / "01_truth_based_summary.png", bbox_inches="tight")
    plt.close(fig)

    sequences = list(CONFIG["real_fov"]["sequences"])
    x = np.arange(len(sequences))
    width = 0.35
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for offset, model in enumerate(MODELS):
        frame = motion.loc[motion["method"] == model].set_index("sequence").loc[sequences]
        axes[0].bar(x + (offset - 0.5) * width, frame["median_difference_of_step"] * 100, width, label=model, color=COLORS[model])
        axes[1].bar(x + (offset - 0.5) * width, frame["p95_difference_of_step"] * 100, width, label=model, color=COLORS[model])
    axes[0].axhline(10, color="#9b2c2c", linestyle="--", linewidth=1)
    axes[1].axhline(25, color="#9b2c2c", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Median difference (% step)")
    axes[1].set_ylabel("P95 difference (% step)")
    axes[1].set_xticks(x, sequences, rotation=25, ha="right")
    axes[0].legend()
    axes[1].legend()
    fig.suptitle("Locked 301-frame motion preservation")
    fig.tight_layout()
    fig.savefig(FIGURES / "02_real_motion_summary.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for row, sequence in enumerate(("5x_0p5um", "5x_1um")):
        for model in MODELS:
            frame = tile.loc[(tile["sequence"] == sequence) & (tile["method"] == model)].sort_values("tile_size")
            axes[row, 0].plot(frame["tile_size"], frame["median_fine_detail_ratio"], marker="o", label=model, color=COLORS[model])
            axes[row, 1].plot(frame["tile_size"], frame["median_off_source_fraction"] * 100, marker="o", label=model, color=COLORS[model])
        axes[row, 0].set_title(f"{sequence}: fine-detail ratio")
        axes[row, 1].set_title(f"{sequence}: off-source edges (%)")
        axes[row, 0].legend()
        axes[row, 1].legend()
    axes[1, 0].set_xlabel("Tile size")
    axes[1, 1].set_xlabel("Tile size")
    fig.tight_layout()
    fig.savefig(FIGURES / "03_5x_tile_sensitivity.png", bbox_inches="tight")
    plt.close(fig)

    raw_root = Path(PROJECT_ROOT / CONFIG["real_fov"]["locked_raw_root"])
    selected = ["5x_0p5um", "20x_0p5um", "50x_0p5um"]
    fig, axes = plt.subplots(3, 3, figsize=(13, 10))
    for row, sequence in enumerate(selected):
        images = [
            read_gray(raw_root / sequence / "frame_0000.bmp"),
            read_gray(RECON / "real_tile1024" / "R79E23" / sequence / "frame_0000.bmp"),
            read_gray(RECON / "real_tile1024" / "R79E100" / sequence / "frame_0000.bmp"),
        ]
        for column, (image, label) in enumerate(zip(images, ["Raw", "R79E23", "R79E100"])):
            display_image(axes[row, column], image, f"{sequence} | {label}")
    fig.suptitle("Fixed first frame; no visual cherry-picking")
    fig.tight_layout()
    fig.savefig(FIGURES / "04_fixed_real_contact_sheet.png", bbox_inches="tight")
    plt.close(fig)

    for suite, item in CONFIG["external_acm_suites"].items():
        source_config = json.loads(Path(PROJECT_ROOT / item["source_config"]).read_text(encoding="utf-8"))
        data_root = Path(PROJECT_ROOT / item["dataset_root"])
        families = source_config["dataset"]["families"]
        fig, axes = plt.subplots(len(families), 3, figsize=(12, 3 * len(families)))
        for row, family in enumerate(families):
            stage = family["stage"]
            images = [
                read_gray(data_root / "src" / stage / "0000.bmp"),
                read_gray(RECON / "external" / suite / "R79E23" / stage / "0000.bmp"),
                read_gray(RECON / "external" / suite / "R79E100" / stage / "0000.bmp"),
            ]
            for column, (image, label) in enumerate(zip(images, ["Raw", "R79E23", "R79E100"])):
                display_image(axes[row, column], image, f"{family['label_tw']} | {label}")
        fig.suptitle(f"{suite}: fixed image 0000 from every family")
        fig.tight_layout()
        fig.savefig(FIGURES / f"05_{suite}_fixed_examples.png", bbox_inches="tight")
        plt.close(fig)

    sem_raw = Path(PROJECT_ROOT / CONFIG["sem_acm"]["raw_input_dir"]) / "18.bmp"
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    images = [read_gray(sem_raw), read_gray(RECON / "sem" / "R79E23" / "18.bmp"), read_gray(RECON / "sem" / "R79E100" / "18.bmp")]
    for axis, image, label in zip(axes, images, ["Raw", "R79E23", "R79E100"]):
        display_image(axis, image, f"SEM-paired optical exposure 18 | {label}")
    fig.tight_layout()
    fig.savefig(FIGURES / "06_sem_paired_exposure18.png", bbox_inches="tight")
    plt.close(fig)

    r74_item = CONFIG["external_acm_suites"]["R74_hard_microscopy"]
    r74_config = json.loads(Path(PROJECT_ROOT / r74_item["source_config"]).read_text(encoding="utf-8"))
    r74_families = r74_config["dataset"]["families"]
    r74_masks = loadmat(
        RESULTS / "acm_external" / "R74_hard_microscopy" / "results" / "masks" / "acm_primary_masks.mat",
        variable_names=["exact_masks", "raw_masks", "e23_masks", "e100_masks"],
    )
    fig, axes = plt.subplots(len(r74_families), 3, figsize=(12, 3 * len(r74_families)))
    for row, family in enumerate(r74_families):
        index = row * int(r74_config["dataset"]["images_per_family"])
        stage = family["stage"]
        images = [
            read_gray(Path(PROJECT_ROOT / r74_item["dataset_root"]) / "src" / stage / "0000.bmp"),
            read_gray(RECON / "external" / "R74_hard_microscopy" / "R79E23" / stage / "0000.bmp"),
            read_gray(RECON / "external" / "R74_hard_microscopy" / "R79E100" / stage / "0000.bmp"),
        ]
        masks = [r74_masks["raw_masks"][:, :, index], r74_masks["e23_masks"][:, :, index], r74_masks["e100_masks"][:, :, index]]
        truth = r74_masks["exact_masks"][:, :, index]
        for column, (image, mask, label) in enumerate(zip(images, masks, ["Raw", "R79E23", "R79E100"])):
            display_image(axes[row, column], image, f"{family['label_tw']} | {label}\n白：真值；紅：辨識輪廓")
            overlay_contours(axes[row, column], truth, mask)
    fig.suptitle("R74 高難度顯微影像：固定案例的輪廓檢查")
    fig.tight_layout()
    fig.savefig(FIGURES / "07_R74_acm_contour_overlays.png", bbox_inches="tight")
    plt.close(fig)

    sem_e23 = loadmat(
        RESULTS / "acm_sem" / "R79E23" / "results" / "masks" / "acm_primary_masks.mat",
        variable_names=["truth_cells", "truth_masks", "raw_cells", "raw_masks", "recon_cells", "recon_masks"],
    )
    sem_e100 = loadmat(
        RESULTS / "acm_sem" / "R79E100" / "results" / "masks" / "acm_primary_masks.mat",
        variable_names=["recon_cells", "recon_masks"],
    )
    exposure_index = 5
    pillar_indices = [0, 17, 35]
    fig, axes = plt.subplots(len(pillar_indices), 3, figsize=(10, 9))
    for row, pillar_index in enumerate(pillar_indices):
        truth = sem_e23["truth_masks"][:, :, pillar_index]
        images = [
            sem_e23["raw_cells"][:, :, pillar_index, exposure_index],
            sem_e23["recon_cells"][:, :, pillar_index, exposure_index],
            sem_e100["recon_cells"][:, :, pillar_index, exposure_index],
        ]
        masks = [
            sem_e23["raw_masks"][:, :, pillar_index, exposure_index],
            sem_e23["recon_masks"][:, :, pillar_index, exposure_index],
            sem_e100["recon_masks"][:, :, pillar_index, exposure_index],
        ]
        for column, (image, mask, label) in enumerate(zip(images, masks, ["Raw", "R79E23", "R79E100"])):
            display_image(axes[row, column], image, f"柱 {pillar_index + 1} | {label}\n白：SEM；紅：辨識輪廓")
            overlay_contours(axes[row, column], truth, mask)
    fig.suptitle("SEM 配對柱：固定曝光與固定柱的輪廓檢查")
    fig.tight_layout()
    fig.savefig(FIGURES / "08_sem_acm_contour_overlays.png", bbox_inches="tight")
    plt.close(fig)


def write_report(
    audit: dict,
    internal: pd.DataFrame,
    internal_result: dict,
    external: pd.DataFrame,
    external_family: pd.DataFrame,
    external_result: dict,
    sem: pd.DataFrame,
    sem_result: dict,
    motion: pd.DataFrame,
    tile: pd.DataFrame,
    real_result: dict,
    selection: dict,
) -> None:
    recommendation = selection["recommended_r79_checkpoint"]
    if recommendation == "unresolved":
        headline = "目前不能乾淨地只選一個權重；第 23 輪與第 100 輪在高優先真值測試上互有勝負。"
    else:
        headline = f"依照事先鎖定的規則，目前較適合當 R79 主候選的是 {recommendation}。"
    internal_all = internal.loc[internal["training_role"] == "ALL"].set_index("model")
    sem_index = sem.set_index("method")
    lines = [
        "# R80：R79 第 23 輪與第 100 輪擴大驗證",
        "",
        "## 結論先行",
        "",
        headline,
        "",
        f"這次完整比較 {audit['internal_test']['images']} 張未參與訓練的內部形狀、{audit['real_fov']['total_frames']} 張真實顯微連續影像、200 張外部合成顯微形狀，以及 {audit['sem_acm']['physical_pillars']} 顆有 SEM 真實輪廓的柱。兩個權重使用完全相同的影像、分塊與輪廓設定。",
        "",
        f"- 真實影像安全檢查：第 23 輪通過 {real_result['models']['R79E23']['passed_sequences']}/6 組；第 100 輪通過 {real_result['models']['R79E100']['passed_sequences']}/6 組。",
        f"- SEM 輪廓判定：{sem_result['winner']}；第 23 輪的邊界距離中位數為 {sem_index.loc['R79E23', 'median_mean_boundary_distance_pitch_pct']:.4f}% 柱距，第 100 輪為 {sem_index.loc['R79E100', 'median_mean_boundary_distance_pitch_pct']:.4f}% 柱距。",
        f"- 高難度合成顯微輪廓判定：{external_result['R74_hard_microscopy']['winner_by_worst_family_boundary_distance']}。",
        f"- 內部保留形狀判定：{internal_result['winner_by_worst_role_mae']}；第 23 輪整體 MAE 為 {internal_all.loc['R79E23', 'median_mae']:.5f}，第 100 輪為 {internal_all.loc['R79E100', 'median_mae']:.5f}。",
        "",
        "![真值輪廓總覽](../results/figures/01_truth_based_summary.png)",
        "",
        "## 301 張真實顯微影像",
        "",
        "| 影像組 | 權重 | 可用比例 | 中位位移差 | P95 位移差 | 結果 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for _, row in motion.sort_values(["sequence", "method"]).iterrows():
        passed = str(row["sequence_pass"]).lower() == "true"
        lines.append(
            f"| {row['sequence']} | {row['method']} | {row['valid_fraction']:.1%} | "
            f"{row['median_difference_of_step']:.2%} | {row['p95_difference_of_step']:.2%} | {'通過' if passed else '未通過'} |"
        )
    lines += [
        "",
        "![真實影像位移保持](../results/figures/02_real_motion_summary.png)",
        "",
        "5×影像另外以 512 與 1024 兩種分塊完整重跑 100 張。這裡用來確認細節保留或假邊緣不是單一分塊設定造成。",
        "",
        "![5×分塊敏感度](../results/figures/03_5x_tile_sensitivity.png)",
        "",
        "![固定真實影像對照](../results/figures/04_fixed_real_contact_sheet.png)",
        "",
        "## 外部合成影像的 ACM 完整輪廓",
        "",
        "| 測試組 | 方法 | 輪廓重疊 | 平均邊界距離 | 周長誤差 |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in external.sort_values(["suite", "method"]).iterrows():
        lines.append(
            f"| {row['suite']} | {row['method']} | {row['median_iou']:.4f} | "
            f"{row['median_mean_boundary_distance_px']:.4f} px | {row['median_perimeter_error_pct']:.3f}% |"
        )
    lines += [
        "",
        "這 200 張有精確形狀答案，ACM 只允許平移對準，不允許縮放或旋轉。R73 與 R74 的失敗模式曾影響 R79 資料設計，因此本段是擴大開發驗證，不是全新盲測。",
        "",
        "要特別注意：在 R74 的 100 張低對比、光線不均、光暈與邊界消失影像中，兩個 R79 權重都比原圖差；第 23 輪只是受損較少。這表示 R79 還不能宣稱任何顯微場景都適用。",
        "",
        "![R73 固定案例](../results/figures/05_R73_expanded_shapes_fixed_examples.png)",
        "",
        "![R74 固定案例](../results/figures/05_R74_hard_microscopy_fixed_examples.png)",
        "",
        "![R74 輪廓疊圖](../results/figures/07_R74_acm_contour_overlays.png)",
        "",
        "## SEM 真實輪廓",
        "",
        "| 方法 | 獨立柱數 | 輪廓重疊 | 平均邊界距離（柱距 %） | 面積誤差 | 周長誤差 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in sem.iterrows():
        lines.append(
            f"| {row['method']} | {int(row['independent_pillars'])} | {row['median_iou']:.4f} | "
            f"{row['median_mean_boundary_distance_pitch_pct']:.4f} | {row['median_area_error_pct']:.3f}% | "
            f"{row['median_perimeter_error_pct']:.3f}% |"
        )
    lines += [
        "",
        "36 顆柱才是獨立樣本；12 個曝光是同一批柱的重複觀察。每顆柱先跨曝光取中位數，再統整 36 顆，避免把曝光重複當成更多樣本。",
        "",
        "![SEM 配對影像](../results/figures/06_sem_paired_exposure18.png)",
        "",
        "![SEM 輪廓疊圖](../results/figures/08_sem_acm_contour_overlays.png)",
        "",
        "## 判定界線",
        "",
        f"最後建議：**{recommendation}**。{selection['selection_reason']}",
        "",
        "這份結果可以用來決定 R79 內部採用第 23 輪還是第 100 輪，但不能保證任何未來樣品、材質或顯微鏡都一定適用，也不會自動改寫專案正式基準。",
        "",
        "完整逐張數值、輸入核對、輪廓表與執行狀態都保存在同一個 R80 資料夾，來源資料與 R79 權重沒有被修改。",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
    internal, internal_result = internal_decision()
    external, external_family, external_result = external_summary()
    sem, sem_per_pillar, sem_result = sem_summary()
    motion, tile, fidelity, real_result = real_decision()
    selection = choose_checkpoint(sem_result, external_result, internal_result, real_result)
    decision = {
        "status": "complete",
        "coverage": {
            "internal_test_images": audit["internal_test"]["images"],
            "real_frames": audit["real_fov"]["total_frames"],
            "real_sequences": 6,
            "external_acm_images": 200,
            "sem_physical_pillars": audit["sem_acm"]["physical_pillars"],
            "sem_repeated_exposures": 12,
        },
        "data_quality": {
            "input_audit_passed": audit["status"] == "pass",
            "real_exact_duplicate_frame_count": audit["real_fov"]["exact_duplicate_frame_count"],
            "external_cross_suite_exact_duplicate_groups": audit["external_acm_suites"]["cross_suite_exact_duplicate_groups"],
            "same_inputs_and_settings": True,
        },
        "internal_test": internal_result,
        "external_acm": external_result,
        "sem_acm": sem_result,
        "real_fov": real_result,
        "selection": selection,
        "claim_boundary": CONFIG["selection_rule"]["promotion_boundary"],
    }
    write_json(RESULTS / "decision.json", decision)
    make_figures(external, external_family, sem, motion, tile)
    write_report(
        audit, internal, internal_result, external, external_family, external_result,
        sem, sem_result, motion, tile, real_result, selection,
    )
    print(json.dumps(decision["selection"], ensure_ascii=False, indent=2), flush=True)
    print(f"REPORT: {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
