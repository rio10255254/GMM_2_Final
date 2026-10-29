from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat


SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE = SCRIPT_DIR.parent
RESULTS = PACKAGE / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
QA = RESULTS / "qa"
for directory in (TABLES, FIGURES, QA):
    directory.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPT_DIR))
from reference_circle_core import (  # noqa: E402
    crop_around,
    measure_inflection_lsc,
    wiener_contrast_restore,
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


PACKAGE_CENTER9 = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9')
)
CONFIG_PATH = PACKAGE_CENTER9 / "config" / "sequence_center9_50x20x.json"
AUDIT_TABLE = (
    PACKAGE_CENTER9
    / "diagnostics"
    / "unified_displacement_step_audit"
    / "tables"
    / "raw_eligibility_locked_before_v42.csv"
)
SESSION_TABLE = AUDIT_TABLE.parent / "session_anchor_summary.csv"
SWEEP_ROOT = Path(str(PROJECT_ROOT / 'PSF_Fitting/tests/artifacts/cd_verification_20260714'))

NSR = 0.0565
METHODS = ("Raw", "Wiener", "MOSR")
COLORS = {"Raw": "#555555", "Wiener": "#D97904", "MOSR": "#2878B5"}

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def selected_pairs(sequence: str, limit_pairs: int = 30) -> pd.DataFrame:
    audit = pd.read_csv(AUDIT_TABLE)
    subset = audit[
        (audit["sequence"] == sequence)
        & audit["raw_eligible_25pct"].astype(bool)
        & (~audit["cross_session"].astype(bool))
    ].copy()
    subset["raw_nominal_abs_error_um"] = np.abs(
        subset["raw_boundary_dx_um"] - subset["expected_signed_step_um"]
    )
    subset = subset.sort_values(
        ["raw_nominal_abs_error_um", "raw_within_grid_nm", "start_frame_index"],
        kind="mergesort",
    ).head(int(limit_pairs))
    return subset.sort_values("start_frame_index").reset_index(drop=True)


def session_prediction(
    sequence: str,
    frame_index: int,
    base_centers: np.ndarray,
    expected_dx_px: float,
) -> np.ndarray:
    sessions = pd.read_csv(SESSION_TABLE)
    candidates = sessions[
        (sessions["sequence"] == sequence)
        & (sessions["start_frame_index"] <= frame_index)
        & (sessions["end_frame_index"] >= frame_index)
    ]
    if len(candidates) != 1:
        raise ValueError(f"frame {frame_index} in {sequence} has {len(candidates)} session records")
    session = candidates.iloc[0]
    delta_index = int(frame_index - int(session["start_frame_index"]))
    predicted = base_centers.copy()
    predicted[:, 1] += float(session["anchor_offset_x_px"]) + delta_index * float(expected_dx_px)
    predicted[:, 2] += float(session["anchor_offset_y_px"])
    return predicted


def load_grayscale(path: Path) -> np.ndarray:
    if not path.is_file():
        raise FileNotFoundError(path)
    array = np.asarray(Image.open(path), dtype=np.float64)
    if array.ndim == 3:
        array = np.mean(array[:, :, :3], axis=2)
    return array / 255.0


