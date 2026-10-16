from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


EXPERIMENT = Path(__file__).resolve().parent
DEFAULT_OLD_ROOT = (
    EXPERIMENT
    / "evaluation"
    / "displacement_50x20x_edrs_nafnet_refresh_20260724"
)
DEFAULT_NEW_ROOT = (
    EXPERIMENT
    / "evaluation"
    / "isocontour_boundary_validation_20260724"
)
DEFAULT_OUTPUT = (
    EXPERIMENT
    / "evaluation"
    / "measurement_method_comparison_20260724"
)
CORE_PATH = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\01_CURRENT_THESIS_RESULTS_V42_CENTER9\scripts\pillar_motion_core.py"
)
METHODS = ("Raw", "NAFNet", "EDSR", "MOSR")
MORPHOLOGY_ORDER = ("pillar", "via")
MAGNIFICATION_ORDER = ("50x", "20x")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bootstrap_mean_ci(
    values: np.ndarray,
    *,
    seed: int,
    draws: int = 20_000,
) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if len(array) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    samples = rng.choice(array, size=(draws, len(array)), replace=True).mean(axis=1)
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def load_old(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path)
    table = table.loc[table["method"].isin(METHODS)].copy()
    table["magnification"] = table["sequence"].str.extract(r"^(50x|20x)")
    table["signed_error_nm"] = (
        table["signed_step_um"] - table["expected_signed_step_um"]
    ) * 1000.0
    table["absolute_error_nm"] = table["signed_error_nm"].abs()
    table["within_grid_mad_nm"] = table["within_grid_nm"]
    table["valid"] = table["evaluable"].astype(bool)
    return table


def old_common_valid(table: pd.DataFrame) -> pd.DataFrame:
    key = ["morphology", "sequence", "end_frame_index"]
    validity = (
        table.pivot_table(
            index=key,
            columns="method",
            values="valid",
            aggfunc="first",
        )
        .reindex(columns=METHODS)
        .fillna(False)
    )
    common = validity.index[validity.all(axis=1)]
    common_keys = pd.MultiIndex.from_frame(pd.DataFrame(common.tolist(), columns=key))
    indexed = table.set_index(key)
    return indexed.loc[indexed.index.isin(common_keys)].reset_index()


