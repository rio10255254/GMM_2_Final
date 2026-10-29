from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\投稿\IMPACT2026")
ASSET_DIR = ROOT / "assets"
QA_DIR = ROOT / "qa"

COMMON_PER_PAIR = Path(
    str(PROJECT_ROOT / 'Experiments/R80_InflectionReferenceCircleSEMValidation/results/tables/displacement_lsc_per_pair_all.csv')
)

IMAGE_DIR = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/figures')
)

SEQUENCES = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]
DISPLAY_SEQUENCE = {
    "50x_x_0p5um": "50x / 0.5 µm",
    "50x_x_1um": "50x / 1.0 µm",
    "20x_0p5um": "20x / 0.5 µm",
    "20x_1um": "20x / 1.0 µm",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sample_sd(values: list[float]) -> float:
    return float(np.std(np.asarray(values, dtype=float), ddof=1))


def assemble_results() -> tuple[
    list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]
]:
    per_pair = read_csv(COMMON_PER_PAIR)

    rows: list[dict[str, object]] = []
    for sequence in SEQUENCES:
        for method in ["Raw", "Wiener", "MOSR"]:
            subset = [
                row
                for row in per_pair
                if row["sequence"] == sequence and row["method"] == method
            ]
            assert len(subset) == 30
            ranks = [int(row["pair_rank_raw_locked"]) for row in subset]
            assert ranks == list(range(1, 31))
            values = np.asarray([float(row["measured_step_um"]) for row in subset])
            nominal = float(subset[0]["nominal_step_um"])
            within = np.asarray([float(row["within_grid_sd_nm"]) for row in subset])
            rows.append(
                {
                    "sequence": sequence,
                    "condition": DISPLAY_SEQUENCE[sequence],
                    "magnification": subset[0]["magnification"],
                    "nominal_step_um": subset[0]["nominal_step_um"],
                    "method": method,
                    "n_pairs": 30,
                    "step_sd_nm": 1000.0 * sample_sd(values.tolist()),
                    "nominal_mae_nm": 1000.0 * float(np.mean(np.abs(values - nominal))),
                    "within_grid_median_nm": float(np.median(within)),
                }
            )

    by_method: dict[str, dict[str, float]] = {}
    aggregate_rows: list[dict[str, object]] = []
    for method in ["Raw", "Wiener", "MOSR"]:
        subset = [r for r in rows if r["method"] == method]
        raw_subset = [row for row in per_pair if row["method"] == method]
        nominal_abs_errors = [float(row["nominal_abs_error_nm"]) for row in raw_subset]
        within_grid = [float(row["within_grid_sd_nm"]) for row in raw_subset]
        by_method[method] = {
            "mean_of_sequence_step_sd_nm": float(np.mean([r["step_sd_nm"] for r in subset])),
            "pooled_nominal_mae_nm": float(np.mean(nominal_abs_errors)),
            "pooled_within_grid_median_nm": float(np.median(within_grid)),
        }
        aggregate_rows.append(
            {
                "condition": "All four",
                "method": method,
                "n_pairs": 120,
                "step_sd_nm": by_method[method]["mean_of_sequence_step_sd_nm"],
                "nominal_mae_nm": by_method[method]["pooled_nominal_mae_nm"],
                "within_grid_median_nm": by_method[method]["pooled_within_grid_median_nm"],
            }
        )

    mosr_sd = by_method["MOSR"]["mean_of_sequence_step_sd_nm"]
    mosr_mae = by_method["MOSR"]["pooled_nominal_mae_nm"]
    improvements = {}
    mosr_within = by_method["MOSR"]["pooled_within_grid_median_nm"]
    for baseline in ["Raw", "Wiener"]:
        improvements[baseline] = {
            "step_sd_reduction_pct": 100
            * (by_method[baseline]["mean_of_sequence_step_sd_nm"] - mosr_sd)
            / by_method[baseline]["mean_of_sequence_step_sd_nm"],
            "nominal_mae_reduction_pct": 100
            * (by_method[baseline]["pooled_nominal_mae_nm"] - mosr_mae)
            / by_method[baseline]["pooled_nominal_mae_nm"],
            "within_grid_reduction_pct": 100
            * (by_method[baseline]["pooled_within_grid_median_nm"] - mosr_within)
            / by_method[baseline]["pooled_within_grid_median_nm"],
        }

    paired: dict[str, dict[str, dict[str, np.ndarray]]] = {}
    for sequence in SEQUENCES:
        paired[sequence] = {}
        for method in ["Raw", "Wiener", "MOSR"]:
            subset = sorted(
                [
                    row
                    for row in per_pair
                    if row["sequence"] == sequence and row["method"] == method
                ],
                key=lambda row: int(row["pair_rank_raw_locked"]),
            )
            paired[sequence][method] = {
                "step": np.asarray([float(row["measured_step_um"]) * 1000 for row in subset]),
                "ae": np.asarray([float(row["nominal_abs_error_nm"]) for row in subset]),
                "grid": np.asarray([float(row["within_grid_sd_nm"]) for row in subset]),
            }

    def aggregate_metric(method: str, indices: dict[str, np.ndarray] | None = None) -> np.ndarray:
        sequence_sd = []
        absolute_errors = []
        grid_values = []
        for sequence in SEQUENCES:
            ix = np.arange(30) if indices is None else indices[sequence]
            sequence_sd.append(np.std(paired[sequence][method]["step"][ix], ddof=1))
            absolute_errors.extend(paired[sequence][method]["ae"][ix])
            grid_values.extend(paired[sequence][method]["grid"][ix])
        return np.asarray(
            [np.mean(sequence_sd), np.mean(absolute_errors), np.median(grid_values)]
        )

    rng = np.random.default_rng(20260824)
    bootstrap_replicates = 20000
    bootstrap_rows: list[dict[str, object]] = []
    metric_names = ["step_sd", "nominal_mae", "within_grid_median"]
    for baseline in ["Raw", "Wiener"]:
        observed = aggregate_metric(baseline) - aggregate_metric("MOSR")
        bootstrap = np.empty((bootstrap_replicates, 3), dtype=float)
        for replicate in range(bootstrap_replicates):
            indices = {sequence: rng.integers(0, 30, 30) for sequence in SEQUENCES}
            bootstrap[replicate] = aggregate_metric(baseline, indices) - aggregate_metric(
                "MOSR", indices
            )
        intervals = np.percentile(bootstrap, [2.5, 97.5], axis=0)
        for index, metric in enumerate(metric_names):
            bootstrap_rows.append(
                {
                    "baseline": baseline,
                    "metric": metric,
                    "baseline_minus_mosr_nm": float(observed[index]),
                    "ci95_low_nm": float(intervals[0, index]),
                    "ci95_high_nm": float(intervals[1, index]),
                }
            )

    pairwise_within_grid_counts = {}
    for baseline in ["Raw", "Wiener"]:
        baseline_values = []
        mosr_values = []
        for sequence in SEQUENCES:
            baseline_values.extend(paired[sequence][baseline]["grid"])
            mosr_values.extend(paired[sequence]["MOSR"]["grid"])
        baseline_values = np.asarray(baseline_values)
        mosr_values = np.asarray(mosr_values)
        pairwise_within_grid_counts[baseline] = {
            "mosr_lower": int(np.sum(mosr_values < baseline_values)),
            "equal": int(np.sum(mosr_values == baseline_values)),
            "n": int(len(mosr_values)),
        }

    audit = {
        "scope": "20x and 50x cross-magnification same-system controlled comparison",
        "sequences": SEQUENCES,
        "pairs_per_sequence": 30,
        "methods": ["Raw", "Wiener", "MOSR"],
        "source_files": [str(COMMON_PER_PAIR)],
        "mean_across_sequences": by_method,
        "mosr_reduction_pct": improvements,
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_results": bootstrap_rows,
        "pairwise_within_grid_counts": pairwise_within_grid_counts,
    }
    return rows, aggregate_rows, bootstrap_rows, audit


