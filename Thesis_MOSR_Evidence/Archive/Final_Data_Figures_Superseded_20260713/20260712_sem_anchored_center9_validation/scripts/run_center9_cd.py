from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, Rectangle
from PIL import Image, ImageOps

from center9_core import center9_identity_map, infer_quadrant_transform


SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE = SCRIPT_DIR.parent
ROOT = PACKAGE.parents[1]
CD_ROOT = PACKAGE / "cd"
TABLE_DIR = CD_ROOT / "tables"
FIGURE_DIR = CD_ROOT / "figures"

SOURCE_WIDE = (
    ROOT
    / "Final_Data_Figures"
    / "20260710_v42_full_validation"
    / "tables"
    / "cd"
    / "100mg_center36_individual_cd_wide.csv"
)
SEM_WORKBOOK = ROOT / "20260618_100MG" / "SEM_data" / "via_pilar.xlsx"
RAW_IMAGE = ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
V42_IMAGE = (
    ROOT
    / "Final_Data_Figures"
    / "20260710_v42_full_validation"
    / "reconstructions"
    / "reconstruct_progress_epoch_120_in_20260618_100MG_20260709_202713"
    / "100mg_static"
    / "Image__2026-06-18__17-10-31.bmp"
)

PHYSICAL_QUADRANTS = (
    ("vertical_lines", "pillar"),
    ("via", "horizontal_lines"),
)
CAPTURE_20260618_QUADRANTS = (
    ("pillar", "vertical_lines"),
    ("horizontal_lines", "via"),
)

COLORS = {
    "raw": "#D1495B",
    "v42": "#2878B5",
    "truth": "#24292F",
    "positive": "#198754",
}


def build_center9_table(
    source_wide_csv: str | Path,
    sem_workbook: str | Path,
    *,
    raw_image: str | Path,
    v42_image: str | Path,
    source_manifest: str | Path | None = None,
) -> pd.DataFrame:
    source_path = Path(source_wide_csv)
    raw_path = Path(raw_image)
    v42_path = Path(v42_image)
    for path in [source_path, Path(sem_workbook), raw_path, v42_path]:
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest_path = (
        Path(source_manifest)
        if source_manifest is not None
        else source_path.parents[2] / "cd_validation_manifest.json"
    )
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def same_path(left: Path, right: str | Path) -> bool:
        return str(left.resolve()).casefold() == str(Path(right).resolve()).casefold()

    if not same_path(raw_path, manifest["cases"]["raw"]["image"]):
        raise ValueError("Raw image does not match validation manifest")
    if not same_path(v42_path, manifest["cases"]["v42_e120"]["image"]):
        raise ValueError("V42 image does not match validation manifest")

    capture_transform = infer_quadrant_transform(
        PHYSICAL_QUADRANTS, CAPTURE_20260618_QUADRANTS
    )
    identities = center9_identity_map(
        sem_workbook, capture_transform=capture_transform
    )
    source = pd.read_csv(source_path)
    source = source[source["feature_key"] == "pillar"].copy()
    for column in ["grid_row", "grid_col"]:
        numeric = pd.to_numeric(source[column], errors="raise")
        if not np.equal(numeric.to_numpy(), np.round(numeric.to_numpy())).all():
            raise ValueError("grid coordinates must be whole numbers")
        source[column] = numeric.astype(int)
    keyed = source.set_index(["grid_row", "grid_col"], verify_integrity=True)

    rows: list[dict[str, object]] = []
    for identity in identities:
        key = (identity.optical_grid_row, identity.optical_grid_col)
        if key not in keyed.index:
            raise ValueError(f"missing optical pillar grid cell: {key}")
        measured = keyed.loc[key]
        if int(measured["clean_for_summary"]) != 1:
            raise ValueError(f"center-nine source row is not clean: {key}")
        if str(measured["raw_status"]) != "ok" or str(measured["v42_e120_status"]) != "ok":
            raise ValueError(f"invalid measurement status at {key}")
        required_positive = [
            "x_px",
            "y_px",
            "radius_px",
            "raw_diameter_um",
            "v42_e120_diameter_um",
        ]
        values = np.asarray(
            [float(measured[column]) for column in required_positive], dtype=np.float64
        )
        if not np.isfinite(values).all() or not (values > 0).all():
            raise ValueError(f"measurements must be finite positive values at {key}")
        raw_diameter = float(measured["raw_diameter_um"])
        v42_diameter = float(measured["v42_e120_diameter_um"])
        truth = float(identity.sem_diameter_um)
        raw_signed_nm = (raw_diameter - truth) * 1000.0
        v42_signed_nm = (v42_diameter - truth) * 1000.0
        rows.append(
            {
                "sem_index": int(identity.sem_index),
                "sem_excel_cell": identity.sem_excel_cell,
                "sem_layout_row": int(identity.sem_layout_row),
                "sem_layout_col": int(identity.sem_layout_col),
                "optical_grid_row": int(identity.optical_grid_row),
                "optical_grid_col": int(identity.optical_grid_col),
                "capture_transform": identity.capture_transform,
                "sem_mapping_status": "corrected_horizontal_mirror",
                "superseded_source_sem_index": int(measured["sem_index"]),
                "superseded_source_sem_excel_cell": str(measured["sem_excel_cell"]),
                "sem_radius_nm": float(identity.sem_radius_nm),
                "sem_diameter_um": truth,
                "detected_feature_id": int(measured["detected_feature_id"]),
                "x_px": float(measured["x_px"]),
                "y_px": float(measured["y_px"]),
                "raw_x_px": float(measured["x_px"]),
                "raw_y_px": float(measured["y_px"]),
                "v42_x_px": float(measured["x_px"]),
                "v42_y_px": float(measured["y_px"]),
                "reference_radius_px": float(measured["radius_px"]),
                "raw_diameter_um": raw_diameter,
                "raw_signed_error_nm": raw_signed_nm,
                "raw_abs_error_nm": abs(raw_signed_nm),
                "v42_e120_diameter_um": v42_diameter,
                "v42_e120_signed_error_nm": v42_signed_nm,
                "v42_e120_abs_error_nm": abs(v42_signed_nm),
                "v42_abs_improvement_nm": abs(raw_signed_nm) - abs(v42_signed_nm),
                "v42_improved_vs_raw": bool(abs(v42_signed_nm) < abs(raw_signed_nm)),
                "measurement_source_csv": str(source_path),
                "measurement_source_manifest": str(manifest_path),
                "raw_source_image": str(raw_path),
                "v42_source_image": str(v42_path),
                "sem_source_workbook": str(Path(sem_workbook)),
            }
        )
    result = pd.DataFrame(rows).sort_values(
        ["optical_grid_row", "optical_grid_col"]
    )
    result.insert(0, "center9_position", np.arange(1, len(result) + 1))
    return result.reset_index(drop=True)