def summarize_groups(table: pd.DataFrame, measurement: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for group_index, (keys, group) in enumerate(
        table.groupby(["morphology", "magnification", "method"], sort=False)
    ):
        errors = group["absolute_error_nm"].to_numpy(dtype=float)
        signed = group["signed_error_nm"].to_numpy(dtype=float)
        low, high = bootstrap_mean_ci(errors, seed=20260724 + group_index)
        records.append(
            {
                "measurement": measurement,
                "morphology": keys[0],
                "magnification": keys[1],
                "method": keys[2],
                "n": len(group),
                "mae_nm": float(np.mean(errors)),
                "mae_ci95_low_nm": low,
                "mae_ci95_high_nm": high,
                "median_absolute_error_nm": float(np.median(errors)),
                "p95_absolute_error_nm": float(np.quantile(errors, 0.95)),
                "error_sd_nm": float(np.std(signed, ddof=1)),
                "median_within_grid_mad_nm": float(
                    np.median(group["within_grid_mad_nm"])
                ),
            }
        )
    return pd.DataFrame(records)


def paired_edsr_mosr(
    table: pd.DataFrame,
    measurement: str,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for group_index, ((morphology, magnification), group) in enumerate(
        table.groupby(["morphology", "magnification"], sort=False)
    ):
        pivot = group.pivot_table(
            index=["sequence", "end_frame_index"],
            columns="method",
            values="absolute_error_nm",
            aggfunc="first",
        ).dropna(subset=["EDSR", "MOSR"])
        advantage = pivot["EDSR"].to_numpy() - pivot["MOSR"].to_numpy()
        low, high = bootstrap_mean_ci(advantage, seed=20261724 + group_index)
        try:
            p_value = float(
                wilcoxon(advantage, alternative="two-sided", zero_method="wilcox").pvalue
            )
        except ValueError:
            p_value = 1.0
        records.append(
            {
                "measurement": measurement,
                "morphology": morphology,
                "magnification": magnification,
                "paired_steps": len(pivot),
                "edsr_mae_nm": float(pivot["EDSR"].mean()),
                "mosr_mae_nm": float(pivot["MOSR"].mean()),
                "advantage_for_mosr_nm": float(np.mean(advantage)),
                "ci95_low_nm": low,
                "ci95_high_nm": high,
                "mosr_win_steps": int((advantage > 0).sum()),
                "edsr_win_steps": int((advantage < 0).sum()),
                "ties": int((advantage == 0).sum()),
                "wilcoxon_p": p_value,
            }
        )
    return pd.DataFrame(records)


def build_trajectories(table: pd.DataFrame) -> pd.DataFrame:
    output: list[pd.DataFrame] = []
    for (_, _), group in table.groupby(["morphology", "sequence"], sort=False):
        order = (
            group[["end_frame_index", "raw_motion_quality_rank"]]
            .drop_duplicates()
            .sort_values("end_frame_index")
            .reset_index(drop=True)
        )
        if len(order) != 30:
            raise RuntimeError("Each morphology/sequence must contain exactly 30 steps")
        order["selected_step"] = np.arange(1, 31)
        joined = group.merge(
            order,
            on=["end_frame_index", "raw_motion_quality_rank"],
            how="inner",
            validate="many_to_one",
        )
        joined["measured_amplitude_um"] = joined["signed_step_um"].abs()
        joined["pi_reference_amplitude_um"] = (
            joined["expected_signed_step_um"].abs()
        )
        output.append(
            joined[
                [
                    "morphology",
                    "magnification",
                    "sequence",
                    "selected_step",
                    "end_frame_index",
                    "raw_motion_quality_rank",
                    "method",
                    "measured_amplitude_um",
                    "pi_reference_amplitude_um",
                ]
            ]
        )
    return pd.concat(output, ignore_index=True)


def synthetic_circle(
    *,
    center_x: float,
    center_y: float,
    radius: float,
    polarity: str,
    blur_sigma: float,
    ringing_strength: float,
    noise_sigma: float,
    seed: int,
    size: int = 192,
    oversample: int = 6,
) -> np.ndarray:
    height = size * oversample
    width = size * oversample
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    x = (x + 0.5) / oversample
    y = (y + 0.5) / oversample
    inside = (x - center_x) ** 2 + (y - center_y) ** 2 <= radius**2
    if polarity == "dark":
        image = np.where(inside, 58.0, 198.0)
    else:
        image = np.where(inside, 198.0, 58.0)
    image = cv2.resize(
        image.astype(np.float32),
        (size, size),
        interpolation=cv2.INTER_AREA,
    )
    if blur_sigma > 0:
        image = cv2.GaussianBlur(image, (0, 0), sigmaX=blur_sigma)
    if ringing_strength > 0:
        low_pass = cv2.GaussianBlur(image, (0, 0), sigmaX=1.15)
        image = image + ringing_strength * (image - low_pass)
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        image = image + rng.normal(0.0, noise_sigma, size=image.shape)
    return np.clip(image, 0, 255).astype(np.uint8)


def synthetic_validation(
    old_core,
    isocontour_module,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    shifts = (0.25, 0.50, 1.00, 3.00)
    radii = (7.6, 19.0)
    blur_sigmas = (0.8, 1.5, 2.5)
    ringing_strengths = (0.0, 0.8, 1.6)
    noise_sigmas = (0.0, 1.2)
    prediction_errors = (-0.35, 0.35)
    center_x = 95.3
    center_y = 96.2
    case_index = 0
    for polarity in ("dark", "bright"):
        for radius in radii:
            for blur_sigma in blur_sigmas:
                for ringing_strength in ringing_strengths:
                    for noise_sigma in noise_sigmas:
                        for prediction_error in prediction_errors:
                            for shift in shifts:
                                case_index += 1
                                first = synthetic_circle(
                                    center_x=center_x,
                                    center_y=center_y,
                                    radius=radius,
                                    polarity=polarity,
                                    blur_sigma=blur_sigma,
                                    ringing_strength=ringing_strength,
                                    noise_sigma=noise_sigma,
                                    seed=case_index * 2,
                                )
                                second = synthetic_circle(
                                    center_x=center_x + shift,
                                    center_y=center_y,
                                    radius=radius,
                                    polarity=polarity,
                                    blur_sigma=blur_sigma,
                                    ringing_strength=ringing_strength,
                                    noise_sigma=noise_sigma,
                                    seed=case_index * 2 + 1,
                                )
                                search_radius = max(4.0, radius * 0.48)
                                config = old_core.TrackerConfig(
                                    radius_px=radius,
                                    pitch_px=radius * 4.0 + 20.0,
                                    polarity=polarity,
                                    search_radius_px=search_radius,
                                    min_valid_pillars=1,
                                    min_edge_strength=0.5,
                                )
                                old_first = old_core.measure_pillar_x(
                                    first,
                                    predicted_x_px=center_x + prediction_error,
                                    predicted_y_px=center_y,
                                    config=config,
                                )
                                old_second = old_core.measure_pillar_x(
                                    second,
                                    predicted_x_px=center_x + shift + prediction_error,
                                    predicted_y_px=center_y,
                                    config=config,
                                )
                                new_first = isocontour_module.measure_feature(
                                    first,
                                    predicted_x_px=center_x + prediction_error,
                                    predicted_y_px=center_y,
                                    radius_px=radius,
                                    search_radius_px=search_radius,
                                )
                                new_second = isocontour_module.measure_feature(
                                    second,
                                    predicted_x_px=center_x + shift + prediction_error,
                                    predicted_y_px=center_y,
                                    radius_px=radius,
                                    search_radius_px=search_radius,
                                )
                                for measurement, first_result, second_result in (
                                    ("original_gradient", old_first, old_second),
                                    ("new_isocontour", new_first, new_second),
                                ):
                                    valid = bool(first_result.valid and second_result.valid)
                                    measured = (
                                        float(second_result.x_px - first_result.x_px)
                                        if valid
                                        else np.nan
                                    )
                                    rows.append(
                                        {
                                            "measurement": measurement,
                                            "polarity": polarity,
                                            "radius_px": radius,
                                            "blur_sigma_px": blur_sigma,
                                            "ringing_strength": ringing_strength,
                                            "noise_sigma_8bit": noise_sigma,
                                            "prediction_error_px": prediction_error,
                                            "true_shift_px": shift,
                                            "valid": valid,
                                            "measured_shift_px": measured,
                                            "absolute_error_px": (
                                                abs(measured - shift)
                                                if valid
                                                else np.nan
                                            ),
                                        }
                                    )
    return pd.DataFrame(rows)


def summarize_synthetic(table: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for keys, group in table.groupby(
        ["measurement", "ringing_strength"], sort=False
    ):
        valid = group.loc[group["valid"]].copy()
        records.append(
            {
                "measurement": keys[0],
                "ringing_strength": keys[1],
                "cases": len(group),
                "valid_cases": len(valid),
                "valid_rate": len(valid) / len(group),
                "mae_px": float(valid["absolute_error_px"].mean()),
                "median_absolute_error_px": float(
                    valid["absolute_error_px"].median()
                ),
                "p95_absolute_error_px": float(
                    valid["absolute_error_px"].quantile(0.95)
                ),
                "max_absolute_error_px": float(valid["absolute_error_px"].max()),
            }
        )
    return pd.DataFrame(records)


def write_report(
    output: Path,
    audit: dict[str, object],
    summary: pd.DataFrame,
    paired: pd.DataFrame,
    synthetic_summary: pd.DataFrame,
) -> None:
    new_summary = summary.loc[summary["measurement"].eq("new_isocontour")]
    old_summary = summary.loc[summary["measurement"].eq("original_gradient")]
    lines = [
        "# 位移邊界量測方法比較",
        "",
        "## 資料完整性",
        "",
        f"- 舊法原始列數：{audit['old_rows']}；新法原始列數：{audit['new_rows']}。",
        f"- 四方法共同有效的舊法資料為 {audit['old_common_rows']} 列；新法為 {audit['new_common_rows']} 列。",
        f"- 新舊方法可逐步配對的資料為 {audit['matched_rows']} 列。",
        f"- 重複主鍵：舊法 {audit['old_duplicate_keys']}，新法 {audit['new_duplicate_keys']}。",
        "",
        "## 方法判讀",
        "",
        "- 舊法以左右邊緣最大灰階斜率的中點定位，對單一而平滑的邊緣很直接，但較容易受到振鈴或多重斜率峰影響。",
        "- 新法以30%、40%、50%、60%與70%局部對比交點的中位數定位，與CD的跨閾值邊界定義一致，也能直接檢查閾值敏感度。",
        "- 是否採用新法不能只看MOSR排名；本資料包同時保留實拍結果、合成已知位移測試與新舊方法配對差異。",
        "",
        "## 新法的實拍結果",
        "",
    ]
    for morphology in MORPHOLOGY_ORDER:
        for magnification in MAGNIFICATION_ORDER:
            block = new_summary.loc[
                new_summary["morphology"].eq(morphology)
                & new_summary["magnification"].eq(magnification)
            ].sort_values("mae_nm")
            ranking = " < ".join(
                f"{row.method} {row.mae_nm:.3f} nm"
                for row in block.itertuples(index=False)
            )
            lines.append(f"- {magnification} {morphology}：{ranking}。")
    lines.extend(
        [
            "",
            "## EDSR與MOSR配對比較",
            "",
        ]
    )
    for row in paired.itertuples(index=False):
        direction = "MOSR較低" if row.advantage_for_mosr_nm > 0 else "EDSR較低"
        lines.append(
            f"- {row.measurement}／{row.magnification} {row.morphology}："
            f"{direction}，差值 {abs(row.advantage_for_mosr_nm):.3f} nm，"
            f"95%區間 [{row.ci95_low_nm:.3f}, {row.ci95_high_nm:.3f}] nm。"
        )
    lines.extend(
        [
            "",
            "## 合成已知位移檢查",
            "",
        ]
    )
    for row in synthetic_summary.itertuples(index=False):
        lines.append(
            f"- {row.measurement}，振鈴強度 {row.ringing_strength:.1f}："
            f"有效率 {row.valid_rate * 100:.1f}%，MAE {row.mae_px:.4f} px，"
            f"P95 {row.p95_absolute_error_px:.4f} px。"
        )
    lines.extend(
        [
            "",
            "## 初步結論",
            "",
            "- 新法在量測定義上較容易說明與稽核，建議作為邊界位置的主要候選；舊法保留為獨立敏感度檢查。",
            "- 新法讓MOSR在50倍pillar成為最低平均絕對誤差，但沒有讓MOSR在所有倍率與形貌都領先。",
            "- 因此，若後續寫入論文，應把選法理由建立在邊界定義與合成驗證，而不是建立在單一模型排名。",
            "",
            "## 舊法摘要（核對用）",
            "",
        ]
    )
    for morphology in MORPHOLOGY_ORDER:
        for magnification in MAGNIFICATION_ORDER:
            block = old_summary.loc[
                old_summary["morphology"].eq(morphology)
                & old_summary["magnification"].eq(magnification)
            ].sort_values("mae_nm")
            ranking = " < ".join(
                f"{row.method} {row.mae_nm:.3f} nm"
                for row in block.itertuples(index=False)
            )
            lines.append(f"- {magnification} {morphology}：{ranking}。")
    (output / "METHOD_COMPARISON_REPORT_zh-TW.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def run(old_root: Path, new_root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    old = load_old(old_root / "displacement_step_measurements.csv")
    new = pd.read_csv(new_root / "step_measurements_locked30.csv")
    new = new.loc[new["method"].isin(METHODS)].copy()
    old_common = old_common_valid(old)
    new_common = new.loc[new["common_valid"].astype(bool)].copy()

    key = ["morphology", "sequence", "end_frame_index", "method"]
    old_duplicates = int(old.duplicated(key).sum())
    new_duplicates = int(new.duplicated(key).sum())
    if old_duplicates or new_duplicates:
        raise RuntimeError("Duplicate step keys detected")

    matched = old_common.merge(
        new_common,
        on=key,
        how="inner",
        suffixes=("_old", "_new"),
        validate="one_to_one",
    )
    matched["old_step_um"] = matched["signed_step_um_old"]
    matched["new_step_um"] = matched["signed_step_um_new"]
    matched["new_minus_old_step_nm"] = (
        matched["new_step_um"] - matched["old_step_um"]
    ) * 1000.0
    matched["absolute_method_disagreement_nm"] = matched[
        "new_minus_old_step_nm"
    ].abs()

    summary = pd.concat(
        [
            summarize_groups(old_common, "original_gradient"),
            summarize_groups(new_common, "new_isocontour"),
        ],
        ignore_index=True,
    )
    paired = pd.concat(
        [
            paired_edsr_mosr(old_common, "original_gradient"),
            paired_edsr_mosr(new_common, "new_isocontour"),
        ],
        ignore_index=True,
    )
    trajectories = build_trajectories(new_common)
    thresholds = pd.read_csv(new_root / "threshold_level_summary.csv")

    old_core = load_module("measurement_comparison_pillar_motion_core", CORE_PATH)
    isocontour_module = load_module(
        "measurement_comparison_isocontour",
        EXPERIMENT / "analyze_isocontour_boundary_displacement.py",
    )
    synthetic = synthetic_validation(old_core, isocontour_module)
    synthetic_summary = summarize_synthetic(synthetic)

    audit = {
        "old_rows": len(old),
        "new_rows": len(new),
        "old_common_rows": len(old_common),
        "new_common_rows": len(new_common),
        "matched_rows": len(matched),
        "old_duplicate_keys": old_duplicates,
        "new_duplicate_keys": new_duplicates,
        "old_common_counts": {
            "|".join(map(str, key_values)): int(value)
            for key_values, value in old_common.groupby(
                ["morphology", "sequence", "method"]
            ).size().items()
        },
        "new_common_counts": {
            "|".join(map(str, key_values)): int(value)
            for key_values, value in new_common.groupby(
                ["morphology", "sequence", "method"]
            ).size().items()
        },
        "synthetic_rows": len(synthetic),
        "synthetic_invalid_rows": int((~synthetic["valid"]).sum()),
    }

    summary.to_csv(
        output / "measurement_summary_by_segment.csv",
        index=False,
        encoding="utf-8-sig",
    )
    paired.to_csv(
        output / "paired_edsr_mosr_by_measurement.csv",
        index=False,
        encoding="utf-8-sig",
    )
    trajectories.to_csv(
        output / "new_isocontour_trajectories.csv",
        index=False,
        encoding="utf-8-sig",
    )
    thresholds.to_csv(
        output / "new_isocontour_threshold_sensitivity.csv",
        index=False,
        encoding="utf-8-sig",
    )
    matched[
        key
        + [
            "magnification_new",
            "old_step_um",
            "new_step_um",
            "new_minus_old_step_nm",
            "absolute_method_disagreement_nm",
        ]
    ].to_csv(
        output / "matched_step_measurement_agreement.csv",
        index=False,
        encoding="utf-8-sig",
    )
    synthetic.to_csv(
        output / "synthetic_known_shift_results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    synthetic_summary.to_csv(
        output / "synthetic_known_shift_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (output / "data_quality_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(output, audit, summary, paired, synthetic_summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-root", type=Path, default=DEFAULT_OLD_ROOT)
    parser.add_argument("--new-root", type=Path, default=DEFAULT_NEW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.old_root, args.new_root, args.output)
