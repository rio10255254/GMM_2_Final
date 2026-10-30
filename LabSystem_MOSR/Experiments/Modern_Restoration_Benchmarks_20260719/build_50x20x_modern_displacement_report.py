from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parent
INPUT = EXPERIMENT / "evaluation" / "displacement_50x20x_edrs_nafnet_refresh_20260724"
OUTPUT = INPUT / "modern_50x20x_report"
METHODS = ["Raw", "EDSR", "NAFNet", "MOSR"]
METHOD_LABELS = {"Raw": "Raw", "EDSR": "EDSR-x1", "NAFNet": "NAFNet", "MOSR": "MOSR"}
MAGNIFICATION_SEQUENCES = {
    "50x": ["50x_x_0p5um", "50x_x_1um"],
    "20x": ["20x_0p5um", "20x_1um"],
}
BOOTSTRAP_ITERATIONS = 5000
RANDOM_SEED = 20260724


def boolean_series(values: pd.Series) -> pd.Series:
    return values.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def ci(values: np.ndarray, statistic: str, rng: np.random.Generator) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return float("nan"), float("nan")
    indices = rng.integers(0, len(values), size=(BOOTSTRAP_ITERATIONS, len(values)))
    samples = values[indices]
    if statistic == "mae":
        bootstrap = np.mean(np.abs(samples), axis=1)
    elif statistic == "mean":
        bootstrap = np.mean(samples, axis=1)
    elif statistic == "sd":
        bootstrap = np.std(samples, axis=1, ddof=1)
    else:
        raise ValueError(statistic)
    return tuple(np.quantile(bootstrap, [0.025, 0.975]).tolist())


