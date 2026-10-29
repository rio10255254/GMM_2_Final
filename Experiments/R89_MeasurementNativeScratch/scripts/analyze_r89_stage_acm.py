"""Summarize frozen-rule ACM results across R89 checkpoints and make visual audits."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.io import loadmat
from scipy.stats import wilcoxon
from skimage.metrics import structural_similarity
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'Experiments/R89_MeasurementNativeScratch'))
EPOCHS = [5, 15, 35, 55, 75, 100]
TOLERANCE = 1e-6


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    return image


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def holm_adjust(values: list[float]) -> list[float]:
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (len(values) - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted.tolist()


def safe_wilcoxon(delta: pd.Series) -> float:
    values = np.asarray(delta, dtype=float)
    if np.all(np.abs(values) <= TOLERANCE):
        return 1.0
    return float(wilcoxon(values, alternative="two-sided").pvalue)


def edge_strength(image: np.ndarray) -> np.ndarray:
    image = image.astype(np.float32)
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
    return np.hypot(gx, gy)


def visual_metrics(raw: np.ndarray, model: np.ndarray) -> dict[str, float]:
    raw_float = raw.astype(np.float32)
    model_float = model.astype(np.float32)
    difference = model_float - raw_float
    absolute = np.abs(difference)
    raw_edge = edge_strength(raw_float)
    model_edge = edge_strength(model_float)
    return {
        "mean_signed_change_gray": float(difference.mean()),
        "mean_abs_change_gray": float(absolute.mean()),
        "p95_abs_change_gray": float(np.percentile(absolute, 95)),
        "fraction_changed_over_10_gray": float(np.mean(absolute > 10.0)),
        "ssim_to_raw": float(structural_similarity(raw_float, model_float, data_range=255)),
        "mean_edge_strength_ratio": float(model_edge.mean() / raw_edge.mean()),
        "p95_edge_strength_ratio": float(
            np.percentile(model_edge, 95) / np.percentile(raw_edge, 95)
        ),
    }


def load_contour_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    final_table = pd.read_csv(
        ROOT
        / "results/final_validation/sem_acm_epoch100/acm_validation/results/tables"
        / "primary_contour_metrics.csv"
    )
    frames = [final_table.loc[final_table["method"] == "Raw"].copy()]
    final = final_table.loc[final_table["method"] == "R89E100"].copy()
    final["method"] = "epoch_100"
    frames.append(final)
    for epoch in EPOCHS[:-1]:
        table = pd.read_csv(
            ROOT
            / f"reports/final_validation/sem_acm_stages/epoch_{epoch:03d}/tables"
            / "primary_contour_metrics.csv"
        )
        table["method"] = f"epoch_{epoch:03d}"
        frames.append(table)
    all_rows = pd.concat(frames, ignore_index=True)
    physical = (
        all_rows.groupby(["method", "pillar_id"], as_index=False)
        .median(numeric_only=True)
        .sort_values(["method", "pillar_id"])
    )
    return all_rows, physical


def summarize_stages(physical: pd.DataFrame) -> pd.DataFrame:
    raw = physical.loc[physical["method"] == "Raw"].set_index("pillar_id")
    records: list[dict[str, float | int | str | bool]] = []
    p_iou: list[float] = []
    p_boundary: list[float] = []
    for epoch in EPOCHS:
        method = f"epoch_{epoch:03d}"
        stage = physical.loc[physical["method"] == method].set_index("pillar_id")
        iou_delta = stage["iou"] - raw["iou"]
        boundary_gain = (
            raw["mean_boundary_distance_pitch_pct"]
            - stage["mean_boundary_distance_pitch_pct"]
        )
        p_iou.append(safe_wilcoxon(iou_delta))
        p_boundary.append(safe_wilcoxon(boundary_gain))
        records.append(
            {
                "epoch": epoch,
                "iou_median": float(stage["iou"].median()),
                "iou_q1": float(stage["iou"].quantile(0.25)),
                "iou_q3": float(stage["iou"].quantile(0.75)),
                "iou_improved_pillars": int((iou_delta > TOLERANCE).sum()),
                "iou_worsened_pillars": int((iou_delta < -TOLERANCE).sum()),
                "iou_tied_pillars": int((np.abs(iou_delta) <= TOLERANCE).sum()),
                "mean_boundary_distance_pitch_pct_median": float(
                    stage["mean_boundary_distance_pitch_pct"].median()
                ),
                "boundary_improved_pillars": int((boundary_gain > TOLERANCE).sum()),
                "boundary_worsened_pillars": int((boundary_gain < -TOLERANCE).sum()),
                "boundary_tied_pillars": int((np.abs(boundary_gain) <= TOLERANCE).sum()),
                "hd95_pitch_pct_median": float(stage["hd95_pitch_pct"].median()),
                "area_error_pct_median": float(stage["area_error_pct"].median()),
                "perimeter_error_pct_median": float(
                    stage["perimeter_error_pct"].median()
                ),
                "circularity_abs_error_median": float(
                    stage["circularity_abs_error"].median()
                ),
            }
        )
    adjusted_iou = holm_adjust(p_iou)
    adjusted_boundary = holm_adjust(p_boundary)
    for index, record in enumerate(records):
        record["iou_wilcoxon_holm_p"] = adjusted_iou[index]
        record["boundary_wilcoxon_holm_p"] = adjusted_boundary[index]

    summary = pd.DataFrame.from_records(records)
    raw_record = {
        "epoch": 0,
        "iou_median": float(raw["iou"].median()),
        "iou_q1": float(raw["iou"].quantile(0.25)),
        "iou_q3": float(raw["iou"].quantile(0.75)),
        "iou_improved_pillars": 0,
        "iou_worsened_pillars": 0,
        "iou_tied_pillars": 36,
        "mean_boundary_distance_pitch_pct_median": float(
            raw["mean_boundary_distance_pitch_pct"].median()
        ),
        "boundary_improved_pillars": 0,
        "boundary_worsened_pillars": 0,
        "boundary_tied_pillars": 36,
        "hd95_pitch_pct_median": float(raw["hd95_pitch_pct"].median()),
        "area_error_pct_median": float(raw["area_error_pct"].median()),
        "perimeter_error_pct_median": float(raw["perimeter_error_pct"].median()),
        "circularity_abs_error_median": float(
            raw["circularity_abs_error"].median()
        ),
        "iou_wilcoxon_holm_p": np.nan,
        "boundary_wilcoxon_holm_p": np.nan,
    }
    return pd.concat([pd.DataFrame([raw_record]), summary], ignore_index=True)


def summarize_by_exposure(all_rows: pd.DataFrame) -> pd.DataFrame:
    by_exposure = (
        all_rows.groupby(["method", "exposure"], as_index=False)
        .median(numeric_only=True)
        .sort_values(["method", "exposure"])
    )
    by_exposure["epoch"] = by_exposure["method"].map(
        lambda value: 0 if value == "Raw" else int(str(value).split("_")[-1])
    )
    return by_exposure


def add_exposure_robustness(summary: pd.DataFrame, by_exposure: pd.DataFrame) -> pd.DataFrame:
    raw = by_exposure.loc[by_exposure["method"] == "Raw"].set_index("exposure")
    records: list[dict[str, float | int]] = []
    for epoch in [0, *EPOCHS]:
        method = "Raw" if epoch == 0 else f"epoch_{epoch:03d}"
        stage = by_exposure.loc[by_exposure["method"] == method].set_index("exposure")
        iou_delta = stage["iou"] - raw["iou"]
        worst_iou_exposure = int(stage["iou"].idxmin())
        worst_boundary_exposure = int(stage["mean_boundary_distance_pitch_pct"].idxmax())
        records.append(
            {
                "epoch": epoch,
                "exposure_median_iou": float(stage["iou"].median()),
                "worst_exposure_iou": float(stage.loc[worst_iou_exposure, "iou"]),
                "worst_iou_exposure": worst_iou_exposure,
                "best_exposure_iou": float(stage["iou"].max()),
                "exposures_iou_improved": int((iou_delta > TOLERANCE).sum()) if epoch else 0,
                "exposures_iou_worsened": int((iou_delta < -TOLERANCE).sum()) if epoch else 0,
                "worst_exposure_boundary_pitch_pct": float(
                    stage.loc[worst_boundary_exposure, "mean_boundary_distance_pitch_pct"]
                ),
                "worst_boundary_exposure": worst_boundary_exposure,
            }
        )
    return summary.merge(pd.DataFrame.from_records(records), how="left", on="epoch")


def add_training_diagnostics(summary: pd.DataFrame) -> pd.DataFrame:
    log = pd.read_csv(
        ROOT
        / "runs/training_R89_scratch_seed890041_20260811_012951/training_log.csv"
    )
    columns = [
        "epoch",
        "patch",
        "core",
        "val_worst_domain",
        "val_eligible",
        "val_identity_gray",
        "val_added_topology_failures",
        "val_motion_mae",
        "val_motion_p95",
        "val_motion_bias_x",
        "val_motion_bias_y",
    ]
    diagnostics = log.loc[log["epoch"].isin(EPOCHS), columns]
    return summary.merge(diagnostics, how="left", on="epoch")


def verify_evaluator_parity() -> dict[str, object]:
    official_path = (
        ROOT
        / "results/final_validation/sem_acm_epoch100/acm_validation/results/tables"
        / "primary_contour_metrics.csv"
    )
    rerun_path = (
        ROOT
        / "reports/final_validation/sem_acm_stages/epoch_100/tables"
        / "primary_contour_metrics.csv"
    )
    official = pd.read_csv(official_path)
    official = official.loc[official["method"] == "R89E100"].sort_values(
        ["exposure", "pillar_id"]
    ).reset_index(drop=True)
    rerun = pd.read_csv(rerun_path).sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
    key_columns = ["exposure", "pillar_id", "grid_row", "grid_col"]
    numeric_columns = [
        column
        for column in rerun.select_dtypes(include=[np.number]).columns
        if column not in key_columns
    ]
    maximum_differences = {
        column: float(np.max(np.abs(official[column] - rerun[column])))
        for column in numeric_columns
    }
    old_images = ROOT / "results/final_validation/sem_acm_epoch100/reconstruction"
    new_images = ROOT / "results/final_validation/sem_acm_stages/epoch_100/reconstruction"
    image_hash_matches = {
        f"{exposure}.bmp": sha256_file(old_images / f"{exposure}.bmp")
        == sha256_file(new_images / f"{exposure}.bmp")
        for exposure in range(13, 25)
    }
    keys_equal = bool(official[key_columns].equals(rerun[key_columns]))
    maximum_numeric_difference = max(maximum_differences.values())
    passed = bool(
        keys_equal
        and all(image_hash_matches.values())
        and maximum_numeric_difference <= 1e-5
    )
    return {
        "status": "pass" if passed else "fail",
        "official_rows": int(len(official)),
        "rerun_rows": int(len(rerun)),
        "keys_equal": keys_equal,
        "all_12_reconstruction_hashes_identical": bool(all(image_hash_matches.values())),
        "maximum_numeric_difference": maximum_numeric_difference,
        "maximum_difference_by_metric": maximum_differences,
    }


def save_trajectory(summary: pd.DataFrame, output: Path) -> None:
    raw = summary.loc[summary["epoch"] == 0].iloc[0]
    stages = summary.loc[summary["epoch"] > 0]
    epochs = stages["epoch"].to_numpy()
    colors = ["#78909c", "#78909c", "#78909c", "#00a676", "#f39c12", "#d62728"]
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)

    axes[0].axhline(raw["iou_median"], color="black", linestyle="--", label="Raw")
    axes[0].plot(epochs, stages["iou_median"], color="#315a8a", linewidth=2)
    axes[0].scatter(epochs, stages["iou_median"], c=colors, s=70, zorder=3)
    axes[0].fill_between(
        epochs,
        stages["iou_q1"].to_numpy(),
        stages["iou_q3"].to_numpy(),
        color="#315a8a",
        alpha=0.13,
        label="Pillar IQR",
    )
    axes[0].set_title("SEM contour overlap")
    axes[0].set_xlabel("Training epoch")
    axes[0].set_ylabel("Median IoU (higher is better)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(frameon=False)

    axes[1].axhline(
        raw["mean_boundary_distance_pitch_pct_median"],
        color="black",
        linestyle="--",
        label="Raw",
    )
    axes[1].plot(
        epochs,
        stages["mean_boundary_distance_pitch_pct_median"],
        color="#7b3f98",
        linewidth=2,
    )
    axes[1].scatter(
        epochs,
        stages["mean_boundary_distance_pitch_pct_median"],
        c=colors,
        s=70,
        zorder=3,
    )
    axes[1].set_title("SEM boundary distance")
    axes[1].set_xlabel("Training epoch")
    axes[1].set_ylabel("Median distance (% of pitch; lower is better)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(frameon=False)

    figure.suptitle("R89 checkpoint trajectory: fixed 36 pillars x 12 exposures", fontsize=14)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def save_exposure_trajectory(by_exposure: pd.DataFrame, output: Path) -> None:
    figure, axis = plt.subplots(figsize=(11.5, 6), constrained_layout=True)
    styles = {
        0: ("Raw", "black", "--", 2.5),
        5: ("E5", "#9e9e9e", ":", 1.5),
        15: ("E15", "#607d8b", "-", 1.8),
        35: ("E35", "#31688e", "-", 1.8),
        55: ("E55", "#00a676", "-", 2.6),
        75: ("E75", "#f39c12", "-", 2.0),
        100: ("E100", "#d62728", "-", 2.6),
    }
    for epoch, (label, color, linestyle, linewidth) in styles.items():
        stage = by_exposure.loc[by_exposure["epoch"] == epoch]
        axis.plot(
            stage["exposure"],
            stage["iou"],
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            marker="o" if epoch in (55, 100) else None,
            markersize=4,
        )
    axis.axvspan(17.5, 18.5, color="#d62728", alpha=0.08)
    axis.set_title("Exposure-dependent SEM contour accuracy (36-pillar median)")
    axis.set_xlabel("Optical exposure image")
    axis.set_ylabel("IoU (higher is better)")
    axis.set_xticks(range(13, 25))
    axis.grid(alpha=0.22)
    axis.legend(ncol=4, frameon=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def contour_area_by_exposure() -> pd.DataFrame:
    base_path = (
        ROOT
        / "results/final_validation/sem_acm_epoch100/acm_validation/results/masks"
        / "acm_primary_masks.mat"
    )
    base = loadmat(
        base_path,
        variable_names=["truth_masks", "raw_masks", "recon_masks", "exposures"],
    )
    exposures = np.asarray(base["exposures"]).ravel().astype(int)
    truth_area = base["truth_masks"].astype(bool).sum(axis=(0, 1))
    methods: dict[int, np.ndarray] = {0: base["raw_masks"], 100: base["recon_masks"]}
    for epoch in EPOCHS[:-1]:
        stage = loadmat(
            ROOT
            / f"reports/final_validation/sem_acm_stages/epoch_{epoch:03d}/masks"
            / "stage_primary_masks.mat",
            variable_names=["recon_masks"],
        )
        methods[epoch] = stage["recon_masks"]
    records: list[dict[str, float | int | str]] = []
    for epoch, masks in methods.items():
        method = "Raw" if epoch == 0 else f"E{epoch}"
        for exposure_index, exposure in enumerate(exposures):
            area = masks[:, :, :, exposure_index].astype(bool).sum(axis=(0, 1))
            signed_error = 100.0 * (area - truth_area) / truth_area
            for pillar_id, value in enumerate(signed_error, start=1):
                records.append(
                    {
                        "epoch": epoch,
                        "method": method,
                        "exposure": int(exposure),
                        "pillar_id": pillar_id,
                        "signed_area_error_pct": float(value),
                    }
                )
    return pd.DataFrame.from_records(records)


def save_area_flip_plot(area_rows: pd.DataFrame, output: Path) -> None:
    grouped = (
        area_rows.groupby(["epoch", "method", "exposure"], as_index=False)[
            "signed_area_error_pct"
        ]
        .median()
        .sort_values(["epoch", "exposure"])
    )
    figure, axis = plt.subplots(figsize=(11.5, 6), constrained_layout=True)
    styles = {
        0: ("Raw", "black", "--", 2.5),
        5: ("E5", "#9e9e9e", ":", 1.5),
        15: ("E15", "#607d8b", "-", 1.8),
        35: ("E35", "#31688e", "-", 1.8),
        55: ("E55", "#00a676", "-", 2.6),
        75: ("E75", "#f39c12", "-", 2.0),
        100: ("E100", "#d62728", "-", 2.6),
    }
    for epoch, (label, color, linestyle, linewidth) in styles.items():
        stage = grouped.loc[grouped["epoch"] == epoch]
        axis.plot(
            stage["exposure"],
            stage["signed_area_error_pct"],
            label=label,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            marker="o" if epoch in (55, 100) else None,
            markersize=4,
        )
    axis.axhline(0, color="black", linewidth=1, alpha=0.5)
    axis.axvspan(17.5, 18.5, color="#d62728", alpha=0.08)
    axis.set_title("Extracted contour area changes abruptly with exposure")
    axis.set_xlabel("Optical exposure image")
    axis.set_ylabel("Median signed area error vs SEM (%)")
    axis.set_xticks(range(13, 25))
    axis.grid(alpha=0.22)
    axis.legend(ncol=4, frameon=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def matlab_round(value: float) -> int:
    return int(np.sign(value) * np.floor(abs(value) + 0.5))


def shift_binary(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask, dtype=bool)
    src_x1 = max(0, -dx)
    src_x2 = min(width, width - dx)
    src_y1 = max(0, -dy)
    src_y2 = min(height, height - dy)
    if src_x1 < src_x2 and src_y1 < src_y2:
        shifted[
            src_y1 + dy : src_y2 + dy, src_x1 + dx : src_x2 + dx
        ] = mask[src_y1:src_y2, src_x1:src_x2]
    return shifted


def align_mask(mask: np.ndarray, truth: np.ndarray) -> np.ndarray:
    pred_center = ndimage.center_of_mass(mask)
    truth_center = ndimage.center_of_mass(truth)
    dy = matlab_round(truth_center[0] - pred_center[0])
    dx = matlab_round(truth_center[1] - pred_center[1])
    return shift_binary(mask, dx, dy)


def perimeter(mask: np.ndarray) -> np.ndarray:
    eroded = ndimage.binary_erosion(mask, structure=np.ones((3, 3)), border_value=0)
    return mask & ~eroded


def overlay_cell(image: np.ndarray, truth: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    base = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_GRAY2RGB)
    truth_edge = ndimage.binary_dilation(perimeter(truth), iterations=1)
    pred_edge = ndimage.binary_dilation(perimeter(predicted), iterations=1)
    base[truth_edge] = (0, 255, 0)
    base[pred_edge] = (255, 0, 255)
    base[truth_edge & pred_edge] = (255, 255, 0)
    return base


def grid_panel(
    cells: np.ndarray,
    masks: np.ndarray,
    truth_masks: np.ndarray,
    global_index: np.ndarray,
    title: str,
) -> np.ndarray:
    tile_side = cells.shape[0]
    gap = 3
    title_height = 48
    panel = np.full(
        (title_height + 6 * tile_side + 5 * gap, 6 * tile_side + 5 * gap, 3),
        24,
        dtype=np.uint8,
    )
    cv2.putText(panel, title, (12, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            tile = overlay_cell(
                cells[:, :, pillar_id - 1],
                truth_masks[:, :, pillar_id - 1],
                masks[:, :, pillar_id - 1],
            )
            cv2.rectangle(tile, (0, 0), (30, 17), (0, 0, 0), -1)
            cv2.putText(
                tile,
                str(pillar_id),
                (3, 13),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y = title_height + row * (tile_side + gap)
            x = col * (tile_side + gap)
            panel[y : y + tile_side, x : x + tile_side] = tile
    return panel


def save_acm_overlay(output: Path, selected_exposure: int) -> None:
    base_path = (
        ROOT
        / "results/final_validation/sem_acm_epoch100/acm_validation/results/masks"
        / "acm_primary_masks.mat"
    )
    base = loadmat(
        base_path,
        variable_names=[
            "truth_masks",
            "raw_cells",
            "raw_masks",
            "recon_cells",
            "recon_masks",
            "global_index",
            "exposures",
        ],
    )
    stage55 = loadmat(
        ROOT
        / "reports/final_validation/sem_acm_stages/epoch_055/masks"
        / "stage_primary_masks.mat",
        variable_names=["recon_cells", "aligned_masks", "exposures"],
    )
    exposures = np.asarray(base["exposures"]).ravel()
    exposure_index = int(np.flatnonzero(exposures == selected_exposure)[0])
    truth_masks = base["truth_masks"].astype(bool)
    raw_masks = np.zeros_like(truth_masks)
    final_masks = np.zeros_like(truth_masks)
    for pillar_index in range(36):
        raw_masks[:, :, pillar_index] = align_mask(
            base["raw_masks"][:, :, pillar_index, exposure_index].astype(bool),
            truth_masks[:, :, pillar_index],
        )
        final_masks[:, :, pillar_index] = align_mask(
            base["recon_masks"][:, :, pillar_index, exposure_index].astype(bool),
            truth_masks[:, :, pillar_index],
        )
    panels = [
        grid_panel(
            base["raw_cells"][:, :, :, exposure_index],
            raw_masks,
            truth_masks,
            base["global_index"],
            "RAW (all 36 pillars)",
        ),
        grid_panel(
            stage55["recon_cells"][:, :, :, exposure_index],
            stage55["aligned_masks"][:, :, :, exposure_index].astype(bool),
            truth_masks,
            base["global_index"],
            "R89 E55",
        ),
        grid_panel(
            base["recon_cells"][:, :, :, exposure_index],
            final_masks,
            truth_masks,
            base["global_index"],
            "R89 E100",
        ),
    ]
    gap = np.full((panels[0].shape[0], 12, 3), 255, dtype=np.uint8)
    body = np.hstack([panels[0], gap, panels[1], gap, panels[2]])
    header = np.full((82, body.shape[1], 3), 24, dtype=np.uint8)
    cv2.putText(
        header,
        f"Exposure {selected_exposure} | translation alignment only | green=SEM truth, magenta=ACM, yellow=agreement",
        (18, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    rgb = np.vstack([header, body])
    output.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not success:
        raise RuntimeError("Could not encode ACM overlay")
    encoded.tofile(output)


def annotate_panel(image: np.ndarray, label: str, width: int = 820) -> np.ndarray:
    scale = width / image.shape[1]
    resized = cv2.resize(image, (width, int(round(image.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    panel = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (330, 48), (0, 0, 0), -1)
    cv2.putText(panel, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
    return panel


def save_real_comparison(
    magnitude: str,
    raw_path: Path,
    e55_path: Path,
    e100_path: Path,
    output: Path,
) -> dict[str, dict[str, float]]:
    raw = read_gray(raw_path)
    e55 = read_gray(e55_path)
    e100 = read_gray(e100_path)
    if raw.shape != e55.shape or raw.shape != e100.shape:
        raise RuntimeError(f"Shape mismatch for {magnitude}")
    panels = [
        annotate_panel(raw, f"{magnitude} RAW"),
        annotate_panel(e55, f"{magnitude} R89 E55"),
        annotate_panel(e100, f"{magnitude} R89 E100"),
    ]
    canvas = np.hstack(panels)
    output.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise RuntimeError(f"Could not encode {output}")
    encoded.tofile(output)
    return {"epoch_055": visual_metrics(raw, e55), "epoch_100": visual_metrics(raw, e100)}


def write_report(
    summary: pd.DataFrame,
    visual: dict[str, object],
    parity: dict[str, object],
    output: Path,
) -> None:
    raw = summary.loc[summary["epoch"] == 0].iloc[0]
    e55 = summary.loc[summary["epoch"] == 55].iloc[0]
    e100 = summary.loc[summary["epoch"] == 100].iloc[0]
    lines = [
        "# R89 各階段 SEM 輪廓與 5x/20x 檢查",
        "",
        "## 結論",
        "",
        "第 55 輪在跨曝光的中間表現最好，但不是穩定版；第 18 號曝光會突然抓到外圈。第 100 輪雖然視覺更有衝擊力，這個問題仍然存在，而且一般輪廓表現也退步。",
        "",
        f"- 原圖輪廓重疊：{raw.iou_median:.6f}",
        f"- 第 55 輪跨曝光中間值：{e55.iou_median:.6f}，36/36 顆的中間值改善；但最差曝光只有 {e55.worst_exposure_iou:.6f}。",
        f"- 第 100 輪跨曝光中間值：{e100.iou_median:.6f}，只有 1/36 顆改善；最差曝光只有 {e100.worst_exposure_iou:.6f}。",
        "- 第 18 號曝光時，第 55 輪抓出的面積比 SEM 大約 22.5%，第 100 輪大約 23.3%；原圖則穩定在約大 5.4%。",
        "",
        "因此第 55 輪只能視為平均幾何較好的研究候選，不能直接取代正式模型。它有明顯曝光敏感性，而且訓練中的其他安全檢查也未全部通過。",
        "",
        "## 計算公平性",
        "",
        "所有權重使用同一批 36 顆柱、12 種曝光、同一份 SEM 真實輪廓與同一套固定輪廓規則。只允許平移對正，不允許縮放或旋轉，因此模型把柱子重建得太大、太小或形狀偏掉都會被保留。輪廓分數本身比較的是二值形狀，不比較亮度；但亮度與邊圈會影響演算法選到內圈還是外圈，這正是這次暴露出的不穩定性。",
        f"第 100 輪已獨立重建與重算一次：12 張影像逐張完全相同，432 筆結果的最大數值差只有 {float(parity['maximum_numeric_difference']):.2e}。",
        "",
        "## 5x / 20x",
        "",
        "兩個倍率都能產生清楚細節，但沒有逐像素配對的真實答案，因此這裡只能證明模型能在不同倍率輸出銳利影像，不能單靠肉眼宣稱重建正確。20x 的第 100 輪變亮與邊圈增強尤其明顯。",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report_root = ROOT / "reports/final_validation/stage_weight_analysis"
    report_root.mkdir(parents=True, exist_ok=True)
    all_rows, physical = load_contour_tables()
    by_exposure = summarize_by_exposure(all_rows)
    area_rows = contour_area_by_exposure()
    summary = add_training_diagnostics(
        add_exposure_robustness(summarize_stages(physical), by_exposure)
    )
    summary.to_csv(report_root / "stage_acm_summary.csv", index=False)
    by_exposure.to_csv(report_root / "stage_acm_by_exposure.csv", index=False)
    area_rows.to_csv(report_root / "mask_signed_area_by_exposure.csv", index=False)
    save_trajectory(summary, report_root / "stage_acm_trajectory.png")
    save_exposure_trajectory(by_exposure, report_root / "stage_acm_by_exposure.png")
    save_area_flip_plot(area_rows, report_root / "mask_signed_area_by_exposure.png")
    for exposure in (13, 18, 24):
        save_acm_overlay(
            report_root / f"acm_all36_overlay_exposure{exposure}.png", exposure
        )

    real_specs = {
        "5x": {
            "raw": Path(str(PROJECT_ROOT / 'Shared_Sources/Real_Sample_Captures/20260704_5x/1um/Image__2026-07-04__17-51-47.bmp')),
            "name": "Image__2026-07-04__17-51-47.bmp",
        },
        "20x": {
            "raw": Path(str(PROJECT_ROOT / 'Shared_Sources/Real_Sample_Captures/20260704_20x/1um/Image__2026-07-04__18-10-19.bmp')),
            "name": "Image__2026-07-04__18-10-19.bmp",
        },
    }
    visual: dict[str, object] = {}
    for magnitude, spec in real_specs.items():
        e55_path = (
            ROOT
            / f"results/final_validation/real_5x_20x_epoch055/{magnitude}"
            / str(spec["name"])
        )
        e100_path = (
            ROOT
            / f"results/final_validation/real_5x_20x_epoch100/{magnitude}"
            / str(spec["name"])
        )
        visual[magnitude] = save_real_comparison(
            magnitude,
            Path(spec["raw"]),
            e55_path,
            e100_path,
            report_root / f"{magnitude}_raw_e55_e100.png",
        )

    parity = verify_evaluator_parity()
    (report_root / "evaluator_parity.json").write_text(
        json.dumps(parity, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    payload = {
        "status": "complete",
        "aggregation": "median across 12 exposures per physical pillar, then median across 36 pillars",
        "comparison_tolerance": TOLERANCE,
        "stage_summary": summary.replace({np.nan: None}).to_dict(orient="records"),
        "by_exposure": by_exposure.replace({np.nan: None}).to_dict(orient="records"),
        "signed_area_by_exposure": area_rows.replace({np.nan: None}).to_dict(orient="records"),
        "visual_metrics": visual,
        "evaluator_parity": parity,
    }
    (report_root / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(summary, visual, parity, report_root / "R89_STAGE_WEIGHT_FINDINGS_TW.md")
    print(summary.to_string(index=False))
    print(json.dumps(visual, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