def validate_per_pair(rows: list[dict[str, object]]) -> dict[str, object]:
    common = read_csv(COMMON_PER_PAIR)
    checks: dict[str, object] = {}

    for sequence in SEQUENCES:
        checks[sequence] = {}
        for method in ["Raw", "Wiener", "MOSR"]:
            subset = [
                row
                for row in common
                if row["sequence"] == sequence and row["method"] == method
            ]
            assert len(subset) == 30
            ranks = [int(row["pair_rank_raw_locked"]) for row in subset]
            assert ranks == list(range(1, 31))
            values = [float(row["measured_step_um"]) for row in subset]
            nominal = float(subset[0]["nominal_step_um"])
            recomputed_sd = 1000.0 * sample_sd(values)
            recomputed_mae = 1000.0 * float(np.mean(np.abs(np.asarray(values) - nominal)))
            recomputed_within = float(
                np.median([float(row["within_grid_sd_nm"]) for row in subset])
            )
            expected = next(
                row
                for row in rows
                if row["sequence"] == sequence and row["method"] == method
            )
            assert abs(recomputed_sd - float(expected["step_sd_nm"])) < 1e-8
            assert abs(recomputed_mae - float(expected["nominal_mae_nm"])) < 1e-8
            assert abs(recomputed_within - float(expected["within_grid_median_nm"])) < 1e-8
            checks[sequence][method] = {
                "pair_count": 30,
                "recomputed_step_sd_nm": recomputed_sd,
                "recomputed_nominal_mae_nm": recomputed_mae,
                "recomputed_within_grid_median_nm": recomputed_within,
            }
    return checks


