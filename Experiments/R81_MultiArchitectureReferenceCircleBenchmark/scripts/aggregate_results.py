from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


R81_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from model_zoo import MODEL_SPECS  # noqa: E402


R80_TABLES = (
    Path(r"D:\GMM_2_Final\Experiments\R80_InflectionReferenceCircleSEMValidation")
    / "results"
    / "tables"
)
RESULTS = R81_ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
REPORTS = R81_ROOT / "reports"
OVERLAP_AUDIT = RESULTS / "training_frame_overlap_audit.json"
for directory in (TABLES, FIGURES, REPORTS):
    directory.mkdir(parents=True, exist_ok=True)

ORDER = (
    "srcnn", "vdsr", "dncnn", "unet", "edsr", "rdn",
    "rcan", "swinir", "nafnet", "restormer", "pft", "ucan", "mosr",
)
DISPLAY = {
    "srcnn": "SRCNN-x1",
    "vdsr": "VDSR-x1",
    "dncnn": "DnCNN",
    "unet": "Base U-Net",
    "edsr": "Compact EDSR-x1",
    "rdn": "Compact RDN-x1",
    "rcan": "Compact RCAN-x1",
    "swinir": "Compact SwinIR-x1",
    "nafnet": "Compact NAFNet",
    "restormer": "Compact Restormer",
    "pft": "Compact PFT-SR-x1*",
    "ucan": "UCAN-x1*",
    "mosr": "MOSR",
}
MOSR_PARAMETER_COUNT = 4_021_214