def metrics(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    residual_nm = (
        frame["signed_step_um"].to_numpy(dtype=float)
        - frame["expected_signed_step_um"].to_numpy(dtype=float)
    ) * 1000.0
    within_grid_nm = frame["within_grid_nm"].to_numpy(dtype=float)
    mae_low, mae_high = ci(residual_nm, "mae", rng)
    sd_low, sd_high = ci(residual_nm, "sd", rng)
    return {
        "common_valid_n": int(len(frame)),
        "mean_signed_bias_nm": float(np.mean(residual_nm)),
        "step_error_sd_nm": float(np.std(residual_nm, ddof=1)),
        "step_error_sd_ci95_low_nm": sd_low,
        "step_error_sd_ci95_high_nm": sd_high,
        "mae_nm": float(np.mean(np.abs(residual_nm))),
        "mae_ci95_low_nm": mae_low,
        "mae_ci95_high_nm": mae_high,
        "median_absolute_error_nm": float(np.median(np.abs(residual_nm))),
        "p95_absolute_error_nm": float(np.percentile(np.abs(residual_nm), 95.0)),
        "mean_within_grid_nm": float(np.mean(within_grid_nm)),
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = INPUT / "displacement_step_measurements.csv"
    if not source.is_file():
        raise FileNotFoundError(source)
    data = pd.read_csv(source)
    data["evaluable"] = boolean_series(data["evaluable"])
    required = {
        "sequence", "end_frame_index", "method", "evaluable", "signed_step_um",
        "within_grid_nm", "expected_signed_step_um", "morphology",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")
    data = data.loc[data["method"].isin(METHODS)].copy()
    key_columns = ["morphology", "sequence", "end_frame_index"]
    rng = np.random.default_rng(RANDOM_SEED)
    summary_rows: list[dict[str, object]] = []
    sequence_rows: list[dict[str, object]] = []
    pairwise_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []

    for morphology in ["pillar", "via"]:
        for magnification, sequences in MAGNIFICATION_SEQUENCES.items():
            subset = data.loc[
                data["morphology"].eq(morphology) & data["sequence"].isin(sequences)
            ].copy()
            expected_rows = len(sequences) * 30
            for method in METHODS:
                method_rows = subset.loc[subset["method"].eq(method)]
                if len(method_rows) != expected_rows:
                    raise RuntimeError(
                        f"{morphology} {magnification} {method}: expected {expected_rows} selected rows, found {len(method_rows)}"
                    )
                audit_rows.append({
                    "morphology": morphology,
                    "magnification": magnification,
                    "method": METHOD_LABELS[method],
                    "selected_steps": int(len(method_rows)),
                    "evaluable_steps": int(method_rows["evaluable"].sum()),
                    "evaluable_fraction": float(method_rows["evaluable"].mean()),
                })

            valid = subset.pivot(index=key_columns, columns="method", values="evaluable")
            valid = valid.reindex(columns=METHODS).fillna(False)
            common_keys = valid.index[valid.all(axis=1)].to_frame(index=False)
            if common_keys.empty:
                raise RuntimeError(f"No common valid steps for {morphology} {magnification}")

            errors_by_method: dict[str, pd.DataFrame] = {}
            for method in METHODS:
                method_frame = subset.loc[subset["method"].eq(method)].merge(
                    common_keys, on=key_columns, how="inner", validate="one_to_one"
                ).sort_values(key_columns)
                result = {
                    "morphology": morphology,
                    "magnification": magnification,
                    "method": METHOD_LABELS[method],
                    "included_sequences": ";".join(sequences),
                    **metrics(method_frame, rng),
                }
                summary_rows.append(result)
                errors_by_method[method] = method_frame.loc[
                    :, key_columns + ["signed_step_um", "expected_signed_step_um"]
                ].copy()

            for sequence in sequences:
                sequence_subset = subset.loc[subset["sequence"].eq(sequence)]
                valid_sequence = sequence_subset.pivot(
                    index=key_columns, columns="method", values="evaluable"
                ).reindex(columns=METHODS).fillna(False)
                common_sequence_keys = valid_sequence.index[valid_sequence.all(axis=1)].to_frame(index=False)
                for method in METHODS:
                    method_frame = sequence_subset.loc[sequence_subset["method"].eq(method)].merge(
                        common_sequence_keys, on=key_columns, how="inner", validate="one_to_one"
                    ).sort_values(key_columns)
                    sequence_rows.append({
                        "morphology": morphology,
                        "magnification": magnification,
                        "sequence": sequence,
                        "method": METHOD_LABELS[method],
                        **metrics(method_frame, rng),
                    })

            mosr = errors_by_method["MOSR"].copy()
            mosr["mosr_abs_error_nm"] = np.abs(
                (mosr["signed_step_um"] - mosr["expected_signed_step_um"]) * 1000.0
            )
            for comparator in ["EDSR", "NAFNet"]:
                other = errors_by_method[comparator].copy()
                other["other_abs_error_nm"] = np.abs(
                    (other["signed_step_um"] - other["expected_signed_step_um"]) * 1000.0
                )
                paired = mosr.merge(
                    other.loc[:, key_columns + ["other_abs_error_nm"]],
                    on=key_columns, how="inner", validate="one_to_one"
                )
                delta = paired["other_abs_error_nm"].to_numpy() - paired["mosr_abs_error_nm"].to_numpy()
                delta_low, delta_high = ci(delta, "mean", rng)
                pairwise_rows.append({
                    "morphology": morphology,
                    "magnification": magnification,
                    "comparison": f"MOSR vs {METHOD_LABELS[comparator]}",
                    "common_valid_n": int(len(paired)),
                    "mean_abs_error_advantage_for_mosr_nm": float(np.mean(delta)),
                    "advantage_ci95_low_nm": delta_low,
                    "advantage_ci95_high_nm": delta_high,
                    "mosr_lower_error_steps": int((delta > 0).sum()),
                    "comparator_lower_error_steps": int((delta < 0).sum()),
                    "ties": int((delta == 0).sum()),
                })

    summary = pd.DataFrame(summary_rows)
    per_sequence = pd.DataFrame(sequence_rows)
    pairwise = pd.DataFrame(pairwise_rows)
    audit = pd.DataFrame(audit_rows)
    summary.to_csv(OUTPUT / "modern_displacement_by_magnification.csv", index=False, encoding="utf-8-sig")
    per_sequence.to_csv(OUTPUT / "modern_displacement_by_sequence.csv", index=False, encoding="utf-8-sig")
    pairwise.to_csv(OUTPUT / "modern_displacement_paired_mosr_comparison.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(OUTPUT / "modern_displacement_availability_audit.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "purpose": "Strict same-step 50x/20x displacement comparison for Raw, EDSR-x1, NAFNet, and MOSR",
        "source": str(source),
        "methods": [METHOD_LABELS[method] for method in METHODS],
        "selection": "30 Raw-motion-ranked adjacent pairs per sequence; 0.5 and 1.0 um sequences are pooled only after subtracting the PI-reference step",
        "primary_population": "per-magnification common-valid intersection across Raw, EDSR-x1, NAFNet, and MOSR",
        "primary_metrics": {
            "step_error_sd_nm": "sample standard deviation of measured minus PI-reference displacement; lower is more stable",
            "mae_nm": "mean absolute measured minus PI-reference displacement; lower is more accurate",
        },
        "ci": {"method": "paired-step bootstrap percentile interval", "iterations": BOOTSTRAP_ITERATIONS, "seed": RANDOM_SEED},
    }
    (OUTPUT / "analysis_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# 50×與20×下 EDSR-x1、NAFNet 與 MOSR 的位移比較",
        "",
        "本整理以四種方法都有效的共同步次進行比較。每個倍率合併0.5 µm與1.0 µm兩個序列；合併前先扣除PI平台的實際回授步距，因此不同步距不會直接混入誤差。",
        "",
        "- 50×：每種結構每種方法均使用60步。",
        "- 20× pillar：EDSR-x1有2步無法量測，共同有效步次為58步。",
        "- 20× via：每種方法均使用60步。",
        "",
        "較小的步距殘差標準差代表同一實際步距下的讀值更穩；較小的MAE代表更接近PI平台回授位置。",
        "",
        "## 主要彙整",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## MOSR的逐步配對比較",
        "",
        "正的平均優勢代表MOSR的絕對誤差較低；負值代表比較模型較低。",
        "",
        pairwise.to_markdown(index=False, floatfmt=".3f"),
    ]
    (OUTPUT / "RESULTS_zh-TW.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print("\n" + audit.to_string(index=False))
    print("\nOutput:", OUTPUT)


if __name__ == "__main__":
    main()