def make_pipeline_figure() -> Path:
    sources = [
        ("Raw", IMAGE_DIR / "01_50x_raw_center9.png"),
        ("Wiener", IMAGE_DIR / "02a_50x_wiener_center9.png"),
        ("MOSR", IMAGE_DIR / "02_50x_v42_center9.png"),
    ]
    images = []
    for _, path in sources:
        image = Image.open(path).convert("L")
        width, height = image.size
        top = min(52, height // 10)
        side = min(width, height - top)
        left = max(0, (width - side) // 2)
        crop = image.crop((left, top, left + side, top + side))
        images.append(crop)

    plt.rcParams.update({"font.family": "Times New Roman", "font.size": 7})
    fig = plt.figure(figsize=(3.36, 2.05), dpi=600)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.46], hspace=0.16, wspace=0.035)
    for index, ((label, _), image) in enumerate(zip(sources, images)):
        axis = fig.add_subplot(grid[0, index])
        axis.imshow(image, cmap="gray", vmin=0, vmax=255)
        axis.set_title(label, fontsize=7.2, pad=1.4)
        axis.set_axis_off()

    flow_axis = fig.add_subplot(grid[1, :])
    flow_axis.set_xlim(0, 1)
    flow_axis.set_ylim(0, 1)
    flow_axis.axis("off")
    labels = [
        "Single-frame\ninput",
        "ACM coarse\ncontour",
        "Max. gradient\npoints",
        "Least-squares\ncenter",
        "Frame-pair\nshift",
    ]
    centers = np.asarray([0.08, 0.275, 0.495, 0.715, 0.92])
    widths = [0.14, 0.16, 0.19, 0.17, 0.15]
    for index, (center, width, label) in enumerate(zip(centers, widths, labels)):
        flow_axis.add_patch(
            plt.Rectangle(
                (center - width / 2, 0.22),
                width,
                0.56,
                facecolor="white",
                edgecolor="black",
                linewidth=0.65,
            )
        )
        flow_axis.text(center, 0.5, label, ha="center", va="center", fontsize=4.95)
        if index < len(labels) - 1:
            flow_axis.annotate(
                "",
                xy=(centers[index + 1] - widths[index + 1] / 2 - 0.006, 0.5),
                xytext=(center + width / 2 + 0.006, 0.5),
                arrowprops={"arrowstyle": "->", "lw": 0.7, "color": "black"},
            )
    output = ASSET_DIR / "figure1_measurement_chain.png"
    fig.savefig(output, bbox_inches="tight", pad_inches=0.01, facecolor="white")
    plt.close(fig)
    return output


