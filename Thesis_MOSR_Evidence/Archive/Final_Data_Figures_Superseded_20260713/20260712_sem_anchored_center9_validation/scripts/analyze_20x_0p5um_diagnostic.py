from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\input_mapping.csv")
DEFAULT_CONFIG = PACKAGE / "config" / "sequence_center9.json"
DEFAULT_COMPARISON = PACKAGE / "displacement" / "tables" / "20x_0p5um_comparison.csv"
EDGE_PHASE_SUMMARY = Path(
    r"D:\GMM_2_Final\20260704_20x_5x_analysis\phase_algorithm_final_summary"
    r"\edge_phase_primary_gap30_summary_um.csv"
)


def _read_grayscale(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _subpixel_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left, center, right = (float(value) for value in values[index - 1 : index + 2])
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return float(index)
    offset = 0.5 * (left - right) / denominator
    return float(index) + float(np.clip(offset, -1.0, 1.0))


def _load_inputs(
    *, mapping_path: Path, config_path: Path, comparison_path: Path
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    mapping = pd.read_csv(mapping_path)
    mapping = mapping.loc[mapping["group"] == "20x_0p5um"].copy()
    mapping["frame_index"] = pd.to_numeric(mapping["index"], errors="raise").astype(int)
    mapping["timestamp"] = pd.to_datetime(mapping["timestamp"], errors="raise")
    mapping = mapping.sort_values("frame_index").reset_index(drop=True)
    if mapping["frame_index"].tolist() != list(range(50)):
        raise ValueError("20x 0.5 um mapping must contain frames 0..49 exactly once")
    gaps = mapping["timestamp"].diff().dt.total_seconds()
    if (gaps.dropna() <= 0).any():
        raise ValueError("timestamps must be strictly increasing")
    mapping["gap_from_previous_seconds"] = gaps

    config = json.loads(config_path.read_text(encoding="utf-8"))["sequences"][
        "20x_0p5um"
    ]
    comparison = pd.read_csv(comparison_path).sort_values("step_index").reset_index(
        drop=True
    )
    if comparison["step_index"].tolist() != list(range(1, 50)):
        raise ValueError("locked comparison must contain steps 1..49 exactly once")
    return mapping, config, comparison


def _track_local_templates(
    images: list[np.ndarray],
    centers: np.ndarray,
    *,
    expected_dx_px: float,
    object_um_per_px: float,
    template_half_size: int = 10,
    search_radius: int = 5,
) -> tuple[pd.DataFrame, list[np.ndarray]]:
    positions = centers.copy()
    positions_by_frame = [positions.copy()]
    records: list[dict[str, Any]] = []
    template_size = (2 * template_half_size + 1,) * 2
    search_size = (2 * (template_half_size + search_radius) + 1,) * 2
    for frame_index in range(1, len(images)):
        next_positions: list[np.ndarray] = []
        pillar_measurements: list[tuple[float, float, float]] = []
        for x_px, y_px in positions:
            template = cv2.getRectSubPix(
                images[frame_index - 1],
                template_size,
                (float(x_px), float(y_px)),
            )
            predicted = np.asarray([x_px + expected_dx_px, y_px], dtype=float)
            search = cv2.getRectSubPix(
                images[frame_index], search_size, tuple(predicted.astype(np.float32))
            )
            match = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, peak = cv2.minMaxLoc(match)
            refined_x = _subpixel_peak(match[peak[1], :], peak[0])
            refined_y = _subpixel_peak(match[:, peak[0]], peak[1])
            offset = np.asarray(
                [refined_x - search_radius, refined_y - search_radius], dtype=float
            )
            current = predicted + offset
            next_positions.append(current)
            pillar_measurements.append(
                (current[0] - x_px, current[1] - y_px, float(score))
            )
        measurement = np.asarray(pillar_measurements, dtype=float)
        dx_px = float(np.median(measurement[:, 0]))
        dy_px = float(np.median(measurement[:, 1]))
        records.append(
            {
                "step_index": frame_index,
                "dx_px": dx_px,
                "dy_px": dy_px,
                "dx_um": dx_px * object_um_per_px,
                "dy_um": dy_px * object_um_per_px,
                "median_match_score": float(np.median(measurement[:, 2])),
                "minimum_match_score": float(np.min(measurement[:, 2])),
                "pillar_dx_sd_nm": float(
                    np.std(measurement[:, 0], ddof=1) * object_um_per_px * 1000.0
                ),
                "pillar_dy_sd_nm": float(
                    np.std(measurement[:, 1], ddof=1) * object_um_per_px * 1000.0
                ),
            }
        )
        positions = np.asarray(next_positions, dtype=float)
        positions_by_frame.append(positions.copy())
    return pd.DataFrame(records), positions_by_frame


def _build_population_summary(steps: pd.DataFrame) -> pd.DataFrame:
    populations = {
        "all_49_steps": np.ones(len(steps), dtype=bool),
        "gap_at_most_30_seconds": steps["gap_seconds"].to_numpy() <= 30.0,
        "regular_cadence_at_most_10_seconds": steps["gap_seconds"].to_numpy()
        <= 10.0,
    }
    records: list[dict[str, Any]] = []
    for population, mask in populations.items():
        for case, prefix in (("Raw", "raw"), ("V42 epoch 120", "v42")):
            selected = steps.loc[mask]
            values = selected[f"{prefix}_locked_dx_um"].to_numpy(dtype=float)
            error = values + 0.5
            records.append(
                {
                    "population": population,
                    "timing_rule": {
                        "all_49_steps": "all adjacent pairs",
                        "gap_at_most_30_seconds": "timestamp gap <= 30 s",
                        "regular_cadence_at_most_10_seconds": "timestamp gap <= 10 s",
                    }[population],
                    "case": case,
                    "step_count": len(values),
                    "mean_signed_step_um": float(np.mean(values)),
                    "signed_step_sd_nm": float(np.std(values, ddof=1) * 1000.0),
                    "rmse_to_nominal_nm": float(np.sqrt(np.mean(error**2)) * 1000.0),
                    "mean_abs_error_nm": float(np.mean(np.abs(error)) * 1000.0),
                    "mean_within_grid_disagreement_nm": float(
                        selected[f"{prefix}_within_grid_nm"].mean()
                    ),
                }
            )
    result = pd.DataFrame(records)
    result["v42_sd_reduction_pct"] = np.nan
    for population in populations:
        rows = result["population"] == population
        indexed = result.loc[rows].set_index("case")
        raw_sd = float(indexed.loc["Raw", "signed_step_sd_nm"])
        v42_sd = float(indexed.loc["V42 epoch 120", "signed_step_sd_nm"])
        result.loc[rows, "v42_sd_reduction_pct"] = (raw_sd - v42_sd) / raw_sd * 100.0
    return result


def _plot_gap_motion(steps: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 8.2), sharex=True, constrained_layout=True)
    axes[0].bar(steps["step_index"], steps["gap_seconds"], color="#777777")
    axes[0].axhline(10, color="#222222", linestyle="--", label="Regular cadence limit (10 s)")
    axes[0].set_ylabel("Time gap (s)")
    axes[0].legend()
    axes[1].plot(steps["step_index"], steps["raw_local_dx_um"], color="#d62728", marker="s", ms=3, label="Raw")
    axes[1].plot(steps["step_index"], steps["v42_local_dx_um"], color="#1f77b4", marker="o", ms=3, label="V42")
    axes[1].axhline(-0.5, color="#222222", linestyle="--")
    axes[1].set_ylabel("Local 2D dx (um)")
    axes[1].legend()
    axes[2].plot(steps["step_index"], steps["raw_local_dy_um"], color="#d62728", marker="s", ms=3, label="Raw")
    axes[2].plot(steps["step_index"], steps["v42_local_dy_um"], color="#1f77b4", marker="o", ms=3, label="V42")
    axes[2].axhline(0, color="#222222", linestyle="--")
    axes[2].set_ylabel("Local 2D dy (um)")
    axes[2].set_xlabel("Step index")
    for axis in axes:
        axis.axvline(15, color="#9467bd", alpha=0.65)
        axis.axvline(45, color="#9467bd", alpha=0.45)
        axis.axvline(46, color="#9467bd", alpha=0.45)
        axis.grid(True, alpha=0.2)
    fig.suptitle("20x 0.5 um: long pauses coincide with abnormal 2D stage motion")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_step_trace(steps: pd.DataFrame, output_path: Path) -> None:
    fig, axis = plt.subplots(figsize=(11.2, 5.6), constrained_layout=True)
    axis.axhline(-0.5, color="#222222", linestyle="--", label="Nominal command (-0.5 um)")
    axis.plot(steps["step_index"], steps["raw_locked_dx_um"], color="#d62728", marker="s", ms=3.5, label="Raw")
    axis.plot(steps["step_index"], steps["v42_locked_dx_um"], color="#1f77b4", marker="o", ms=3.5, label="V42 epoch 120")
    pauses = steps["gap_seconds"] > 10
    axis.scatter(steps.loc[pauses, "step_index"], steps.loc[pauses, "raw_locked_dx_um"], s=95, facecolors="none", edgecolors="#111111", label="Gap > 10 s")
    axis.set_xlabel("Step index")
    axis.set_ylabel("Signed measured step (um)")
    axis.set_title("Locked center-nine boundary measurement, all 49 steps")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_correlation(steps: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), constrained_layout=True)
    for axis, x_col, y_col, title in (
        (axes[0], "raw_locked_dx_um", "v42_locked_dx_um", "Locked boundary method"),
        (axes[1], "raw_local_dx_um", "v42_local_dx_um", "Independent local 2D method"),
    ):
        axis.scatter(steps[x_col], steps[y_col], c=steps["gap_seconds"], cmap="viridis", s=42)
        low = min(float(steps[x_col].min()), float(steps[y_col].min())) - 0.02
        high = max(float(steps[x_col].max()), float(steps[y_col].max())) + 0.02
        axis.plot([low, high], [low, high], color="#222222", linestyle="--")
        axis.set_xlim(low, high)
        axis.set_ylim(low, high)
        axis.set_xlabel("Raw step (um)")
        axis.set_ylabel("V42 step (um)")
        axis.set_title(title)
        axis.grid(True, alpha=0.2)
    fig.suptitle("Raw and V42 reproduce the same stage-motion events")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_populations(summary: pd.DataFrame, output_path: Path) -> None:
    names = ["All 49", "Gap <= 30 s", "Gap <= 10 s"]
    populations = ["all_49_steps", "gap_at_most_30_seconds", "regular_cadence_at_most_10_seconds"]
    raw = summary.set_index(["population", "case"])
    raw_values = [raw.loc[(population, "Raw"), "signed_step_sd_nm"] for population in populations]
    v42_values = [raw.loc[(population, "V42 epoch 120"), "signed_step_sd_nm"] for population in populations]
    x = np.arange(len(populations))
    width = 0.36
    fig, axis = plt.subplots(figsize=(9.5, 5.5), constrained_layout=True)
    bars_raw = axis.bar(x - width / 2, raw_values, width, color="#d62728", label="Raw")
    bars_v42 = axis.bar(x + width / 2, v42_values, width, color="#1f77b4", label="V42 epoch 120")
    axis.bar_label(bars_raw, fmt="%.1f", padding=3)
    axis.bar_label(bars_v42, fmt="%.1f", padding=3)
    axis.set_xticks(x, names)
    axis.set_ylabel("Signed step standard deviation (nm)")
    axis.set_title("Timing-defined populations explain the apparent instability")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    axis.set_ylim(0, max(raw_values + v42_values) * 1.22)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_event(
    raw_images: list[np.ndarray],
    v42_images: list[np.ndarray],
    raw_positions: list[np.ndarray],
    v42_positions: list[np.ndarray],
    output_path: Path,
) -> None:
    def crop_pair(images: list[np.ndarray], positions: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        center = positions[14].mean(axis=0)
        size = (118, 118)
        return (
            cv2.getRectSubPix(images[14], size, tuple(center.astype(np.float32))),
            cv2.getRectSubPix(images[15], size, tuple(center.astype(np.float32))),
        )

    fig, axes = plt.subplots(2, 3, figsize=(10.5, 7.2), constrained_layout=True)
    for row, (label, images, positions) in enumerate(
        (("Raw", raw_images, raw_positions), ("V42", v42_images, v42_positions))
    ):
        before, after = crop_pair(images, positions)
        edges_before = cv2.Canny(before, 30, 90)
        edges_after = cv2.Canny(after, 30, 90)
        overlay = np.zeros((*before.shape, 3), dtype=np.uint8)
        overlay[..., 0] = edges_before
        overlay[..., 1] = edges_after
        overlay[..., 2] = edges_after
        axes[row, 0].imshow(before, cmap="gray")
        axes[row, 1].imshow(after, cmap="gray")
        axes[row, 2].imshow(overlay)
        axes[row, 0].set_ylabel(label)
        for axis in axes[row]:
            axis.set_xticks([])
            axis.set_yticks([])
    axes[0, 0].set_title("Frame 14")
    axes[0, 1].set_title("Frame 15 after 48 s gap")
    axes[0, 2].set_title("Edge overlay: red before, cyan after")
    fig.suptitle("Step 15 is a vertical repositioning event, not a normal x step")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _write_report(steps: pd.DataFrame, populations: pd.DataFrame, evidence: pd.DataFrame, path: Path) -> None:
    pop = populations.set_index(["population", "case"])
    ev = evidence.set_index("metric")["value"]
    report = f"""# 20x 0.5 um 位移異常診斷

## 結論

這組資料看起來有約 75 nm 的步距標準差，主因不是 V42 單獨產生不穩定，而是拍攝序列中包含平台沒有正常完成 X 位移、同時發生 Y 方向換位的事件。Raw 與 V42 的 49 步結果相關係數為 {ev['locked_raw_v42_step_correlation']:.3f}，使用另一套局部二維比對後仍為 {ev['local_raw_v42_step_correlation']:.3f}，兩種方法都看到相同異常。

## 最明顯事件

第 14 張至第 15 張之間停了 48 秒。正常命令是水平移動 0.5 um，但局部二維比對顯示 Raw 水平只移動 {abs(steps.set_index('step_index').loc[15, 'raw_local_dx_um']):.3f} um、垂直移動 {abs(steps.set_index('step_index').loc[15, 'raw_local_dy_um']):.3f} um；V42 也得到幾乎相同結果。第 45、46 步則呈現先不足、再補償的水平移動，且同時伴隨垂直偏移。

## 不同客觀母體

| 母體 | Raw 標準差 (nm) | V42 標準差 (nm) | 說明 |
|---|---:|---:|---|
| 全部 49 步 | {pop.loc[('all_49_steps', 'Raw'), 'signed_step_sd_nm']:.2f} | {pop.loc[('all_49_steps', 'V42 epoch 120'), 'signed_step_sd_nm']:.2f} | 正式完整結果，不刪任何步數 |
| 拍攝間隔不超過 30 秒 | {pop.loc[('gap_at_most_30_seconds', 'Raw'), 'signed_step_sd_nm']:.2f} | {pop.loc[('gap_at_most_30_seconds', 'V42 epoch 120'), 'signed_step_sd_nm']:.2f} | 僅排除 48 秒中斷，共 48 步 |
| 正常節奏，不超過 10 秒 | {pop.loc[('regular_cadence_at_most_10_seconds', 'Raw'), 'signed_step_sd_nm']:.2f} | {pop.loc[('regular_cadence_at_most_10_seconds', 'V42 epoch 120'), 'signed_step_sd_nm']:.2f} | 由時間條件定義，共 44 步 |

正常拍攝節奏下，V42 的標準差比 Raw 低 {pop.loc[('regular_cadence_at_most_10_seconds', 'Raw'), 'signed_step_sd_nm'] - pop.loc[('regular_cadence_at_most_10_seconds', 'V42 epoch 120'), 'signed_step_sd_nm']:.2f} nm；但完整 49 步仍應保留在稽核結果中。論文若呈現正常節奏子集，必須同時揭露時間門檻、排除的五個步數與完整結果，不能把它包裝成全部資料都改善。

## 方法交叉檢查

原本方法量測九顆圓柱的水平邊界；新增方法逐顆在二維影像中追蹤同一圓柱。兩種方法對 Raw 與 V42 的相關係數都高於 0.98。既有邊緣相位法在排除超過 30 秒的中斷後，Raw 標準差為 {ev['existing_edge_phase_gap30_raw_sd_nm']:.2f} nm，也與本次九圓柱方法的 {pop.loc[('gap_at_most_30_seconds', 'Raw'), 'signed_step_sd_nm']:.2f} nm 接近。

## 可支持的論文敘述

V42 在 20x 0.5 um 的完整序列中沒有降低整段步距標準差，但明顯降低九顆圓柱彼此的不一致。進一步檢查顯示完整標準差主要受長停頓後的平台二維換位支配；在正常拍攝節奏下，V42 才呈現小幅穩定性改善。平台命令仍只是名義參考，不是獨立位置真值。
"""
    path.write_text(report, encoding="utf-8")


def run_diagnostic(
    *,
    output_root: str | Path,
    mapping_path: str | Path = DEFAULT_MAPPING,
    config_path: str | Path = DEFAULT_CONFIG,
    comparison_path: str | Path = DEFAULT_COMPARISON,
) -> dict[str, Path]:
    output = Path(output_root)
    tables = output / "tables"
    figures = output / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    mapping, config, locked = _load_inputs(
        mapping_path=Path(mapping_path),
        config_path=Path(config_path),
        comparison_path=Path(comparison_path),
    )
    names = [f"frame_{index:04d}.bmp" for index in range(50)]
    raw_images = [_read_grayscale(Path(config["raw_dir"]) / name) for name in names]
    v42_images = [_read_grayscale(Path(config["v42_dir"]) / name) for name in names]
    centers = np.asarray([[row[1], row[2]] for row in config["centers"]], dtype=float)
    raw_local, raw_positions = _track_local_templates(
        raw_images,
        centers,
        expected_dx_px=float(config["expected_signed_dx_px"]),
        object_um_per_px=float(config["object_um_per_px"]),
    )
    v42_local, v42_positions = _track_local_templates(
        v42_images,
        centers,
        expected_dx_px=float(config["expected_signed_dx_px"]),
        object_um_per_px=float(config["object_um_per_px"]),
    )

    steps = pd.DataFrame(
        {
            "step_index": locked["step_index"],
            "start_frame_index": locked["step_index"] - 1,
            "end_frame_index": locked["step_index"],
            "start_timestamp": mapping["timestamp"].iloc[:-1].dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy(),
            "end_timestamp": mapping["timestamp"].iloc[1:].dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy(),
            "gap_seconds": mapping["gap_from_previous_seconds"].iloc[1:].to_numpy(),
            "raw_locked_dx_um": locked["consensus_dx_um_raw"],
            "v42_locked_dx_um": locked["consensus_dx_um_v42"],
            "raw_within_grid_nm": locked["within_grid_disagreement_nm_raw"],
            "v42_within_grid_nm": locked["within_grid_disagreement_nm_v42"],
            "raw_local_dx_um": raw_local["dx_um"],
            "v42_local_dx_um": v42_local["dx_um"],
            "raw_local_dy_um": raw_local["dy_um"],
            "v42_local_dy_um": v42_local["dy_um"],
            "raw_local_match_score": raw_local["median_match_score"],
            "v42_local_match_score": v42_local["median_match_score"],
            "raw_local_pillar_dx_sd_nm": raw_local["pillar_dx_sd_nm"],
            "v42_local_pillar_dx_sd_nm": v42_local["pillar_dx_sd_nm"],
        }
    )
    steps["timing_population"] = np.select(
        [steps["gap_seconds"] <= 10, steps["gap_seconds"] <= 30],
        ["regular_cadence", "extended_pause"],
        default="long_interruption",
    )
    populations = _build_population_summary(steps)

    edge_phase = pd.read_csv(EDGE_PHASE_SUMMARY)
    edge_raw = edge_phase.loc[
        (edge_phase["group"] == "20x_0p5um") & (edge_phase["image"] == "Raw")
    ]
    if len(edge_raw) != 1:
        raise ValueError("existing edge-phase Raw cross-check is not unique")
    evidence_values = {
        "locked_raw_v42_step_correlation": float(np.corrcoef(steps["raw_locked_dx_um"], steps["v42_locked_dx_um"])[0, 1]),
        "local_raw_v42_step_correlation": float(np.corrcoef(steps["raw_local_dx_um"], steps["v42_local_dx_um"])[0, 1]),
        "locked_vs_local_raw_correlation": float(np.corrcoef(steps["raw_locked_dx_um"], steps["raw_local_dx_um"])[0, 1]),
        "locked_vs_local_v42_correlation": float(np.corrcoef(steps["v42_locked_dx_um"], steps["v42_local_dx_um"])[0, 1]),
        "maximum_timestamp_gap_seconds": float(steps["gap_seconds"].max()),
        "timestamp_sessions_at_60_seconds": float(1 + np.sum(steps["gap_seconds"] > 60)),
        "correlation_gap_vs_abs_error_raw": float(np.corrcoef(steps["gap_seconds"], np.abs(steps["raw_locked_dx_um"] + 0.5))[0, 1]),
        "correlation_gap_vs_abs_error_v42": float(np.corrcoef(steps["gap_seconds"], np.abs(steps["v42_locked_dx_um"] + 0.5))[0, 1]),
        "locked_v42_minus_raw_sd_nm": float(np.std(steps["v42_locked_dx_um"] - steps["raw_locked_dx_um"], ddof=1) * 1000.0),
        "existing_edge_phase_gap30_raw_sd_nm": float(edge_raw.iloc[0]["std_step_um"] * 1000.0),
    }
    evidence = pd.DataFrame(
        [{"metric": metric, "value": value} for metric, value in evidence_values.items()]
    )

    paths = {
        "steps": tables / "all_49_steps_with_timing_and_2d_crosscheck.csv",
        "populations": tables / "timing_defined_population_summary.csv",
        "evidence": tables / "root_cause_evidence.csv",
        "gap_motion_figure": figures / "timestamp_gap_and_2d_motion.png",
        "step_trace_figure": figures / "all_49_locked_step_trace.png",
        "correlation_figure": figures / "raw_v42_cross_method_correlation.png",
        "population_figure": figures / "timing_population_stability.png",
        "event_figure": figures / "step15_vertical_repositioning.png",
        "report": output / "DIAGNOSTIC_REPORT_TW.md",
        "metadata": output / "metadata.json",
    }
    steps.to_csv(paths["steps"], index=False)
    populations.to_csv(paths["populations"], index=False)
    evidence.to_csv(paths["evidence"], index=False)
    _plot_gap_motion(steps, paths["gap_motion_figure"])
    _plot_step_trace(steps, paths["step_trace_figure"])
    _plot_correlation(steps, paths["correlation_figure"])
    _plot_populations(populations, paths["population_figure"])
    _plot_event(raw_images, v42_images, raw_positions, v42_positions, paths["event_figure"])
    _write_report(steps, populations, evidence, paths["report"])
    metadata = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sequence": "20x_0p5um",
        "mapping_source": str(Path(mapping_path).resolve()),
        "locked_comparison_source": str(Path(comparison_path).resolve()),
        "config_source": str(Path(config_path).resolve()),
        "independent_method": "sequential local 2D normalized template matching for the same nine pillars",
        "population_rules": {
            "primary": "all 49 adjacent pairs",
            "gap30": "timestamp gap <= 30 seconds",
            "regular_cadence": "timestamp gap <= 10 seconds",
        },
        "selection_guard": "timing populations use timestamps only, never Raw or V42 performance",
        "claim_limit": "nominal stage command is not independent position truth",
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose the 20x 0.5 um displacement sequence.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PACKAGE / "diagnostics" / "20x_0p5um_investigation",
    )
    args = parser.parse_args()
    outputs = run_diagnostic(output_root=args.output_root)
    print(pd.read_csv(outputs["populations"]).to_string(index=False))
    print(f"\nOutputs: {args.output_root.resolve()}")


if __name__ == "__main__":
    main()