def summarize_cd(table: pd.DataFrame) -> pd.DataFrame:
    raw_mae = float(table["raw_abs_error_nm"].mean())
    records: list[dict[str, object]] = []
    for case, label, diameter_col, signed_col, abs_col in [
        (
            "raw",
            "Raw",
            "raw_diameter_um",
            "raw_signed_error_nm",
            "raw_abs_error_nm",
        ),
        (
            "v42_e120",
            "V42 epoch 120",
            "v42_e120_diameter_um",
            "v42_e120_signed_error_nm",
            "v42_e120_abs_error_nm",
        ),
    ]:
        signed = table[signed_col].to_numpy(dtype=np.float64)
        absolute = table[abs_col].to_numpy(dtype=np.float64)
        mae = float(np.mean(absolute))
        records.append(
            {
                "case": case,
                "case_label": label,
                "total_count": int(len(table)),
                "mean_diameter_um": float(table[diameter_col].mean()),
                "mean_abs_error_nm": mae,
                "median_abs_error_nm": float(np.median(absolute)),
                "rmse_nm": float(np.sqrt(np.mean(np.square(signed)))),
                "mean_signed_bias_nm": float(np.mean(signed)),
                "max_abs_error_nm": float(np.max(absolute)),
                "improved_vs_raw_count": (
                    int(table["v42_improved_vs_raw"].sum()) if case == "v42_e120" else 0
                ),
                "mean_abs_improvement_nm": raw_mae - mae,
                "mean_abs_improvement_pct": (
                    (raw_mae - mae) / raw_mae * 100.0 if raw_mae else np.nan
                ),
            }
        )
    return pd.DataFrame(records)


def symmetric_improvement_limit(values: list[float] | np.ndarray | pd.Series) -> float:
    array = np.asarray(values, dtype=np.float64)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 1.0
    return max(float(np.max(np.abs(finite))), 1.0)


def _read_display_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.autocontrast(image.convert("L")).convert("RGB")