def make_two_page_method_figure() -> Path:
    sources = [
        ("Raw", IMAGE_DIR / "01_50x_raw_center9.png"),
        ("Fixed Wiener", IMAGE_DIR / "02a_50x_wiener_center9.png"),
        ("MOSR", IMAGE_DIR / "02_50x_v42_center9.png"),
    ]
    images = []
    for _, path in sources:
        source = Image.open(path).convert("L")
        width, height = source.size
        top = min(52, height // 10)
        side = min(width, height - top)
        left = max(0, (width - side) // 2)
        images.append(source.crop((left, top, left + side, top + side)))

    plt.rcParams.update({"font.family": "Times New Roman", "font.size": 7})
    fig = plt.figure(figsize=(3.36, 2.10), dpi=600)
    grid = fig.add_gridspec(3, 3, height_ratios=[0.90, 0.55, 0.36], hspace=0.10, wspace=0.035)

    for index, ((label, _), image) in enumerate(zip(sources, images)):
        axis = fig.add_subplot(grid[0, index])
        axis.imshow(image, cmap="gray", vmin=0, vmax=255)
        axis.set_title(label, fontsize=7.3, pad=1.0)
        axis.set_axis_off()

    method_axis = fig.add_subplot(grid[1, :])
    method_axis.set_xlim(0, 1)
    method_axis.set_ylim(0, 1)
    method_axis.axis("off")
    method_axis.text(
        0.5,
        0.96,
        "MOSR: shared 20x/50x weights",
        ha="center",
        va="center",
        fontsize=6.7,
        fontstyle="italic",
    )
    blocks = [
        (0.165, "Optical variation\nPSF guidance"),
        (0.500, "Sampling phase\nAnti-aliasing"),
        (0.835, "Geometry drift\nInput anchor"),
    ]
    box_width = 0.30
    for index, (center, label) in enumerate(blocks):
        method_axis.add_patch(
            plt.Rectangle(
                (center - box_width / 2, 0.08),
                box_width,
                0.68,
                facecolor="white",
                edgecolor="black",
                linewidth=0.65,
            )
        )
        method_axis.text(center, 0.42, label, ha="center", va="center", fontsize=6.6)
        if index < len(blocks) - 1:
            method_axis.annotate(
                "",
                xy=(blocks[index + 1][0] - box_width / 2 - 0.005, 0.42),
                xytext=(center + box_width / 2 + 0.005, 0.42),
                arrowprops={"arrowstyle": "->", "lw": 0.7, "color": "black"},
            )

    output_axis = fig.add_subplot(grid[2, :])
    output_axis.set_xlim(0, 1)
    output_axis.set_ylim(0, 1)
    output_axis.axis("off")
    output_axis.add_patch(
        plt.Rectangle((0.025, 0.06), 0.95, 0.86, facecolor="white", edgecolor="black", linewidth=0.65)
    )
    output_axis.text(
        0.50,
        0.49,
        "Raw / Wiener / MOSR\n"
        "maximum-gradient boundary -> LSC center -> displacement",
        ha="center",
        va="center",
        fontsize=6.35,
    )

    output = ASSET_DIR / "figure1_two_page_mosr_concept.png"
    fig.savefig(output, bbox_inches="tight", pad_inches=0.01, facecolor="white")
    plt.close(fig)
    return output


def make_aggregate_summary_figure(aggregate_rows: list[dict[str, object]]) -> Path:
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 7,
            "axes.linewidth": 0.65,
            "xtick.major.width": 0.55,
            "ytick.major.width": 0.55,
        }
    )
    methods = ["Raw", "Wiener", "MOSR"]
    colors = {"Raw": "0.82", "Wiener": "0.52", "MOSR": "0.08"}
    hatches = {"Raw": "..", "Wiener": "//", "MOSR": None}
    metrics = [
        ("step_sd_nm", "Step SD"),
        ("nominal_mae_nm", "Nominal\nMAE"),
        ("within_grid_median_nm", "Median\nwithin-grid SD"),
    ]
    by_method = {row["method"]: row for row in aggregate_rows}
    x = np.arange(len(metrics), dtype=float)
    width = 0.23
    fig, axis = plt.subplots(figsize=(3.36, 1.58), dpi=600)
    for method_index, method in enumerate(methods):
        values = [float(by_method[method][field]) for field, _ in metrics]
        positions = x + (method_index - 1) * width
        bars = axis.bar(
            positions,
            values,
            width=width,
            color=colors[method],
            edgecolor="black",
            linewidth=0.5,
            hatch=hatches[method],
            label=method,
        )
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.28,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=5.7,
            )
    axis.set_ylabel("Value (nm)", fontsize=7.0)
    axis.set_xticks(x)
    axis.set_xticklabels([label for _, label in metrics], fontsize=6.6)
    axis.set_ylim(0, 14.2)
    axis.set_yticks([0, 5, 10])
    axis.tick_params(axis="y", labelsize=6.3)
    axis.grid(axis="y", color="0.86", linewidth=0.45)
    axis.set_axisbelow(True)
    axis.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.24),
        ncol=3,
        frameon=False,
        fontsize=6.5,
        handlelength=1.5,
        columnspacing=1.2,
    )
    fig.subplots_adjust(left=0.16, right=0.99, top=0.76, bottom=0.25)
    output = ASSET_DIR / "figure2_aggregate_summary.png"
    fig.savefig(output, bbox_inches="tight", pad_inches=0.01, facecolor="white")
    plt.close(fig)
    return output


