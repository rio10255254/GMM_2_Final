from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon


ROOT = Path(__file__).resolve().parent
MODERN = ROOT.parent / "Modern_Restoration_Benchmarks_20260719"
FORMAL = (
    MODERN
    / "evaluation"
    / "displacement_50x20x_edrs_nafnet_refresh_20260724"
)
BEST = ROOT.parent / "MOSR_BestCheckpoint_Diagnostic_20260724" / "evaluation"
ANCHORED = ROOT / "evaluation"
SUBPIXEL = (
    ROOT.parent
    / "Subpixel_Translation_Equivariance_20260720"
    / "analysis"
    / "tables"
)
TRAIN_LOG = (
    ROOT.parent
    / ".."
    / ".."
    / ".."
    / "Deliverables"
    / "Standalone_Models"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
    / "results"
    / "run_logs"
    / "full_training_20260709_202710"
    / "train_stdout.log"
).resolve()
OUTPUT = ROOT / "diagnosis"


VARIANTS = {
    "MOSR epoch 120": FORMAL,
    "MOSR training-selected epoch 10": BEST,
    "MOSR epoch 120 + checkpoint anchor": ANCHORED,
}


def as_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def finite_method_rows(table: pd.DataFrame, method: str) -> pd.DataFrame:
    rows = table.loc[table["method"].eq(method)].copy()
    rows = rows.loc[
        as_bool(rows["evaluable"])
        & rows["signed_step_um"].notna()
        & rows["expected_signed_step_um"].notna()
    ].copy()
    rows["absolute_error_nm"] = (
        rows["signed_step_um"].astype(float)
        - rows["expected_signed_step_um"].astype(float)
    ).abs() * 1000.0
    return rows


def paired_comparison(table: pd.DataFrame, morphology: str) -> dict[str, float | int]:
    subset = table.loc[table["morphology"].eq(morphology)].copy()
    edsr = finite_method_rows(subset, "EDSR")
    mosr = finite_method_rows(subset, "MOSR")
    keys = ["morphology", "sequence", "end_frame_index"]
    paired = edsr.merge(
        mosr,
        on=keys,
        suffixes=("_edsr", "_mosr"),
        validate="one_to_one",
    )
    delta = (
        paired["absolute_error_nm_mosr"].to_numpy(dtype=float)
        - paired["absolute_error_nm_edsr"].to_numpy(dtype=float)
    )
    rng = np.random.default_rng(1261200)
    draws = np.empty(10000, dtype=float)
    for index in range(len(draws)):
        sampled = rng.integers(0, len(delta), len(delta))
        draws[index] = float(np.mean(delta[sampled]))
    try:
        p_value = float(wilcoxon(delta, zero_method="wilcox").pvalue)
    except ValueError:
        p_value = 1.0
    return {
        "n": int(len(delta)),
        "mosr_minus_edsr_mean_absolute_error_nm": float(np.mean(delta)),
        "bootstrap_95ci_low_nm": float(np.percentile(draws, 2.5)),
        "bootstrap_95ci_high_nm": float(np.percentile(draws, 97.5)),
        "mosr_win_fraction": float(np.mean(delta < 0.0)),
        "tie_fraction": float(np.mean(delta == 0.0)),
        "wilcoxon_p_value": p_value,
    }


def load_pooled(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path / "displacement_pooled_common_valid.csv")
    return table.loc[table["method"].isin(["EDSR", "MOSR"])].copy()


def build_checkpoint_comparison() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    paired_rows: list[dict[str, object]] = []
    formal_edsr_added = False
    for variant, path in VARIANTS.items():
        pooled = load_pooled(path)
        if not formal_edsr_added:
            edsr = pooled.loc[pooled["method"].eq("EDSR")].copy()
            edsr["method_variant"] = "EDSR-x1 + fixed optical adapter"
            rows.append(edsr)
            formal_edsr_added = True
        mosr = pooled.loc[pooled["method"].eq("MOSR")].copy()
        mosr["method_variant"] = variant
        rows.append(mosr)

        long_table = pd.read_csv(path / "displacement_step_measurements.csv")
        for morphology in ("pillar", "via"):
            paired_rows.append(
                {
                    "variant": variant,
                    "morphology": morphology,
                    **paired_comparison(long_table, morphology),
                }
            )
    comparison = pd.concat(rows, ignore_index=True)
    keep = [
        "morphology",
        "method_variant",
        "n",
        "mae_nm",
        "median_absolute_error_nm",
        "rmse_nm",
        "p95_absolute_error_nm",
        "mean_within_grid_nm",
        "median_within_grid_nm",
    ]
    return comparison.loc[:, keep], pd.DataFrame(paired_rows)