def require_columns(table: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns - set(table.columns)
    if missing:
        raise RuntimeError(f"{label} missing columns: {sorted(missing)}")


def external_row(key: str) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    training_path = RESULTS / "training" / key / "training_summary.json"
    evaluation_root = RESULTS / "evaluation" / key
    manifest_path = evaluation_root / "evaluation_manifest.json"
    for path in (training_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    training = json.loads(training_path.read_text(encoding="utf-8"))
    evaluation = json.loads(manifest_path.read_text(encoding="utf-8"))
    if evaluation.get("blind_external_generalization") is not False:
        raise RuntimeError(f"{key} evaluation has an unsupported generalization claim")
    if evaluation.get("formal_displacement_frames_have_training_package_crops") is not True:
        raise RuntimeError(f"{key} evaluation is missing the training-frame overlap disclosure")
    static = pd.read_csv(evaluation_root / "static_summary.csv")
    per_static = pd.read_csv(evaluation_root / "static_per_pillar.csv")
    displacement = pd.read_csv(evaluation_root / "displacement_summary.csv")
    per_pair = pd.read_csv(evaluation_root / "displacement_per_pair.csv")
    require_columns(static, {"magnification", "median_abs_error_nm"}, f"{key} static")
    combined = displacement[displacement["scope"] == "all_four_sequences"]
    if len(combined) != 1:
        raise RuntimeError(f"{key} has {len(combined)} combined displacement rows")
    by_mag = static.set_index("magnification")
    if set(by_mag.index) != {"20x", "50x"}:
        raise RuntimeError(f"{key} static magnifications: {set(by_mag.index)}")
    combined_row = combined.iloc[0]
    validation = training["best_validation"]
    row = {
        "model_key": key,
        "model": DISPLAY[key],
        "year": MODEL_SPECS[key].year,
        "category": MODEL_SPECS[key].category,
        "parameter_count": int(training["parameter_count"]),
        "parameter_m": float(training["parameter_count"]) / 1e6,
        "training_crop_px": int(training["config"]["crop_size"]),
        "best_epoch": int(training["best_epoch"]),
        "validation_l1": float(validation["l1"]),
        "validation_ssim": float(validation["ssim"]),
        "cd_20x_median_abs_error_nm": float(by_mag.loc["20x", "median_abs_error_nm"]),
        "cd_50x_median_abs_error_nm": float(by_mag.loc["50x", "median_abs_error_nm"]),
        "displacement_step_sd_nm": float(combined_row["step_sd_nm"]),
        "displacement_nominal_mae_nm": float(combined_row["mean_nominal_abs_error_nm"]),
        "displacement_within_grid_nm": float(combined_row["median_within_grid_sd_nm"]),
        "median_static_inference_seconds": float(evaluation["median_static_inference_seconds"]),
        "median_displacement_roi_inference_seconds": float(
            evaluation["median_displacement_roi_inference_seconds"]
        ),
        "formal_measurement_backend": True,
        "grayscale_threshold_used": False,
        "training_protocol": "common_external_128px_15epoch",
    }
    return row, per_static, per_pair


def mosr_row() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    static_summary = pd.read_csv(R80_TABLES / "static_center9_reference_circles_summary.csv")
    static_per = pd.read_csv(R80_TABLES / "static_center9_reference_circles_per_pillar.csv")
    displacement_summary = pd.read_csv(R80_TABLES / "displacement_lsc_summary_all.csv")
    displacement_per = pd.read_csv(R80_TABLES / "displacement_lsc_per_pair_all.csv")
    static_summary = static_summary[static_summary["method"] == "MOSR"].set_index("magnification")
    static_per = static_per[static_per["method"] == "MOSR"].copy()
    displacement_summary = displacement_summary[
        (displacement_summary["method"] == "MOSR")
        & (displacement_summary["scope"] == "all_four_sequences")
    ]
    displacement_per = displacement_per[displacement_per["method"] == "MOSR"].copy()
    if len(displacement_summary) != 1 or len(static_per) != 18 or len(displacement_per) != 120:
        raise RuntimeError("R80 MOSR evidence is incomplete")
    d = displacement_summary.iloc[0]
    row = {
        "model_key": "mosr",
        "model": DISPLAY["mosr"],
        "year": 2026,
        "category": "measurement-oriented proposed model",
        "parameter_count": MOSR_PARAMETER_COUNT,
        "parameter_m": MOSR_PARAMETER_COUNT / 1e6,
        "training_crop_px": np.nan,
        "best_epoch": 120,
        "validation_l1": np.nan,
        "validation_ssim": np.nan,
        "cd_20x_median_abs_error_nm": float(static_summary.loc["20x", "median_abs_error_nm"]),
        "cd_50x_median_abs_error_nm": float(static_summary.loc["50x", "median_abs_error_nm"]),
        "displacement_step_sd_nm": float(d["step_sd_nm"]),
        "displacement_nominal_mae_nm": float(d["mean_nominal_abs_error_nm"]),
        "displacement_within_grid_nm": float(d["median_within_grid_sd_nm"]),
        "median_static_inference_seconds": np.nan,
        "median_displacement_roi_inference_seconds": np.nan,
        "formal_measurement_backend": True,
        "grayscale_threshold_used": False,
        "training_protocol": "mosr_measurement_oriented_final_v42",
    }
    return row, static_per, displacement_per


def pair_identity(table: pd.DataFrame) -> set[tuple[str, int, int]]:
    return set(
        zip(
            table["sequence"].astype(str),
            table["start_frame_index"].astype(int),
            table["end_frame_index"].astype(int),
        )
    )


def add_metric_ranks(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    metrics = (
        "cd_20x_median_abs_error_nm",
        "cd_50x_median_abs_error_nm",
        "displacement_step_sd_nm",
        "displacement_nominal_mae_nm",
        "displacement_within_grid_nm",
    )
    for metric in metrics:
        result[f"rank_{metric}"] = result[metric].rank(method="min", ascending=True).astype(int)
    return result


def plot_summary(summary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 13
    plt.rcParams["axes.labelsize"] = 14
    plt.rcParams["xtick.labelsize"] = 12
    plt.rcParams["ytick.labelsize"] = 12
    ordered = summary.set_index("model_key").loc[list(ORDER)]
    metrics = (
        ("cd_20x_median_abs_error_nm", "20× LSC直徑絕對誤差中位數 (nm)"),
        ("cd_50x_median_abs_error_nm", "50× LSC直徑絕對誤差中位數 (nm)"),
        ("displacement_step_sd_nm", "四序列平均逐步位移標準差 (nm)"),
        ("displacement_within_grid_nm", "九顆pillar位移離散度中位數 (nm)"),
    )
    colors = ["#7A93A8"] * len(ordered)
    colors[list(ORDER).index("pft")] = "#D9A441"
    colors[list(ORDER).index("ucan")] = "#6A9F58"
    colors[list(ORDER).index("mosr")] = "#2878B5"
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.2), constrained_layout=True)
    y = np.arange(len(ordered))
    for ax, (column, label) in zip(axes.flat, metrics):
        values = ordered[column].to_numpy(float)
        ax.barh(y, values, color=colors, alpha=0.9)
        maximum = float(np.max(values))
        ax.set_xlim(0.0, maximum * 1.18 if maximum > 0.0 else 1.0)
        ax.set_yticks(y, ordered["model"], fontsize=12)
        ax.invert_yaxis()
        ax.set_xlabel(label)
        ax.grid(axis="x", alpha=0.25)
        for index, value in enumerate(values):
            ax.text(value, index, f" {value:.2f}", va="center", fontsize=11.5)
    fig.savefig(
        FIGURES / "01_thirteen_model_reference_circle_comparison.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


def write_report(summary: pd.DataFrame) -> None:
    metrics = {
        "20× CD": "cd_20x_median_abs_error_nm",
        "50× CD": "cd_50x_median_abs_error_nm",
        "逐步位移標準差": "displacement_step_sd_nm",
        "名義步距平均絕對誤差": "displacement_nominal_mae_nm",
        "九顆pillar位移離散度": "displacement_within_grid_nm",
    }
    lines = [
        "# R81 十三模型共同量測結果",
        "",
        "十二個外部模型以相同訓練資料、分組切分、128-pixel裁切、15-epoch上限與最佳驗證權重規則重新訓練。MOSR保留其量測導向訓練；十三者的正式比較只在完全相同的鎖定影像與ACM＋最大梯度轉折點＋參考圓後端進行。",
        "",
        "PFT-SR-x1*為2025年官方PFT核心的六層、單通道、等尺寸精簡改寫，不是官方公開預訓練成績。",
        "UCAN-x1*為2026年官方UCAN核心的單通道、等尺寸改寫，不是官方公開預訓練成績。",
        "",
        "## 各指標最低值",
        "",
    ]
    for label, column in metrics.items():
        winner = summary.loc[summary[column].idxmin()]
        lines.append(f"- {label}: {winner['model']}，{winner[column]:.2f} nm。")
    lines.extend(
        [
            "",
            "## 解讀界線",
            "",
            "- 不把五個指標事後平均成單一總分；每一項分開報告。",
            "- PI平台只提供名義設定步距，不是獨立干涉儀真值。",
            "- 四組正式位移序列的所有入選影格都有對應裁切出現在訓練封裝，因此這是同系統受控比較，不是外部資料盲測。",
            "- Raw為取像參考而非學習模型，Wiener為中心九顆校準區域參考，兩者不計入十三模型數量。",
            "- 全流程未使用灰階閾值，也未依模型表現重選影格。",
            "",
        ]
    )
    (REPORTS / "R81_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows: list[dict[str, object]] = []
    static_tables: dict[str, pd.DataFrame] = {}
    pair_tables: dict[str, pd.DataFrame] = {}
    for key in ORDER[:-1]:
        row, static, pairs = external_row(key)
        rows.append(row)
        static_tables[key] = static
        pair_tables[key] = pairs
    row, static, pairs = mosr_row()
    rows.append(row)
    static_tables["mosr"] = static
    pair_tables["mosr"] = pairs
    summary = pd.DataFrame(rows)
    summary["order"] = summary["model_key"].map({key: i for i, key in enumerate(ORDER)})
    summary = summary.sort_values("order").drop(columns="order").reset_index(drop=True)

    if len(summary) != 13 or set(summary["model_key"]) != set(ORDER):
        raise RuntimeError("thirteen-model roster is incomplete")
    reference_pairs = pair_identity(pair_tables["mosr"])
    if len(reference_pairs) != 120:
        raise RuntimeError(f"MOSR pair identity count is {len(reference_pairs)}")
    for key, table in pair_tables.items():
        identities = pair_identity(table)
        if identities != reference_pairs:
            raise RuntimeError(
                f"pair identity mismatch for {key}: missing={len(reference_pairs-identities)}, "
                f"extra={len(identities-reference_pairs)}"
            )
    for key, table in static_tables.items():
        identity = set(
            zip(table["magnification"].astype(str), table["pillar_image_index"].astype(int))
        )
        expected = {(magnification, pillar) for magnification in ("20x", "50x") for pillar in range(1, 10)}
        if identity != expected:
            raise RuntimeError(f"static identity mismatch for {key}")
    numeric = summary[
        [
            "cd_20x_median_abs_error_nm",
            "cd_50x_median_abs_error_nm",
            "displacement_step_sd_nm",
            "displacement_nominal_mae_nm",
            "displacement_within_grid_nm",
        ]
    ].to_numpy(float)
    if not np.isfinite(numeric).all():
        raise RuntimeError("non-finite formal measurement metric")
    if summary["grayscale_threshold_used"].astype(bool).any():
        raise RuntimeError("threshold-based result entered formal table")
    external_summary = summary[summary["model_key"] != "mosr"]
    if set(external_summary["training_crop_px"].astype(int)) != {128}:
        raise RuntimeError("external architecture crop sizes are not uniformly 128 pixels")
    if set(external_summary["training_protocol"].astype(str)) != {
        "common_external_128px_15epoch"
    }:
        raise RuntimeError("external architecture training protocol is inconsistent")

    summary = add_metric_ranks(summary)
    summary.to_csv(TABLES / "thirteen_model_measurement_summary.csv", index=False, encoding="utf-8-sig")
    if not OVERLAP_AUDIT.is_file():
        raise FileNotFoundError(OVERLAP_AUDIT)
    overlap_audit = json.loads(OVERLAP_AUDIT.read_text(encoding="utf-8"))
    if overlap_audit.get("blind_external_generalization") is not False:
        raise RuntimeError("training-frame overlap audit has an unexpected claim")
    unique_frames = {
        key: int(value["selected_unique_frames"])
        for key, value in overlap_audit["sequence_audit"].items()
    }
    qa = {
        "model_count": len(summary),
        "external_model_count": 12,
        "classic_or_seminal_models": ["SRCNN", "VDSR", "DnCNN", "U-Net", "EDSR", "RDN", "RCAN"],
        "latest_representative": "UCAN, CVPR 2026",
        "latest_representative_source_commit": "b812c0adb8ce70d442973db5c87bab7d1e8c3333",
        "declared_same_resolution_adaptations": ["Compact PFT-SR-x1*", "UCAN-x1*"],
        "external_means_architecture_not_dataset": True,
        "static_center9_is_psf_and_scale_calibration_region": True,
        "formal_displacement_frames_have_training_package_crops": True,
        "unique_formal_frames_by_sequence": unique_frames,
        "blind_external_generalization_claimed": False,
        "static_measurements_per_model": 18,
        "locked_displacement_pairs_per_model": 120,
        "same_pair_identity": True,
        "same_static_identity": True,
        "grayscale_threshold_used": False,
        "composite_posthoc_score_used": False,
    }
    (RESULTS / "data_quality_audit.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot_summary(summary)
    write_report(summary)
    print(summary.to_string(index=False))
    print(json.dumps(qa, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
