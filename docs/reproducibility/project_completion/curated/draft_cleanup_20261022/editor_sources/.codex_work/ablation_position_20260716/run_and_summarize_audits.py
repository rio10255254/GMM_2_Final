from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[8]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
FORMAL_PACKAGE = ROOT / "Final_Data_Figures" / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
DIAGNOSTIC = ROOT / "Final_Data_Figures" / "05_ABLATION_DIAGNOSTICS" / "boundary_position_diagnostic"
CONFIG_SOURCE = FORMAL_PACKAGE / "config" / "sequence_center9_50x20x.json"
SCRIPT_ROOT = FORMAL_PACKAGE / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from audit_all_displacement_sequences import run_unified_audit  # noqa: E402


METHODS = {
    "Raw": ("raw_boundary_dx_um", "raw_within_grid_nm"),
    "Pre-strengthening model": ("pre_boundary_dx_um", "pre_within_grid_nm"),
    "MOSR without boundary correction": ("no_boundary_dx_um", "no_boundary_within_grid_nm"),
    "Full MOSR": ("full_boundary_dx_um", "full_within_grid_nm"),
}

METHOD_COLORS = {
    "Raw": "#7f7f7f",
    "Pre-strengthening model": "#9467bd",
    "MOSR without boundary correction": "#cc8a00",
    "Full MOSR": "#1f6fae",
}

SEQUENCE_LABELS = {
    "50x_x_0p5um": "50x, 0.5 um",
    "50x_x_1um": "50x, 1.0 um",
    "20x_0p5um": "20x, 0.5 um",
    "20x_1um": "20x, 1.0 um",
}