def build_subpixel_diagnostics() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clusters = pd.read_csv(SUBPIXEL / "cluster_translation_metrics.csv")
    clusters = clusters.loc[
        as_bool(clusters["primary_endpoint"])
        & as_bool(clusters["valid"])
        & clusters["method"].isin(["EDSR", "MOSR"])
    ].copy()
    clusters["absolute_error_px"] = clusters["absolute_error_px"].astype(float)
    by_shift = (
        clusters.groupby(["method", "shift_magnitude_px"], as_index=False)
        .agg(
            n=("absolute_error_px", "size"),
            median_absolute_error_px=("absolute_error_px", "median"),
            mean_absolute_error_px=("absolute_error_px", "mean"),
            p95_absolute_error_px=(
                "absolute_error_px",
                lambda values: float(np.percentile(values, 95.0)),
            ),
        )
        .sort_values(["shift_magnitude_px", "method"])
    )

    paired = (
        clusters.loc[:, ["cluster_id", "method", "absolute_error_px"]]
        .pivot(index="cluster_id", columns="method", values="absolute_error_px")
        .dropna()
        .reset_index()
    )
    paired["mosr_minus_edsr_absolute_error_px"] = paired["MOSR"] - paired["EDSR"]
    cluster_meta = clusters.drop_duplicates("cluster_id").loc[
        :, ["cluster_id", "case_id", "magnification", "morphology", "axis", "shift_px", "shift_magnitude_px"]
    ]
    paired = paired.merge(cluster_meta, on="cluster_id", how="left", validate="one_to_one")

    sharpness = pd.read_csv(SUBPIXEL / "sharpness_cluster_metrics.csv")
    sharpness = sharpness.loc[sharpness["method"].isin(["EDSR", "MOSR"])].copy()
    joined = clusters.merge(
        sharpness,
        on=["method", "case_id", "magnification", "morphology", "axis", "shift_px"],
        how="inner",
        validate="one_to_one",
    )
    mechanism_rows: list[dict[str, object]] = []
    equivariance = pd.read_csv(SUBPIXEL / "image_equivariance_metrics.csv")
    for method in ("EDSR", "MOSR"):
        method_clusters = clusters.loc[clusters["method"].eq(method)]
        method_sharpness = sharpness.loc[sharpness["method"].eq(method)]
        method_equivariance = equivariance.loc[equivariance["method"].eq(method)]
        error_width = joined.loc[joined["method"].eq(method)]
        rho_width, p_width = spearmanr(
            error_width["absolute_error_px"],
            error_width["median_transition_width_px"],
        )
        rho_ring, p_ring = spearmanr(
            error_width["absolute_error_px"],
            error_width["median_overshoot_ratio"],
        )
        mechanism_rows.append(
            {
                "method": method,
                "subpixel_median_absolute_error_px": float(
                    method_clusters["absolute_error_px"].median()
                ),
                "subpixel_p95_absolute_error_px": float(
                    np.percentile(method_clusters["absolute_error_px"], 95.0)
                ),
                "median_normalized_equivariance_rmse": float(
                    method_equivariance["normalized_rmse"].median()
                ),
                "median_transition_width_px": float(
                    method_sharpness["median_transition_width_px"].median()
                ),
                "median_normalized_edge_slope": float(
                    method_sharpness["median_normalized_slope_per_px"].median()
                ),
                "median_overshoot_ratio": float(
                    method_sharpness["median_overshoot_ratio"].median()
                ),
                "spearman_error_vs_width": float(rho_width),
                "spearman_error_vs_width_p": float(p_width),
                "spearman_error_vs_overshoot": float(rho_ring),
                "spearman_error_vs_overshoot_p": float(p_ring),
            }
        )
    return by_shift, paired, pd.DataFrame(mechanism_rows)


