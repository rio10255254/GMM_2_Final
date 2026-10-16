from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PACKAGE = Path(__file__).resolve().parents[1]
FULL_SUMMARY = PACKAGE / "displacement" / "tables" / "raw_v42_common_valid_summary.csv"
SESSION_DIAGNOSTICS = PACKAGE / "diagnostics" / "50x_0p5um_sessions"
APPROVED_SEQUENCES = (
    "50x_x_0p5um",
    "50x_x_1um",
    "20x_0p5um",
    "20x_1um",
)


def _protected_digest() -> str:
    files = [
        PACKAGE / "REPORT.md",
        PACKAGE / "manifest.json",
        PACKAGE / "reproducibility_sha256.csv",
    ]
    files.extend(
        path
        for root in (PACKAGE / "cd", PACKAGE / "displacement")
        for path in root.rglob("*")
        if path.is_file()
    )
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: str(item).lower()):
        digest.update(str(path.relative_to(PACKAGE)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _corrected_wide_row(summary: pd.DataFrame) -> dict[str, Any]:
    indexed = summary.set_index("case")
    raw = indexed.loc["Raw"]
    v42 = indexed.loc["V42 epoch 120"]
    raw_sd = float(raw["signed_step_sd_nm"])
    v42_sd = float(v42["signed_step_sd_nm"])
    raw_grid = float(raw["mean_within_grid_disagreement_nm"])
    v42_grid = float(v42["mean_within_grid_disagreement_nm"])
    return {
        "sequence": "50x_x_0p5um",
        "magnification": "50x",
        "nominal_step_um": 0.5,
        "raw_scheduled_steps": int(raw["scheduled_steps"]),
        "v42_scheduled_steps": int(v42["scheduled_steps"]),
        "raw_valid_steps": int(raw["valid_steps"]),
        "v42_valid_steps": int(v42["valid_steps"]),
        "raw_coverage_pct": float(raw["coverage_pct"]),
        "v42_coverage_pct": float(v42["coverage_pct"]),
        "raw_mean_step_magnitude_um": float(raw["mean_step_magnitude_um"]),
        "v42_mean_step_magnitude_um": float(v42["mean_step_magnitude_um"]),
        "raw_step_magnitude_sd_nm": float(raw["step_magnitude_sd_nm"]),
        "v42_step_magnitude_sd_nm": float(v42["step_magnitude_sd_nm"]),
        "raw_signed_step_sd_nm": raw_sd,
        "v42_signed_step_sd_nm": v42_sd,
        "raw_wrong_direction_steps": int(raw["wrong_direction_steps"]),
        "v42_wrong_direction_steps": int(v42["wrong_direction_steps"]),
        "raw_wrong_direction_pct": float(raw["wrong_direction_pct"]),
        "v42_wrong_direction_pct": float(v42["wrong_direction_pct"]),
        "raw_magnitude_bias_to_nominal_nm": float(raw["magnitude_bias_to_nominal_nm"]),
        "v42_magnitude_bias_to_nominal_nm": float(v42["magnitude_bias_to_nominal_nm"]),
        "raw_rmse_to_nominal_command_nm": float(raw["rmse_to_nominal_command_nm"]),
        "v42_rmse_to_nominal_command_nm": float(v42["rmse_to_nominal_command_nm"]),
        "raw_mean_within_grid_disagreement_nm": raw_grid,
        "v42_mean_within_grid_disagreement_nm": v42_grid,
        "v42_step_sd_reduction_nm": raw_sd - v42_sd,
        "v42_step_sd_reduction_pct": (raw_sd - v42_sd) / raw_sd * 100.0,
        "v42_within_grid_reduction_nm": raw_grid - v42_grid,
        "v42_within_grid_reduction_pct": (raw_grid - v42_grid) / raw_grid * 100.0,
        "analysis_population": "48 within-session adjacent pairs",
        "excluded_cross_session_pairs": 2,
        "session_count": 3,
    }


def _build_summary() -> pd.DataFrame:
    full = pd.read_csv(FULL_SUMMARY)
    session = pd.read_csv(SESSION_DIAGNOSTICS / "tables" / "corrected_raw_v42_summary.csv")
    rows = [_corrected_wide_row(session)]
    for sequence in APPROVED_SEQUENCES[1:]:
        selected = full.loc[full["sequence"] == sequence]
        if len(selected) != 1:
            raise ValueError(f"expected exactly one source row for {sequence}")
        row = selected.iloc[0].to_dict()
        row.update(
            {
                "analysis_population": "all consecutive adjacent pairs",
                "excluded_cross_session_pairs": 0,
                "session_count": 1,
            }
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    if tuple(result["sequence"]) != APPROVED_SEQUENCES:
        raise RuntimeError("thesis summary sequence order is not locked")
    return result


def _build_before_after(summary: pd.DataFrame) -> pd.DataFrame:
    old = pd.read_csv(FULL_SUMMARY).set_index("sequence").loc["50x_x_0p5um"]
    corrected = summary.set_index("sequence").loc["50x_x_0p5um"]
    rows = []
    for case, prefix in (("Raw", "raw"), ("V42 epoch 120", "v42")):
        rows.append(
            {
                "analysis_version": "old_unsegmented",
                "case": case,
                "eligible_steps": int(old[f"{prefix}_scheduled_steps"]),
                "valid_steps": int(old[f"{prefix}_valid_steps"]),
                "coverage_pct": float(old[f"{prefix}_coverage_pct"]),
                "signed_step_sd_nm": float(old[f"{prefix}_signed_step_sd_nm"]),
                "mean_within_grid_disagreement_nm": float(
                    old[f"{prefix}_mean_within_grid_disagreement_nm"]
                ),
            }
        )
        rows.append(
            {
                "analysis_version": "corrected_timestamp_sessions",
                "case": case,
                "eligible_steps": int(corrected[f"{prefix}_scheduled_steps"]),
                "valid_steps": int(corrected[f"{prefix}_valid_steps"]),
                "coverage_pct": float(corrected[f"{prefix}_coverage_pct"]),
                "signed_step_sd_nm": float(corrected[f"{prefix}_signed_step_sd_nm"]),
                "mean_within_grid_disagreement_nm": float(
                    corrected[f"{prefix}_mean_within_grid_disagreement_nm"]
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot_before_after(table: pd.DataFrame, output_path: Path) -> None:
    order = [
        ("old_unsegmented", "Raw", "Old Raw"),
        ("old_unsegmented", "V42 epoch 120", "Old V42"),
        ("corrected_timestamp_sessions", "Raw", "Corrected Raw"),
        ("corrected_timestamp_sessions", "V42 epoch 120", "Corrected V42"),
    ]
    indexed = table.set_index(["analysis_version", "case"])
    selected = pd.DataFrame(
        [indexed.loc[(version, case)] for version, case, _ in order],
        index=[label for _, _, label in order],
    )
    colors = ["#ef9a9a", "#90caf9", "#d62728", "#1f77b4"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), constrained_layout=True)
    for axis, column, ylabel in (
        (axes[0], "coverage_pct", "Valid-step coverage (%)"),
        (axes[1], "signed_step_sd_nm", "Signed step standard deviation (nm)"),
    ):
        bars = axis.bar(selected.index, selected[column], color=colors)
        axis.bar_label(bars, fmt="%.1f", padding=3)
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=20)
        axis.grid(axis="y", alpha=0.25)
        axis.set_ylim(0, float(selected[column].max()) * 1.22)
    fig.suptitle("50x 0.5 um analysis before and after acquisition-session correction")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_grouped_metric(
    summary: pd.DataFrame,
    output_path: Path,
    *,
    raw_column: str,
    v42_column: str,
    ylabel: str,
    title: str,
) -> None:
    labels = ["50x 0.5 um", "50x 1.0 um", "20x 0.5 um", "20x 1.0 um"]
    positions = np.arange(len(summary))
    width = 0.36
    fig, axis = plt.subplots(figsize=(10.2, 5.8), constrained_layout=True)
    raw_bars = axis.bar(
        positions - width / 2,
        summary[raw_column],
        width,
        color="#d62728",
        label="Raw",
    )
    v42_bars = axis.bar(
        positions + width / 2,
        summary[v42_column],
        width,
        color="#1f77b4",
        label="V42 epoch 120",
    )
    axis.bar_label(raw_bars, fmt="%.1f", padding=3, fontsize=9)
    axis.bar_label(v42_bars, fmt="%.1f", padding=3, fontsize=9)
    axis.set_xticks(positions, labels)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    axis.set_ylim(0, max(summary[raw_column].max(), summary[v42_column].max()) * 1.2)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _write_report(summary: pd.DataFrame, path: Path) -> None:
    rows = summary.set_index("sequence")
    corrected = rows.loc["50x_x_0p5um"]
    report = f"""# 50x 與 20x 位移驗證結果

## 使用範圍

本資料夾只收錄論文預定使用的四組位移資料：50x 的 0.5 um、1.0 um，以及 20x 的 0.5 um、1.0 um。Raw 與 V42 使用相同影像順序、相同九顆中心圓柱及相同有效性條件。

## 50x 0.5 um 資料修正

原始 51 張影像並非一次連續拍完。拍攝時間在第 26 至 27 張之間相隔 1321 秒，在第 30 至 31 張之間相隔 283 秒，因此資料實際分成 0-26、27-30、31-50 三個批次。正常批次內間隔最多 32 秒；把判定門檻從 45 秒調到 180 秒，仍得到完全相同的三段。

兩個跨批次組合仍完整保留在稽核表，但不當作平台執行的 0.5 um 連續步距。三個批次起點以同一組九顆圓柱各自做局部二維對準，九顆估計的起點散布只有約 0.01 至 0.03 px。批次內共 48 步全部納入，沒有依重建結果挑選步數。

舊分析把 51 張影像當成單次連續拍攝，並沿用第一批影像的垂直位置，因此樣品在後兩批向下移動約 12.66 px 與 14.41 px 後，部分水平剖面已沒有穿過原本的圓柱位置。舊結果只能保留 33/50 步，Raw 與 V42 的標準差都約為 63 nm；這主要反映資料串接與區域錯位，不應解讀為模型對 0.5 um 位移突然失效。

修正後 Raw 的步距標準差為 {corrected['raw_signed_step_sd_nm']:.2f} nm，V42 為 {corrected['v42_signed_step_sd_nm']:.2f} nm，降低 {corrected['v42_step_sd_reduction_pct']:.1f}%。九顆圓柱彼此量得位移不一致的程度，則由 {corrected['raw_mean_within_grid_disagreement_nm']:.2f} nm 降至 {corrected['v42_mean_within_grid_disagreement_nm']:.2f} nm，降低 {corrected['v42_within_grid_reduction_pct']:.1f}%。

## 四組結果摘要

| 資料組 | Raw 標準差 (nm) | V42 標準差 (nm) | V42 標準差降低 (%) | Raw 九圓柱不一致 (nm) | V42 九圓柱不一致 (nm) |
|---|---:|---:|---:|---:|---:|
"""
    labels = {
        "50x_x_0p5um": "50x 0.5 um",
        "50x_x_1um": "50x 1.0 um",
        "20x_0p5um": "20x 0.5 um",
        "20x_1um": "20x 1.0 um",
    }
    for sequence in APPROVED_SEQUENCES:
        row = rows.loc[sequence]
        report += (
            f"| {labels[sequence]} | {row['raw_signed_step_sd_nm']:.2f} | "
            f"{row['v42_signed_step_sd_nm']:.2f} | "
            f"{row['v42_step_sd_reduction_pct']:+.1f} | "
            f"{row['raw_mean_within_grid_disagreement_nm']:.2f} | "
            f"{row['v42_mean_within_grid_disagreement_nm']:.2f} |\n"
        )
    report += """

## 解讀限制

這些數值可用來比較同一資料下 Raw 與 V42 的重複性，以及九顆圓柱的局部邊界一致性。平台命令值是名義參考，並不是另一套獨立量測儀器提供的真實位置，因此不可把本表寫成絕對定位準確度。
"""
    path.write_text(report, encoding="utf-8")


def build_thesis_package(*, output_root: str | Path) -> dict[str, Path]:
    output = Path(output_root).resolve()
    protected_roots = {(PACKAGE / name).resolve() for name in ("cd", "displacement")}
    if output == PACKAGE.resolve() or output in protected_roots:
        raise ValueError("thesis output must remain separate from the protected archive")
    before_digest = _protected_digest()
    if output.exists():
        shutil.rmtree(output)
    tables = output / "tables"
    figures = output / "figures"
    details = figures / "sequence_details"
    tables.mkdir(parents=True)
    details.mkdir(parents=True)

    summary = _build_summary()
    before_after = _build_before_after(summary)
    paths = {
        "summary": tables / "displacement_summary_50x_20x.csv",
        "corrected_steps": tables / "50x_0p5um_corrected_48_steps.csv",
        "pair_audit": tables / "50x_0p5um_all_50_pairs_audit.csv",
        "before_after": tables / "50x_0p5um_before_after_audit.csv",
        "stability_figure": figures / "displacement_stability_50x_20x.png",
        "grid_figure": figures / "nine_pillar_consistency_50x_20x.png",
        "before_after_figure": figures / "50x_0p5um_before_after.png",
        "corrected_trace_figure": figures / "50x_0p5um_corrected_step_trace.png",
        "gap_figure": figures / "50x_0p5um_acquisition_gaps.png",
        "anchor_figure": figures / "50x_0p5um_session_anchors.png",
        "report": output / "THESIS_REPORT.md",
        "manifest": output / "manifest.json",
    }
    summary.to_csv(paths["summary"], index=False)
    before_after.to_csv(paths["before_after"], index=False)
    shutil.copy2(
        SESSION_DIAGNOSTICS / "tables" / "corrected_48_within_session_steps.csv",
        paths["corrected_steps"],
    )
    shutil.copy2(
        SESSION_DIAGNOSTICS / "tables" / "all_50_adjacent_pairs_audit.csv",
        paths["pair_audit"],
    )
    shutil.copy2(
        SESSION_DIAGNOSTICS / "figures" / "corrected_48_step_trace.png",
        paths["corrected_trace_figure"],
    )
    shutil.copy2(
        SESSION_DIAGNOSTICS / "figures" / "timestamp_gap_sessions.png",
        paths["gap_figure"],
    )
    shutil.copy2(
        SESSION_DIAGNOSTICS / "figures" / "absolute_xy_session_shift.png",
        paths["anchor_figure"],
    )
    _plot_grouped_metric(
        summary,
        paths["stability_figure"],
        raw_column="raw_signed_step_sd_nm",
        v42_column="v42_signed_step_sd_nm",
        ylabel="Signed step standard deviation (nm)",
        title="Displacement repeatability using the same center-nine pillars",
    )
    _plot_grouped_metric(
        summary,
        paths["grid_figure"],
        raw_column="raw_mean_within_grid_disagreement_nm",
        v42_column="v42_mean_within_grid_disagreement_nm",
        ylabel="Mean within-grid disagreement (nm)",
        title="Agreement among nine independently measured pillars",
    )
    _plot_before_after(before_after, paths["before_after_figure"])

    source_figures = PACKAGE / "displacement" / "figures"
    for sequence in APPROVED_SEQUENCES[1:]:
        for suffix in ("identity_overlay", "step_trace", "within_grid_residuals"):
            source = source_figures / f"{sequence}_{suffix}.png"
            if not source.is_file():
                raise FileNotFoundError(source)
            shutil.copy2(source, details / source.name)

    _write_report(summary, paths["report"])
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "thesis displacement results for 50x and 20x",
        "sequences": list(APPROVED_SEQUENCES),
        "corrected_sequence": "50x_x_0p5um",
        "corrected_population": "48 within-session adjacent pairs; two cross-session pairs retained only in the audit table",
        "session_starts": [0, 27, 31],
        "anchor_method": "same nine pillars, local 2D subpixel matching, median session offset",
        "step_selection": "all eligible adjacent pairs; no result-based selection",
        "protected_archive_digest_before": before_digest,
        "claim_limit": "repeatability comparison; nominal stage command is not independent position truth",
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    after_digest = _protected_digest()
    if before_digest != after_digest:
        raise RuntimeError("protected full-audit archive changed during thesis packaging")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the clean 50x/20x thesis package.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PACKAGE / "thesis_50x_20x",
    )
    args = parser.parse_args()
    outputs = build_thesis_package(output_root=args.output_root)
    print(pd.read_csv(outputs["summary"]).to_string(index=False))
    print(f"\nOutputs: {args.output_root.resolve()}")


if __name__ == "__main__":
    main()