def make_condition_config(condition_folder: str, output_path: Path) -> Path:
    config = json.loads(CONFIG_SOURCE.read_text(encoding="utf-8"))
    root = DIAGNOSTIC / "reconstructions" / condition_folder
    names = {
        "50x_x_0p5um": "50x_0p5um",
        "50x_x_1um": "50x_1um",
        "20x_0p5um": "20x_0p5um",
        "20x_1um": "20x_1um",
    }
    for sequence_name, folder_name in names.items():
        config["sequences"][sequence_name]["v42_dir"] = str(root / folder_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def run_condition_audit(condition_folder: str) -> Path:
    config_path = make_condition_config(
        condition_folder, DIAGNOSTIC / "configs" / f"{condition_folder}.json"
    )
    output = DIAGNOSTIC / "audits" / condition_folder
    run_unified_audit(output_root=output, config_path=config_path)
    return output / "tables" / "all_adjacent_pairs_audit.csv"


def bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def load_common_table(
    formal_path: Path, no_boundary_path: Path, pre_path: Path
) -> pd.DataFrame:
    keys = ["sequence", "start_frame_index", "end_frame_index"]
    base_columns = keys + [
        "magnification",
        "nominal_step_um",
        "expected_signed_step_um",
        "raw_boundary_dx_um",
        "raw_within_grid_nm",
        "raw_eligible_25pct",
    ]

    full = pd.read_csv(formal_path)
    no_boundary = pd.read_csv(no_boundary_path)
    pre = pd.read_csv(pre_path)
    table = full[base_columns].copy()
    table["full_valid"] = bool_series(full["v42_evaluable"]) & bool_series(full["v42_boundary_valid"])
    table["full_boundary_dx_um"] = full["v42_boundary_dx_um"]
    table["full_within_grid_nm"] = full["v42_within_grid_nm"]

    def method_subset(source: pd.DataFrame, prefix: str) -> pd.DataFrame:
        result = source[keys].copy()
        result[f"{prefix}_valid"] = bool_series(source["v42_evaluable"]) & bool_series(
            source["v42_boundary_valid"]
        )
        result[f"{prefix}_boundary_dx_um"] = source["v42_boundary_dx_um"]
        result[f"{prefix}_within_grid_nm"] = source["v42_within_grid_nm"]
        return result

    table = table.merge(method_subset(no_boundary, "no_boundary"), on=keys, how="inner")
    table = table.merge(method_subset(pre, "pre"), on=keys, how="inner")
    table["raw_eligible_25pct"] = bool_series(table["raw_eligible_25pct"])
    table["common_valid"] = (
        table["raw_eligible_25pct"]
        & table["full_valid"]
        & table["no_boundary_valid"]
        & table["pre_valid"]
    )
    required = [
        "raw_boundary_dx_um",
        "raw_within_grid_nm",
        "full_boundary_dx_um",
        "full_within_grid_nm",
        "no_boundary_boundary_dx_um",
        "no_boundary_within_grid_nm",
        "pre_boundary_dx_um",
        "pre_within_grid_nm",
    ]
    table["common_valid"] &= table[required].notna().all(axis=1)

    table = table.rename(
        columns={
            "no_boundary_boundary_dx_um": "no_boundary_dx_um",
            "pre_boundary_dx_um": "pre_boundary_dx_um",
        }
    )
    table["raw_command_abs_error_nm"] = (
        (table["raw_boundary_dx_um"] - table["expected_signed_step_um"]).abs() * 1000.0
    )
    table["raw_rank_score_nm"] = table["raw_command_abs_error_nm"] + table["raw_within_grid_nm"]
    return table


def choose_population(table: pd.DataFrame, population: str) -> pd.DataFrame:
    common = table.loc[table["common_valid"]].copy()
    if population == "all_common_valid":
        return common
    if population != "raw_ranked_best_30":
        raise ValueError(population)
    selected = []
    for _, group in common.groupby("sequence", sort=False):
        selected.append(
            group.sort_values(
                ["raw_rank_score_nm", "start_frame_index", "end_frame_index"]
            ).head(30)
        )
    return pd.concat(selected, ignore_index=True)


def summarize_population(table: pd.DataFrame, population: str) -> pd.DataFrame:
    selected = choose_population(table, population)
    rows = []
    for sequence, group in selected.groupby("sequence", sort=False):
        expected = group["expected_signed_step_um"].astype(float).to_numpy()
        for method, (step_column, grid_column) in METHODS.items():
            steps = group[step_column].astype(float).to_numpy()
            grid = group[grid_column].astype(float).to_numpy()
            rows.append(
                {
                    "population": population,
                    "sequence": sequence,
                    "method": method,
                    "pair_count": len(group),
                    "mean_signed_step_um": float(np.mean(steps)),
                    "signed_step_bias_nm": float(np.mean(steps - expected) * 1000.0),
                    "signed_step_sd_nm": float(np.std(steps, ddof=1) * 1000.0),
                    "command_mae_nm": float(np.mean(np.abs(steps - expected)) * 1000.0),
                    "mean_within_grid_nm": float(np.mean(grid)),
                    "median_within_grid_nm": float(np.median(grid)),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_differences(table: pd.DataFrame, population: str, repeats: int = 5000) -> pd.DataFrame:
    selected = choose_population(table, population)
    rng = np.random.default_rng(20260716)
    rows = []
    comparisons = [
        ("Full MOSR", "MOSR without boundary correction"),
        ("Full MOSR", "Pre-strengthening model"),
    ]
    for sequence, group in selected.groupby("sequence", sort=False):
        expected = group["expected_signed_step_um"].astype(float).to_numpy()
        n = len(group)
        for preferred, reference in comparisons:
            preferred_step, preferred_grid = METHODS[preferred]
            reference_step, reference_grid = METHODS[reference]
            pstep = group[preferred_step].astype(float).to_numpy()
            rstep = group[reference_step].astype(float).to_numpy()
            pgrid = group[preferred_grid].astype(float).to_numpy()
            rgrid = group[reference_grid].astype(float).to_numpy()
            samples = {
                "signed_step_sd_difference_nm": [],
                "command_mae_difference_nm": [],
                "mean_within_grid_difference_nm": [],
            }
            for _ in range(repeats):
                index = rng.integers(0, n, n)
                samples["signed_step_sd_difference_nm"].append(
                    np.std(pstep[index], ddof=1) * 1000.0 - np.std(rstep[index], ddof=1) * 1000.0
                )
                samples["command_mae_difference_nm"].append(
                    np.mean(np.abs(pstep[index] - expected[index])) * 1000.0
                    - np.mean(np.abs(rstep[index] - expected[index])) * 1000.0
                )
                samples["mean_within_grid_difference_nm"].append(
                    np.mean(pgrid[index]) - np.mean(rgrid[index])
                )
            for metric, values in samples.items():
                values_array = np.asarray(values, dtype=float)
                rows.append(
                    {
                        "population": population,
                        "sequence": sequence,
                        "preferred_method": preferred,
                        "reference_method": reference,
                        "metric": metric,
                        "difference_preferred_minus_reference": float(np.mean(values_array)),
                        "ci95_low": float(np.percentile(values_array, 2.5)),
                        "ci95_high": float(np.percentile(values_array, 97.5)),
                        "preferred_better_fraction": float(np.mean(values_array < 0.0)),
                    }
                )
    return pd.DataFrame(rows)


def add_relative_comparisons(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = ["signed_step_sd_nm", "command_mae_nm", "mean_within_grid_nm"]
    for (population, sequence), group in summary.groupby(["population", "sequence"]):
        indexed = group.set_index("method")
        for reference in ("MOSR without boundary correction", "Pre-strengthening model", "Raw"):
            for metric in metrics:
                full_value = float(indexed.loc["Full MOSR", metric])
                reference_value = float(indexed.loc[reference, metric])
                rows.append(
                    {
                        "population": population,
                        "sequence": sequence,
                        "metric": metric,
                        "reference_method": reference,
                        "full_mosr_value": full_value,
                        "reference_value": reference_value,
                        "difference_full_minus_reference": full_value - reference_value,
                        "reduction_percent": (
                            (reference_value - full_value) / reference_value * 100.0
                            if reference_value != 0
                            else np.nan
                        ),
                    }
                )
    return pd.DataFrame(rows)


def plot_metric(summary: pd.DataFrame, metric: str, ylabel: str, filename: str) -> None:
    data = summary.loc[summary["population"] == "raw_ranked_best_30"].copy()
    sequences = list(SEQUENCE_LABELS)
    methods = list(METHODS)
    x = np.arange(len(sequences))
    width = 0.18
    fig, axis = plt.subplots(figsize=(8.2, 4.0), dpi=180, constrained_layout=True)
    for index, method in enumerate(methods):
        values = [
            float(data.loc[(data["sequence"] == sequence) & (data["method"] == method), metric].iloc[0])
            for sequence in sequences
        ]
        axis.bar(
            x + (index - 1.5) * width,
            values,
            width,
            label=method,
            color=METHOD_COLORS[method],
        )
    axis.set_xticks(x)
    axis.set_xticklabels([SEQUENCE_LABELS[item] for item in sequences], fontsize=8)
    axis.set_ylabel(ylabel, fontsize=9)
    axis.tick_params(axis="y", labelsize=8)
    axis.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, fontsize=7, ncol=2, loc="upper center")
    axis.set_title("Common-valid Raw-ranked 30-step position diagnostic", fontsize=10)
    path = DIAGNOSTIC / "figures" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_report(
    summary: pd.DataFrame,
    relative: pd.DataFrame,
    bootstrap: pd.DataFrame,
    synthetic: pd.DataFrame,
    table: pd.DataFrame,
) -> None:
    primary = summary.loc[summary["population"] == "raw_ranked_best_30"].copy()
    lines = [
        "# 邊界與位置穩定性消融診斷",
        "",
        "## 性質",
        "",
        "這是決定是否值得進行正式重訓消融的前置診斷，尚未寫入論文。比較包含完整模型、推論時關閉邊界修正、量測導向加強前的同架構模型，以及原始影像。所有方法使用相同原始影像與相同固定光學路徑。",
        "",
        "## 公平性規則",
        "",
        "- 正式模型的本機重建先與已鎖定輸出逐像素比對。",
        "- 只比較三種模型都能完成九顆 pillar 量測的共同有效步驟。",
        "- 每組 30 步完全依 Raw 的命令誤差與九宮格不一致量排序，模型結果不參與挑選。",
        "- 另保留全部共同有效步驟作敏感度檢查。",
        "- 命令位移只作一致性參考，不視為獨立平台真值。",
        "",
        "## 30 步主結果",
        "",
    ]
    for sequence in SEQUENCE_LABELS:
        lines.append(f"### {SEQUENCE_LABELS[sequence]}")
        lines.append("")
        subset = primary.loc[primary["sequence"] == sequence]
        lines.append("| Method | Step SD (nm) | Command MAE (nm) | Nine-pillar disagreement (nm) |")
        lines.append("|---|---:|---:|---:|")
        for method in METHODS:
            row = subset.loc[subset["method"] == method].iloc[0]
            lines.append(
                f"| {method} | {row['signed_step_sd_nm']:.3f} | {row['command_mae_nm']:.3f} | {row['mean_within_grid_nm']:.3f} |"
            )
        lines.append("")

    def direction_count(reference: str, metric: str) -> tuple[int, int]:
        selected = relative.loc[
            (relative["population"] == "raw_ranked_best_30")
            & (relative["reference_method"] == reference)
            & (relative["metric"] == metric)
        ]
        return int((selected["difference_full_minus_reference"] < 0).sum()), len(selected)

    lines.extend(["## 方向檢查", ""])
    for reference in ("MOSR without boundary correction", "Pre-strengthening model"):
        labels = []
        for metric, label in (
            ("signed_step_sd_nm", "逐步標準差"),
            ("command_mae_nm", "命令偏差"),
            ("mean_within_grid_nm", "九宮格不一致"),
        ):
            better, total = direction_count(reference, metric)
            labels.append(f"{label} {better}/{total}")
        lines.append(f"- 完整模型相較 {reference}：" + "；".join(labels) + "。")
    raw_grid = relative.loc[
        (relative["population"] == "raw_ranked_best_30")
        & (relative["reference_method"] == "Raw")
        & (relative["metric"] == "mean_within_grid_nm")
    ]
    raw_grid_reductions = raw_grid["reduction_percent"].astype(float).tolist()
    synthetic_pivot = synthetic.pivot(index="magnification", columns="method", values="translation_error_median_px")
    boundary_synthetic_better = int(
        (
            synthetic_pivot["Full MOSR"]
            < synthetic_pivot["MOSR without boundary correction"]
        ).sum()
    )
    lines.extend(
        [
            "",
            "## 結論",
            "",
            (
                "1. 不建議把『關閉邊界修正』這一組寫進論文作為正向消融。完整模型相較關閉版本，"
                "逐步標準差僅 1/4 組較低、命令參考 MAE 為 0/4 組較低、九宮格不一致為 2/4 組較低；"
                f"人工次像素位移亦僅 {boundary_synthetic_better}/2 個倍率較低。這不足以支持該單一模組穩定位置的因果說法。"
            ),
            (
                "2. 量測導向加強的整體方向較有利：相較加強前模型，完整模型在 30 步主結果中有 3/4 組逐步標準差較低、"
                "4/4 組命令參考 MAE 較低，但九宮格不一致只有 2/4 組較低。因此可以說整體訓練通常改善位移讀值，"
                "仍不能把改善獨立歸因於單一模組。"
            ),
            (
                "3. 最穩健且可直接保留的結果仍是完整 MOSR 相較 Raw 的九顆 pillar 一致性：四組 30 步的平均不一致量皆下降，"
                f"降幅為 {min(raw_grid_reductions):.1f}% 至 {max(raw_grid_reductions):.1f}%。"
            ),
            (
                "4. 若要正式證明研究方法中的位置穩定機制，下一輪應維持所有光學與網路結構不變，只分別移除"
                "『邊界位置約束』與『序列平移一致性約束』重新訓練；目前這份診斷先不要寫入論文。"
            ),
        ]
    )
    lines.extend(
        [
            "",
            "## 判讀限制",
            "",
            "關閉邊界修正是同一權重下的直接模組旁路，可用來判斷該模組在推論端的淨作用；加強前後模型比較則同時包含訓練階段與品質控制差異，不能單獨歸因於某一個損失項。若結果方向清楚且在全部共同有效步驟中仍一致，才值得再投入完整重訓消融。",
            "",
            "## 檔案完整性",
            "",
            f"- 共同逐步資料：{len(table)} rows",
            f"- 合成位移摘要：{len(synthetic)} rows",
            f"- Bootstrap 摘要：{len(bootstrap)} rows",
        ]
    )
    (DIAGNOSTIC / "REPORT_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-audits", action="store_true")
    args = parser.parse_args()
    no_boundary_existing = (
        DIAGNOSTIC
        / "audits"
        / "without_boundary_correction"
        / "tables"
        / "all_adjacent_pairs_audit.csv"
    )
    pre_existing = (
        DIAGNOSTIC
        / "audits"
        / "pre_strengthening_model"
        / "tables"
        / "all_adjacent_pairs_audit.csv"
    )
    no_boundary_path = (
        no_boundary_existing
        if args.reuse_audits and no_boundary_existing.exists()
        else run_condition_audit("without_boundary_correction")
    )
    pre_path = (
        pre_existing
        if args.reuse_audits and pre_existing.exists()
        else run_condition_audit("pre_strengthening_model")
    )
    formal_path = (
        FORMAL_PACKAGE
        / "diagnostics"
        / "unified_displacement_step_audit"
        / "tables"
        / "all_adjacent_pairs_audit.csv"
    )

    common = load_common_table(formal_path, no_boundary_path, pre_path)
    summaries = pd.concat(
        [
            summarize_population(common, "raw_ranked_best_30"),
            summarize_population(common, "all_common_valid"),
        ],
        ignore_index=True,
    )
    relative = add_relative_comparisons(summaries)
    bootstrap = pd.concat(
        [
            bootstrap_differences(common, "raw_ranked_best_30"),
            bootstrap_differences(common, "all_common_valid"),
        ],
        ignore_index=True,
    )
    synthetic = pd.read_csv(DIAGNOSTIC / "tables" / "synthetic_shift_summary.csv")

    table_dir = DIAGNOSTIC / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    common.to_csv(table_dir / "common_pair_measurements.csv", index=False, encoding="utf-8-sig")
    summaries.to_csv(table_dir / "actual_sequence_summary.csv", index=False, encoding="utf-8-sig")
    relative.to_csv(table_dir / "actual_sequence_relative_comparison.csv", index=False, encoding="utf-8-sig")
    bootstrap.to_csv(table_dir / "paired_bootstrap_difference.csv", index=False, encoding="utf-8-sig")

    plot_metric(summaries, "signed_step_sd_nm", "Signed step standard deviation (nm)", "actual_step_stability.png")
    plot_metric(summaries, "command_mae_nm", "Command-reference MAE (nm)", "actual_command_mae.png")
    plot_metric(
        summaries,
        "mean_within_grid_nm",
        "Mean nine-pillar disagreement (nm)",
        "actual_nine_pillar_consistency.png",
    )
    write_report(summaries, relative, bootstrap, synthetic, common)

    metadata = {
        "formal_pair_table": str(formal_path),
        "without_boundary_pair_table": str(no_boundary_path),
        "pre_strengthening_pair_table": str(pre_path),
        "formal_pair_table_sha256": sha256(formal_path),
        "without_boundary_pair_table_sha256": sha256(no_boundary_path),
        "pre_strengthening_pair_table_sha256": sha256(pre_path),
        "primary_population": "30 common-valid pairs per sequence ranked using Raw only",
        "sensitivity_population": "all common-valid Raw-eligible pairs",
        "bootstrap_repeats": 5000,
        "random_seed": 20260716,
        "claim_limit": "diagnostic evidence; not a retrained loss-function ablation",
    }
    (DIAGNOSTIC / "analysis_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summaries.loc[summaries["population"] == "raw_ranked_best_30"].to_string(index=False))
    print(f"\nReport: {DIAGNOSTIC / 'REPORT_TW.md'}")


if __name__ == "__main__":
    main()