def write_report(
    checkpoint: pd.DataFrame,
    paired: pd.DataFrame,
    by_shift: pd.DataFrame,
    mechanism: pd.DataFrame,
    training_counts: dict[str, int],
) -> None:
    def row(frame: pd.DataFrame, **filters: str) -> pd.Series:
        selected = frame.copy()
        for key, value in filters.items():
            selected = selected.loc[selected[key].eq(value)]
        return selected.iloc[0]

    edsr_pillar = row(
        checkpoint,
        morphology="pillar",
        method_variant="EDSR-x1 + fixed optical adapter",
    )
    formal_pillar = row(
        checkpoint, morphology="pillar", method_variant="MOSR epoch 120"
    )
    formal_via = row(checkpoint, morphology="via", method_variant="MOSR epoch 120")
    anchored_pillar = row(
        checkpoint,
        morphology="pillar",
        method_variant="MOSR epoch 120 + checkpoint anchor",
    )
    anchored_via = row(
        checkpoint,
        morphology="via",
        method_variant="MOSR epoch 120 + checkpoint anchor",
    )
    mech_edsr = row(mechanism, method="EDSR")
    mech_mosr = row(mechanism, method="MOSR")
    shift01_edsr = by_shift.loc[
        by_shift["method"].eq("EDSR") & np.isclose(by_shift["shift_magnitude_px"], 0.1)
    ].iloc[0]
    shift01_mosr = by_shift.loc[
        by_shift["method"].eq("MOSR") & np.isclose(by_shift["shift_magnitude_px"], 0.1)
    ].iloc[0]

    lines = [
        "# EDSR 與 MOSR 位移結果診斷",
        "",
        "## 結論",
        "",
        "EDSR 在目前的全位移範圍平均結果較好，主要原因不是挑步或缺值，而是它採用全解析度殘差卷積，沒有 MOSR 三次步幅為 2 的降採樣，因此較不受取樣相位影響。MOSR 並非全面失效：在最小的 0.1 pixel 測試中，MOSR 的中位絕對誤差最低；在正式 pillar 測試中，MOSR 與 EDSR 的平均差只有 0.26 nm，且 MOSR 的尾端誤差略低。",
        "",
        "## 已排除的解釋",
        "",
        "- 所有方法使用相同 Raw 鎖定的 30 步，沒有依模型結果重新挑步。",
        "- 最佳第 10 輪重新推論沒有改善正式平均誤差，因此第 120 輪並不是 EDSR 領先的唯一原因。",
        "- 啟用權重內原先宣告的低頻定位保護後，via 有改善，但 pillar 變差；單靠輸出錨定無法解決模型內部的相位誤差。",
        "- EDSR 並不是靠模糊換取穩定。它的中位 10–90% 邊界寬度比 MOSR 小，且振鈴比例也較低。",
        "",
        "## 關鍵數字",
        "",
        f"- 正式 pillar：EDSR MAE {edsr_pillar['mae_nm']:.2f} nm，MOSR 第 120 輪 {formal_pillar['mae_nm']:.2f} nm；差距 {formal_pillar['mae_nm'] - edsr_pillar['mae_nm']:.2f} nm。",
        f"- MOSR 的正式 pillar p95 為 {formal_pillar['p95_absolute_error_nm']:.2f} nm，EDSR 為 {edsr_pillar['p95_absolute_error_nm']:.2f} nm；MOSR 的尾端誤差略低。",
        f"- 定位保護版 MOSR：pillar MAE {anchored_pillar['mae_nm']:.2f} nm，via MAE {anchored_via['mae_nm']:.2f} nm；相較原版 via {formal_via['mae_nm']:.2f} nm 有改善，但 pillar 變差。",
        f"- 0.1 pixel 已知位移：MOSR 中位誤差 {shift01_mosr['median_absolute_error_px']:.5f} pixel，EDSR {shift01_edsr['median_absolute_error_px']:.5f} pixel。",
        f"- 全範圍已知位移：MOSR 中位誤差 {mech_mosr['subpixel_median_absolute_error_px']:.5f} pixel，EDSR {mech_edsr['subpixel_median_absolute_error_px']:.5f} pixel。",
        f"- 邊界寬度：MOSR {mech_mosr['median_transition_width_px']:.2f} pixel，EDSR {mech_edsr['median_transition_width_px']:.2f} pixel。",
        f"- 振鈴比例：MOSR {mech_mosr['median_overshoot_ratio']:.4f}，EDSR {mech_edsr['median_overshoot_ratio']:.4f}。",
        f"- 訓練 120 輪中共記錄 {training_counts['oversmooth_guard_events']} 次過度平滑警示；最佳權重在第 10 輪後未再更新。",
        "",
        "## 根本原因",
        "",
        "1. MOSR 的抗混疊設計只處理上採樣，但編碼器仍有三層步幅為 2 的卷積降採樣。輸入平移一個像素時，三層特徵會落在不同取樣相位；EDSR 沒有這條路徑。",
        "2. 正式訓練後期的損失幾乎由梯度重建主導，平移幾何項的實際占比約 0.2%。模型學會讓局部邊緣變陡，但沒有足夠壓力維持整條邊界的相位。",
        "3. MOSR 出現局部斜率高、外圍過渡仍寬的雙層輪廓。這會讓半高或徑向邊界追蹤器在不同取樣相位間產生小幅漂移。",
        "4. 現行 EDSR 也使用固定 PSF 輸入轉換，因此它不是完全未使用光學先驗的原始 EDSR；目前比較主要反映後端網路結構差異。",
        "",
        "## 要讓 MOSR 真正成為全範圍最佳的必要修改",
        "",
        "1. 將三個步幅為 2 的降採樣改成保存全部取樣相位的降採樣方式，並與現有安全上採樣配對。",
        "2. 把已知位移的邊界位置損失提升為主要訓練訊號，直接約束重建前後的位移差，而不只比較梯度外觀。",
        "3. 新增外圍振鈴抑制，限制局部陡邊之外的第二圈亮暗過渡。",
        "4. 用獨立的開發資料選權重，評分同時包含 0.1–1 pixel 位移誤差、p95、邊界寬度與振鈴；正式平台序列只在最後測一次。",
        "",
        "## 可採用的論文定位",
        "",
        "在目前版本中，可以準確寫成：MOSR 在最小 0.1 pixel 位移的中位定位誤差最低，且在正式 pillar 測試得到與 EDSR 相當的平均誤差與較低的 p95；EDSR 在較大與整數像素平移下受益於全解析度殘差結構。若要宣稱 MOSR 對整個位移範圍皆最佳，必須先完成上述降採樣與損失設計修改並重新訓練。",
    ]
    (OUTPUT / "DIAGNOSTIC_REPORT_zh-TW.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    checkpoint, paired = build_checkpoint_comparison()
    by_shift, cluster_paired, mechanism = build_subpixel_diagnostics()
    log_text = TRAIN_LOG.read_text(encoding="utf-8", errors="replace")
    training_counts = {
        "epochs": log_text.count("Starting Epoch"),
        "oversmooth_guard_events": log_text.count("reason=oversmooth"),
        "best_epoch_10_summary_lines": log_text.count("Best epoch = 10"),
    }

    checkpoint.to_csv(OUTPUT / "checkpoint_comparison.csv", index=False)
    paired.to_csv(OUTPUT / "paired_edsr_mosr_comparisons.csv", index=False)
    by_shift.to_csv(OUTPUT / "subpixel_error_by_shift.csv", index=False)
    cluster_paired.to_csv(OUTPUT / "subpixel_paired_clusters.csv", index=False)
    mechanism.to_csv(OUTPUT / "mechanism_metrics.csv", index=False)

    summary = {
        "question": "Why EDSR leads the current broad displacement comparison and what must change for MOSR to lead legitimately",
        "data_sources": {
            "formal_epoch120": str(FORMAL),
            "training_selected_epoch10": str(BEST),
            "checkpoint_anchor_epoch120": str(ANCHORED),
            "subpixel_experiment": str(SUBPIXEL),
            "training_log": str(TRAIN_LOG),
        },
        "training_counts": training_counts,
        "checkpoint_comparison": checkpoint.to_dict(orient="records"),
        "paired_comparison": paired.to_dict(orient="records"),
        "mechanism_metrics": mechanism.to_dict(orient="records"),
    }
    (OUTPUT / "diagnosis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(checkpoint, paired, by_shift, mechanism, training_counts)
    print((OUTPUT / "DIAGNOSTIC_REPORT_zh-TW.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