def process_sequence(sequence: str, config: dict, limit_pairs: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    specification = config["sequences"][sequence]
    pairs = selected_pairs(sequence, limit_pairs=limit_pairs)
    frame_indices = sorted(
        set(pairs["start_frame_index"].astype(int)) | set(pairs["end_frame_index"].astype(int))
    )
    base_centers = np.asarray(specification["centers"], dtype=float)
    raw_dir = Path(PROJECT_ROOT / specification["raw_dir"])
    mosr_dir = Path(PROJECT_ROOT / specification["v42_dir"])
    magnification = specification["magnification"]
    pitch = float(specification["pitch_px"])
    radius = float(specification["radius_px"])
    scale = float(specification["object_um_per_px"])
    expected_dx_px = float(specification["expected_signed_dx_px"])
    patch_half = int(np.ceil(0.46 * pitch))
    sample_count = 64 if magnification == "20x" else 96
    acm_iterations = 13 if magnification == "20x" else 15
    normal_half = 2.4 if magnification == "20x" else 4.0
    psf = np.asarray(loadmat(SWEEP_ROOT / f"{magnification}_deconvolution_sweep.mat", squeeze_me=True)["psf"], dtype=float)

    center_rows: list[dict[str, object]] = []
    for frame_index in frame_indices:
        filename = f"frame_{frame_index:04d}.bmp"
        raw = load_grayscale(raw_dir / filename)
        mosr = load_grayscale(mosr_dir / filename)
        predicted = session_prediction(sequence, frame_index, base_centers, expected_dx_px)

        margin = int(np.ceil(0.55 * pitch))
        x0 = max(0, int(np.floor(np.min(predicted[:, 1]))) - margin)
        x1 = min(raw.shape[1], int(np.ceil(np.max(predicted[:, 1]))) + margin + 1)
        y0 = max(0, int(np.floor(np.min(predicted[:, 2]))) - margin)
        y1 = min(raw.shape[0], int(np.ceil(np.max(predicted[:, 2]))) + margin + 1)
        raw_roi = raw[y0:y1, x0:x1]
        mosr_roi = mosr[y0:y1, x0:x1]
        wiener_roi = wiener_contrast_restore(raw_roi, psf, NSR, pitch_px=pitch)
        method_images = {"Raw": raw_roi, "Wiener": wiener_roi, "MOSR": mosr_roi}

        for method, image in method_images.items():
            for pillar_id, predicted_x, predicted_y in predicted:
                local_center = (float(predicted_x - x0), float(predicted_y - y0))
                patch, patch_center, patch_origin = crop_around(image, local_center, patch_half)
                measurement = measure_inflection_lsc(
                    patch,
                    patch_center,
                    radius,
                    sample_count=sample_count,
                    acm_iterations=acm_iterations,
                    normal_half_width_px=normal_half,
                    polarity="dark",
                )
                global_x = measurement.lsc.cx + patch_origin[0] + x0
                global_y = measurement.lsc.cy + patch_origin[1] + y0
                center_rows.append(
                    {
                        "sequence": sequence,
                        "magnification": magnification,
                        "frame_index": frame_index,
                        "method": method,
                        "pillar_id": int(pillar_id),
                        "predicted_x_px": float(predicted_x),
                        "predicted_y_px": float(predicted_y),
                        "lsc_center_x_px": global_x,
                        "lsc_center_y_px": global_y,
                        "lsc_radius_px": measurement.lsc.radius,
                        "gradient_strength_median": float(np.median(measurement.signed_gradient_strength)),
                        "object_um_per_px": scale,
                    }
                )

    centers = pd.DataFrame(center_rows)
    pair_rows: list[dict[str, object]] = []
    indexed = centers.set_index(["method", "frame_index", "pillar_id"])
    for pair_rank, pair in pairs.iterrows():
        start = int(pair["start_frame_index"])
        end = int(pair["end_frame_index"])
        for method in METHODS:
            pillar_dx: list[float] = []
            pillar_dy: list[float] = []
            for pillar_id in base_centers[:, 0].astype(int):
                before = indexed.loc[(method, start, pillar_id)]
                after = indexed.loc[(method, end, pillar_id)]
                dx_um = (float(after["lsc_center_x_px"]) - float(before["lsc_center_x_px"])) * scale
                dy_um = (float(after["lsc_center_y_px"]) - float(before["lsc_center_y_px"])) * scale
                pillar_dx.append(dx_um)
                pillar_dy.append(dy_um)
            aggregate_dx = float(np.median(pillar_dx))
            aggregate_dy = float(np.median(pillar_dy))
            nominal = float(specification["nominal_step_um"])
            pair_rows.append(
                {
                    "sequence": sequence,
                    "magnification": magnification,
                    "pair_rank_raw_locked": pair_rank + 1,
                    "start_frame_index": start,
                    "end_frame_index": end,
                    "method": method,
                    "nominal_step_um": nominal,
                    "aggregate_dx_um": aggregate_dx,
                    "aggregate_dy_um": aggregate_dy,
                    "measured_step_um": abs(aggregate_dx),
                    "nominal_abs_error_nm": abs(abs(aggregate_dx) - nominal) * 1000.0,
                    "within_grid_sd_nm": float(np.std(pillar_dx, ddof=1) * 1000.0),
                    "cross_axis_abs_nm": abs(aggregate_dy) * 1000.0,
                }
            )
    return centers, pd.DataFrame(pair_rows)


def summarize_pairs(per_pair: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (sequence, method), group in per_pair.groupby(["sequence", "method"], sort=False):
        rows.append(
            {
                "scope": "per_sequence",
                "sequence": sequence,
                "magnification": group["magnification"].iloc[0],
                "method": method,
                "n_pairs": len(group),
                "step_sd_nm": float(np.std(group["measured_step_um"], ddof=1) * 1000.0),
                "mean_nominal_abs_error_nm": float(np.mean(group["nominal_abs_error_nm"])),
                "median_within_grid_sd_nm": float(np.median(group["within_grid_sd_nm"])),
                "median_cross_axis_abs_nm": float(np.median(group["cross_axis_abs_nm"])),
            }
        )
    for method, group in per_pair.groupby("method", sort=False):
        rows.append(
            {
                "scope": "all_four_sequences",
                "sequence": "combined",
                "magnification": "20x+50x",
                "method": method,
                "n_pairs": len(group),
                "step_sd_nm": float(
                    np.mean(
                        [
                            np.std(sequence_group["measured_step_um"], ddof=1) * 1000.0
                            for _, sequence_group in group.groupby("sequence")
                        ]
                    )
                ),
                "mean_nominal_abs_error_nm": float(np.mean(group["nominal_abs_error_nm"])),
                "median_within_grid_sd_nm": float(np.median(group["within_grid_sd_nm"])),
                "median_cross_axis_abs_nm": float(np.median(group["cross_axis_abs_nm"])),
            }
        )
    return pd.DataFrame(rows)


def plot_summary(summary: pd.DataFrame) -> None:
    combined = summary[summary["scope"] == "all_four_sequences"].set_index("method").loc[list(METHODS)]
    metrics = [
        ("step_sd_nm", "四序列平均步階標準差 (nm)"),
        ("mean_nominal_abs_error_nm", "相對名目步距平均絕對偏差 (nm)"),
        ("median_within_grid_sd_nm", "九顆pillar內離散度中位數 (nm)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8), constrained_layout=True)
    for ax, (metric, label) in zip(axes, metrics):
        values = combined[metric].to_numpy(float)
        bars = ax.bar(np.arange(3), values, color=[COLORS[m] for m in METHODS], alpha=0.88)
        ax.set_xticks(np.arange(3), METHODS)
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.25)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
    fig.savefig(FIGURES / "08_lsc_center_displacement_summary.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_traces(per_pair: pd.DataFrame) -> None:
    sequences = list(per_pair["sequence"].drop_duplicates())
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.0), constrained_layout=True)
    for ax, sequence in zip(axes.flat, sequences):
        subset = per_pair[per_pair["sequence"] == sequence]
        nominal = float(subset["nominal_step_um"].iloc[0])
        ax.axhline(nominal, color="#111111", ls="--", lw=1.0, label="名目步距")
        for method in METHODS:
            group = subset[subset["method"] == method].sort_values("start_frame_index")
            ax.plot(group["start_frame_index"], group["measured_step_um"], "-o", ms=3, lw=1.1, color=COLORS[method], label=method)
        ax.set_title(sequence)
        ax.set_xlabel("起始影格")
        ax.set_ylabel("LSC圓心位移 (µm)")
        ax.grid(alpha=0.25)
    axes[0, 0].legend(frameon=False, ncol=2, fontsize=8)
    fig.savefig(FIGURES / "09_lsc_center_displacement_traces.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_readout(summary: pd.DataFrame) -> None:
    combined = summary[summary["scope"] == "all_four_sequences"]
    lines = [
        "# R80 LSC圓心位移結果",
        "",
        "影格名單由Raw在分析前鎖定；每序列取Raw名目步距偏差最低且九顆完整的30組相鄰影格，Wiener與MOSR不參與選擇。",
        "",
        "每一顆pillar先以ACM取得完整粗輪廓，再沿法線取最大梯度轉折點；位移由相鄰影格的最小平方圓圓心差計算。全流程不使用灰階閾值。",
        "",
    ]
    for row in combined.itertuples(index=False):
        lines.append(
            f"- {row.method}: 四序列平均步階標準差 {row.step_sd_nm:.2f} nm，"
            f"相對名目步距平均絕對偏差 {row.mean_nominal_abs_error_nm:.2f} nm，"
            f"九顆pillar內離散度中位數 {row.median_within_grid_sd_nm:.2f} nm。"
        )
    (RESULTS / "DISPLACEMENT_LSC_READOUT_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence", action="append", choices=["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"])
    parser.add_argument("--limit-pairs", type=int, default=30)
    args = parser.parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sequences = args.sequence or list(config["sequences"].keys())

    centers_all: list[pd.DataFrame] = []
    pairs_all: list[pd.DataFrame] = []
    selection_all: list[pd.DataFrame] = []
    for sequence in sequences:
        print(f"processing {sequence}", flush=True)
        selection = selected_pairs(sequence, limit_pairs=args.limit_pairs)
        selection_all.append(selection.assign(sequence_locked=sequence))
        centers, pairs = process_sequence(sequence, config, args.limit_pairs)
        centers_all.append(centers)
        pairs_all.append(pairs)
        print(f"  frames={centers['frame_index'].nunique()} centers={len(centers)} pairs={len(pairs)}", flush=True)

    centers = pd.concat(centers_all, ignore_index=True)
    per_pair = pd.concat(pairs_all, ignore_index=True)
    selection = pd.concat(selection_all, ignore_index=True)
    summary = summarize_pairs(per_pair)
    suffix = "all" if len(sequences) == 4 else "_".join(sequences)
    centers.to_csv(TABLES / f"displacement_lsc_centers_{suffix}.csv", index=False, encoding="utf-8-sig")
    per_pair.to_csv(TABLES / f"displacement_lsc_per_pair_{suffix}.csv", index=False, encoding="utf-8-sig")
    selection.to_csv(TABLES / f"displacement_raw_locked_selection_{suffix}.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / f"displacement_lsc_summary_{suffix}.csv", index=False, encoding="utf-8-sig")
    if len(sequences) == 4:
        plot_summary(summary)
        plot_traces(per_pair)
        write_readout(summary)
        metadata = {
            "method": "ACM coarse contour + maximum-gradient inflection points + LSC center",
            "grayscale_threshold_used": False,
            "wiener_nsr": NSR,
            "selection": "30 Raw-ranked adjacent pairs per sequence, locked before Wiener/MOSR",
            "stage_reference": "nominal commanded step; no independent interferometer truth",
            "native_scales_um_per_px": {"20x": 0.1725, "50x": 0.0690},
        }
        (RESULTS / "displacement_lsc_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