def plot_identity_overlay(table: pd.DataFrame, output: Path) -> None:
    image = _read_display_image(Path(table["raw_source_image"].iloc[0]))
    min_x = float(table["x_px"].min())
    max_x = float(table["x_px"].max())
    min_y = float(table["y_px"].min())
    max_y = float(table["y_px"].max())
    pad = 105.0

    fig, ax = plt.subplots(figsize=(8.2, 7.0), dpi=180)
    ax.imshow(image, cmap="gray", vmin=0, vmax=255)
    for row in table.itertuples(index=False):
        radius = max(25.0, float(row.reference_radius_px) * 1.55)
        ax.add_patch(
            Circle(
                (float(row.x_px), float(row.y_px)),
                radius,
                fill=False,
                linewidth=2.0,
                edgecolor=COLORS["v42"],
            )
        )
        ax.text(
            float(row.x_px),
            float(row.y_px) - radius - 8,
            f"P{int(row.sem_index)} / {row.sem_excel_cell}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color="white",
            bbox={"facecolor": "#20252B", "edgecolor": "none", "pad": 2.0},
        )
    ax.add_patch(
        Rectangle(
            (min_x - 45, min_y - 45),
            max_x - min_x + 90,
            max_y - min_y + 90,
            fill=False,
            linewidth=1.4,
            linestyle="--",
            edgecolor="#FFC107",
        )
    )
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.set_ylim(max_y + pad, min_y - pad)
    ax.set_title("SEM-anchored center-nine pillars", fontsize=14, fontweight="semibold")
    ax.set_xlabel("Optical x position (pixel)")
    ax.set_ylabel("Optical y position (pixel)")
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def plot_per_pillar_cd(table: pd.DataFrame, output: Path) -> None:
    x = np.arange(len(table))
    labels = [f"P{int(value)}" for value in table["sem_index"]]
    fig, ax = plt.subplots(figsize=(10.5, 5.6), dpi=180)
    ax.plot(
        x,
        table["sem_diameter_um"],
        color=COLORS["truth"],
        linestyle="--",
        linewidth=1.6,
        marker="_",
        markersize=12,
        label="SEM truth",
    )
    ax.plot(
        x,
        table["raw_diameter_um"],
        color=COLORS["raw"],
        marker="s",
        markerfacecolor="white",
        linewidth=1.4,
        label="Raw",
    )
    ax.plot(
        x,
        table["v42_e120_diameter_um"],
        color=COLORS["v42"],
        marker="o",
        markerfacecolor="white",
        linewidth=1.4,
        label="V42 epoch 120",
    )
    ax.set_xticks(x, labels)
    ax.set_ylabel("Pillar diameter (um)")
    ax.set_xlabel("SEM pillar identity")
    ax.set_title("Center-nine pillar CD: Raw and V42 vs SEM", fontweight="semibold")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def _grid_matrix(table: pd.DataFrame, column: str) -> np.ndarray:
    return (
        table.pivot(
            index="optical_grid_row", columns="optical_grid_col", values=column
        )
        .sort_index()
        .sort_index(axis=1)
        .to_numpy(dtype=np.float64)
    )


def plot_error_heatmaps(table: pd.DataFrame, output: Path) -> None:
    panels = [
        ("Raw absolute error", _grid_matrix(table, "raw_abs_error_nm"), "magma_r"),
        (
            "V42 absolute error",
            _grid_matrix(table, "v42_e120_abs_error_nm"),
            "magma_r",
        ),
        ("V42 improvement", _grid_matrix(table, "v42_abs_improvement_nm"), "RdYlGn"),
    ]
    error_max = max(float(np.max(panels[0][1])), float(np.max(panels[1][1])))
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.1), dpi=180)
    for index, (title, matrix, cmap) in enumerate(panels):
        if index < 2:
            vmin, vmax = 0.0, error_max
        else:
            vmax = symmetric_improvement_limit(matrix)
            vmin = -vmax
        image = axes[index].imshow(matrix, cmap=cmap, vmin=vmin, vmax=vmax)
        for row in range(3):
            for col in range(3):
                axes[index].text(
                    col,
                    row,
                    f"{matrix[row, col]:.1f}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color=(
                        "black"
                        if abs(matrix[row, col]) < max(abs(vmin), abs(vmax)) * 0.55
                        else "white"
                    ),
                )
        axes[index].set_title(title, fontsize=11, fontweight="semibold")
        axes[index].set_xticks(range(3), ["c4", "c5", "c6"])
        axes[index].set_yticks(range(3), ["r4", "r5", "r6"])
        fig.colorbar(image, ax=axes[index], fraction=0.046, pad=0.04, label="nm")
    fig.suptitle("SEM-anchored center-nine CD error", fontweight="semibold")
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    table = build_center9_table(
        SOURCE_WIDE,
        SEM_WORKBOOK,
        raw_image=RAW_IMAGE,
        v42_image=V42_IMAGE,
    )
    summary = summarize_cd(table)
    table.to_csv(
        TABLE_DIR / "center9_cd_per_pillar.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    summary.to_csv(
        TABLE_DIR / "center9_cd_summary.csv",
        index=False,
        encoding="utf-8-sig",
        float_format="%.9f",
    )
    plot_identity_overlay(table, FIGURE_DIR / "center9_raw_identity_overlay.png")
    plot_per_pillar_cd(table, FIGURE_DIR / "center9_cd_per_pillar.png")
    plot_error_heatmaps(table, FIGURE_DIR / "center9_cd_error_heatmaps.png")
    metadata = {
        "selection": "SEM layout J8:L10, the 3x3 pillar block nearest the physical sample center",
        "capture_orientation_proof": {
            "physical_quadrants": PHYSICAL_QUADRANTS,
            "observed_20260618_quadrants": CAPTURE_20260618_QUADRANTS,
            "unique_transform": "flip_x",
        },
        "sem_workbook": str(SEM_WORKBOOK),
        "measurement_source": str(SOURCE_WIDE),
        "measurement_source_manifest": str(
            SOURCE_WIDE.parents[2] / "cd_validation_manifest.json"
        ),
        "raw_image": str(RAW_IMAGE),
        "v42_image": str(V42_IMAGE),
        "pixel_scale_nm_per_px": 69.0,
        "counts": {"pillars": int(len(table)), "cases": 2},
    }
    (CD_ROOT / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return table, summary


if __name__ == "__main__":
    run()