def make_trace_figure(rows: list[dict[str, object]]) -> Path:
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.size": 6.7,
            "axes.linewidth": 0.7,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(3.36, 2.82), dpi=600, sharex=True)
    methods = ["Raw", "Wiener", "MOSR"]
    colors = {"Raw": "0.82", "Wiener": "0.50", "MOSR": "0.08"}
    hatches = {"Raw": "..", "Wiener": "//", "MOSR": None}
    metric_specs = [
        ("step_sd_nm", "Step SD (nm)"),
        ("nominal_mae_nm", "Nominal MAE (nm)"),
        ("within_grid_median_nm", "Grid median (nm)"),
    ]
    x = np.arange(len(SEQUENCES), dtype=float)
    bar_width = 0.24
    for axis, (field, label) in zip(axes, metric_specs):
        for method_index, method in enumerate(methods):
            values = [
                float(next(row for row in rows if row["sequence"] == sequence and row["method"] == method)[field])
                for sequence in SEQUENCES
            ]
            axis.bar(
                x + (method_index - 1) * bar_width,
                values,
                width=bar_width,
                color=colors[method],
                edgecolor="black",
                linewidth=0.45,
                hatch=hatches[method],
                label=method,
            )
        axis.set_ylabel(label, fontsize=6.2)
        axis.grid(axis="y", color="0.88", linewidth=0.4)
        axis.set_axisbelow(True)
        axis.tick_params(axis="y", labelsize=5.8)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(["50x\n0.5", "50x\n1.0", "20x\n0.5", "20x\n1.0"], fontsize=6.0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=6.1)
    fig.subplots_adjust(left=0.21, right=0.99, top=0.91, bottom=0.12, hspace=0.20)
    output = ASSET_DIR / "figure2_cross_magnification_metrics.png"
    fig.savefig(output, bbox_inches="tight", pad_inches=0.01, facecolor="white")
    plt.close(fig)
    return output


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    rows, aggregate_rows, bootstrap_rows, audit = assemble_results()
    audit["per_pair_recomputation"] = validate_per_pair(rows)

    with (ASSET_DIR / "selected_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (ASSET_DIR / "aggregate_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(aggregate_rows[0].keys()))
        writer.writeheader()
        writer.writerows(aggregate_rows)
    with (ASSET_DIR / "bootstrap_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(bootstrap_rows[0].keys()))
        writer.writeheader()
        writer.writerows(bootstrap_rows)
    with (QA_DIR / "selected_results_audit.json").open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2, ensure_ascii=False)

    outputs = [
        make_pipeline_figure(),
        make_two_page_method_figure(),
        make_aggregate_summary_figure(aggregate_rows),
        make_trace_figure(rows),
    ]
    print(json.dumps({"figures": [str(path) for path in outputs], "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
