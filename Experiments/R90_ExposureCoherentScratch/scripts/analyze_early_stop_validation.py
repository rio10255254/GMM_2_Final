"""Audit and summarize the locked R90 early-stop comparison."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "early_stop_validation.json"
RESULTS = ROOT / "results" / "early_stop_validation"
REPORTS = ROOT / "reports" / "early_stop_validation"
TABLES = RESULTS / "tables"
ACM = RESULTS / "sem_acm"
RAW_TABLE = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables\primary_contour_metrics.csv")
BASE_MASK = Path(r"D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch\results\final_validation\sem_acm_epoch100\acm_validation\results\masks\acm_primary_masks.mat")

METRICS = {
    "iou": "higher",
    "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def audit_inputs(protocol: dict[str, Any], stages: list[int]) -> dict[str, Any]:
    source_manifest = read_json(RESULTS / "fixed_source_manifest.json")
    if source_manifest["protocol_id"] != protocol["protocol_id"]:
        raise RuntimeError("Source manifest protocol mismatch")
    if source_manifest["sealed_holdout_accessed"]:
        raise RuntimeError("Sealed holdout must not be used for checkpoint selection")
    for row in source_manifest["appearance"] + source_manifest["sem"]:
        if sha256_file(Path(row["source"])) != row["sha256"]:
            raise RuntimeError(f"Source changed: {row['source']}")
    expected_identities = {(exposure, pillar) for exposure in range(13, 25) for pillar in range(1, 37)}
    acm_counts: dict[str, int] = {}
    for epoch in stages:
        label = f"E{epoch:03d}"
        path = ACM / label / "tables" / "primary_contour_metrics.csv"
        table = pd.read_csv(path)
        if len(table) != 432 or table.isna().any().any():
            raise RuntimeError(f"{label}: incomplete ACM results")
        observed = set(map(tuple, table[["exposure", "pillar_id"]].astype(int).to_numpy()))
        if observed != expected_identities:
            raise RuntimeError(f"{label}: exposure/pillar identities differ")
        acm_counts[label] = int(len(table))
    appearance = pd.read_csv(TABLES / "appearance_per_frame.csv")
    if len(appearance) != len(stages) * 30 or appearance.isna().any().any():
        raise RuntimeError("Appearance table is incomplete")
    inventory = pd.read_csv(TABLES / "reconstruction_inventory.csv")
    if len(inventory) != len(stages) * 42:
        raise RuntimeError("Reconstruction inventory is incomplete")
    for row in inventory.itertuples(index=False):
        path = Path(row.output)
        if not path.is_file() or sha256_file(path) != row.output_sha256:
            raise RuntimeError(f"Reconstruction hash mismatch: {path}")
    return {
        "status": "pass",
        "protocol_hash": sha256_file(PROTOCOL),
        "fixed_appearance_sources": len(source_manifest["appearance"]),
        "fixed_sem_sources": len(source_manifest["sem"]),
        "reconstruction_outputs": int(len(inventory)),
        "appearance_rows": int(len(appearance)),
        "acm_rows_by_stage": acm_counts,
        "sealed_holdout_accessed": False,
        "all_file_hashes_verified": True,
    }


def load_acm(stages: list[int]) -> pd.DataFrame:
    base = pd.read_csv(RAW_TABLE)
    base = base.loc[base["method"].isin(["Raw", "R61v16"])].copy()
    tables = [base]
    for epoch in stages:
        label = f"E{epoch:03d}"
        table = pd.read_csv(ACM / label / "tables" / "primary_contour_metrics.csv")
        if set(table["method"].unique()) != {label}:
            raise RuntimeError(f"{label}: method label mismatch")
        tables.append(table)
    combined = pd.concat(tables, ignore_index=True)
    combined.to_csv(TABLES / "sem_acm_all_records.csv", index=False, encoding="utf-8-sig")
    return combined


def summarize_acm(combined: pd.DataFrame, stages: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = list(METRICS)
    physical = combined.groupby(["pillar_id", "method"], observed=True)[metrics].median().unstack("method")
    methods = ["Raw", "R61v16", *[f"E{epoch:03d}" for epoch in stages]]
    rows: list[dict[str, Any]] = []
    for method in methods:
        row: dict[str, Any] = {"method": method, "independent_pillars": 36, "repeated_exposures": 12}
        for metric in metrics:
            values = physical[(metric, method)].to_numpy(float)
            row[f"median_{metric}"] = float(np.median(values))
            row[f"q1_{metric}"] = float(np.percentile(values, 25))
            row[f"q3_{metric}"] = float(np.percentile(values, 75))
        rows.append(row)
    method_summary = pd.DataFrame(rows)
    method_summary.to_csv(TABLES / "sem_acm_method_summary.csv", index=False, encoding="utf-8-sig")

    comparison_rows: list[dict[str, Any]] = []
    for epoch in stages:
        candidate = f"E{epoch:03d}"
        for comparator in ("Raw", "R61v16"):
            for metric, direction in METRICS.items():
                source = physical[(metric, comparator)].to_numpy(float)
                selected = physical[(metric, candidate)].to_numpy(float)
                improvement = selected - source if direction == "higher" else source - selected
                comparison_rows.append({
                    "epoch": epoch,
                    "comparison": f"{candidate}_vs_{comparator}",
                    "comparator": comparator,
                    "metric": metric,
                    "direction": direction,
                    "comparator_median": float(np.median(source)),
                    "candidate_median": float(np.median(selected)),
                    "median_improvement_positive_is_candidate_better": float(np.median(improvement)),
                    "improved_pillars": int(np.count_nonzero(improvement > 1e-9)),
                    "tied_pillars": int(np.count_nonzero(np.abs(improvement) <= 1e-9)),
                    "worsened_pillars": int(np.count_nonzero(improvement < -1e-9)),
                })
    comparisons = pd.DataFrame(comparison_rows)
    comparisons.to_csv(TABLES / "sem_acm_paired_comparisons.csv", index=False, encoding="utf-8-sig")

    exposure_summary = combined.groupby(["exposure", "method"], observed=True)[metrics].median().reset_index()
    exposure_summary.to_csv(TABLES / "sem_acm_by_exposure.csv", index=False, encoding="utf-8-sig")
    return method_summary, comparisons, exposure_summary


def extract_cell(image: np.ndarray, center: np.ndarray, half: int) -> np.ndarray:
    cx, cy = np.rint(center).astype(int)
    padded = np.pad(image, half, mode="symmetric")
    cx += half
    cy += half
    return padded[cy - half:cy + half, cx - half:cx + half].astype(np.float64)


def crossing(profile: np.ndarray, value: float) -> float:
    indices = np.flatnonzero(profile[25:51] >= value)
    return float(25 + indices[0]) if len(indices) else np.nan


def radial_diagnostic(protocol: dict[str, Any], stages: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = loadmat(BASE_MASK, variable_names=["opt_centers", "cell_half"])
    centers = np.asarray(base["opt_centers"], dtype=float)
    half = int(np.asarray(base["cell_half"]).squeeze())
    yy, xx = np.mgrid[:2 * half, :2 * half]
    radius = np.hypot(xx - (2 * half - 1) / 2, yy - (2 * half - 1) / 2)
    raw_root = Path(protocol["development_arms"]["sem_contour"]["optical_inputs"])
    roots = {"Raw": raw_root}
    roots.update({
        f"E{epoch:03d}": RESULTS / "reconstructions" / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction"
        for epoch in stages
    })
    records: list[dict[str, Any]] = []
    for exposure in range(13, 25):
        for method, directory in roots.items():
            image = read_gray(directory / f"{exposure}.bmp")
            for position, center in enumerate(centers, start=1):
                cell = extract_cell(image, center, half)
                low, high = np.percentile(cell, [1, 99])
                normalized = np.clip((cell - low) / max(high - low, 1e-9), 0, 1)
                profile = np.asarray([
                    normalized[(radius >= value) & (radius < value + 1)].mean()
                    for value in range(52)
                ])
                inside, outside = np.median(profile[10:25]), np.median(profile[47:51])
                amplitude = outside - inside
                q25, q50, q75 = inside + 0.25 * amplitude, inside + 0.50 * amplitude, inside + 0.75 * amplitude
                derivative = np.gradient(profile)
                records.append({
                    "exposure": exposure,
                    "method": method,
                    "grid_position": position,
                    "midpoint_radius_px": crossing(profile, q50),
                    "gradient_peak_radius_px": float(25 + np.argmax(derivative[25:51])),
                    "transition_width_px": crossing(profile, q75) - crossing(profile, q25),
                    "normalized_contrast": float(amplitude),
                    "inside_mean_gray": float(cell[radius < 25].mean()),
                    "edge_annulus_mean_gray": float(cell[(radius >= 35) & (radius < 42)].mean()),
                    "outside_mean_gray": float(cell[(radius >= 47) & (radius < 51)].mean()),
                })
    table = pd.DataFrame(records)
    summary = table.groupby(["exposure", "method"], observed=True)[[
        "midpoint_radius_px", "gradient_peak_radius_px", "transition_width_px", "normalized_contrast",
        "inside_mean_gray", "edge_annulus_mean_gray", "outside_mean_gray",
    ]].median().reset_index()
    raw = summary.loc[summary["method"] == "Raw"].set_index("exposure")
    summary["midpoint_minus_raw_px"] = summary.apply(lambda row: row["midpoint_radius_px"] - raw.loc[int(row["exposure"]), "midpoint_radius_px"], axis=1)
    summary["gradient_peak_minus_raw_px"] = summary.apply(lambda row: row["gradient_peak_radius_px"] - raw.loc[int(row["exposure"]), "gradient_peak_radius_px"], axis=1)
    table.to_csv(TABLES / "sem_radial_per_position.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLES / "sem_radial_by_exposure.csv", index=False, encoding="utf-8-sig")
    return table, summary


def stage_objectives(
    stages: list[int],
    method_summary: pd.DataFrame,
    exposure_summary: pd.DataFrame,
    radial_summary: pd.DataFrame,
) -> pd.DataFrame:
    appearance = pd.read_csv(TABLES / "appearance_per_frame.csv")
    stored = pd.read_csv(TABLES / "stored_checkpoint_metrics.csv").set_index("epoch")
    methods = method_summary.set_index("method")
    rows: list[dict[str, Any]] = []
    for epoch in stages:
        label = f"E{epoch:03d}"
        stage_appearance = appearance.loc[appearance["epoch"] == epoch]
        acm_exposure = exposure_summary.loc[exposure_summary["method"] == label].set_index("exposure")
        radial = radial_summary.loc[radial_summary["method"] == label].set_index("exposure")
        row: dict[str, Any] = {
            "epoch": epoch,
            "sem_median_iou": float(methods.loc[label, "median_iou"]),
            "sem_median_boundary_pitch_pct": float(methods.loc[label, "median_mean_boundary_distance_pitch_pct"]),
            "sem_median_area_error_pct": float(methods.loc[label, "median_area_error_pct"]),
            "sem_median_perimeter_error_pct": float(methods.loc[label, "median_perimeter_error_pct"]),
            "sem_worst_exposure_iou": float(acm_exposure["iou"].min()),
            "sem_worst_exposure": int(acm_exposure["iou"].idxmin()),
            "sem_worst_exposure_boundary_pitch_pct": float(acm_exposure["mean_boundary_distance_pitch_pct"].max()),
            "exposure18_iou": float(acm_exposure.loc[18, "iou"]),
            "exposure18_boundary_pitch_pct": float(acm_exposure.loc[18, "mean_boundary_distance_pitch_pct"]),
            "exposure18_midpoint_shift_px": float(radial.loc[18, "midpoint_minus_raw_px"]),
            "exposure18_gradient_peak_shift_px": float(radial.loc[18, "gradient_peak_minus_raw_px"]),
            "max_abs_median_midpoint_shift_px": float(radial["midpoint_minus_raw_px"].abs().max()),
            "stored_balanced_score": float(stored.loc[epoch, "balanced_score"]),
            "stored_identity_texture_ratio": float(stored.loc[epoch, "identity_texture_ratio"]),
            "stored_motion_p95_px": float(stored.loc[epoch, "motion_p95_px"]),
            "stored_signed_motion_bias_magnitude_px": float(np.hypot(stored.loc[epoch, "signed_motion_bias_x_px"], stored.loc[epoch, "signed_motion_bias_y_px"])),
            "stored_low_branch_edge_leakage_gray": float(stored.loc[epoch, "low_branch_edge_leakage_gray"]),
        }
        for magnification in (5, 20, 50):
            group = stage_appearance.loc[stage_appearance["magnification"] == magnification]
            row[f"detail_{magnification}x"] = float(group["fine_detail_energy_ratio"].median())
            row[f"edge_gain_{magnification}x"] = float(group["edge_gain_on_raw_support"].median())
            row[f"dark_edge_{magnification}x"] = float(group["dark_change_fraction_on_raw_edge_band"].median())
            row[f"off_source_edge_{magnification}x"] = float(group["off_source_strong_edge_fraction"].median())
            row[f"mean_abs_change_{magnification}x_gray"] = float(group["mean_abs_change_gray"].median())
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "stage_objectives.csv", index=False, encoding="utf-8-sig")
    return table


def pareto_flags(table: pd.DataFrame) -> pd.DataFrame:
    objectives = {
        "sem_median_iou": "higher",
        "sem_worst_exposure_iou": "higher",
        "sem_median_boundary_pitch_pct": "lower",
        "max_abs_median_midpoint_shift_px": "lower",
        "detail_5x": "higher",
        "detail_20x": "higher",
        "detail_50x": "higher",
        "dark_edge_5x": "lower",
        "stored_identity_texture_ratio": "lower",
        "stored_motion_p95_px": "lower",
    }
    values = table[list(objectives)].to_numpy(float)
    transformed = values.copy()
    for index, direction in enumerate(objectives.values()):
        if direction == "higher":
            transformed[:, index] *= -1.0
    dominated = []
    for index in range(len(table)):
        by_other = np.all(transformed <= transformed[index] + 1e-12, axis=1) & np.any(transformed < transformed[index] - 1e-12, axis=1)
        by_other[index] = False
        dominated.append(bool(np.any(by_other)))
    result = table.copy()
    result["pareto_non_dominated"] = ~np.asarray(dominated)
    result.to_csv(TABLES / "stage_objectives_with_pareto.csv", index=False, encoding="utf-8-sig")
    return result


def save_tradeoff_figure(table: pd.DataFrame) -> str:
    REPORTS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    plots = [
        ("detail_50x", "sem_median_iou", "50x detail vs SEM contour"),
        ("detail_20x", "dark_edge_5x", "20x detail vs 5x dark-edge warning"),
        ("stored_motion_p95_px", "sem_worst_exposure_iou", "stored motion vs worst exposure"),
    ]
    for axis, (x_name, y_name, title) in zip(axes, plots):
        axis.plot(table[x_name], table[y_name], color="#7f8c8d", linewidth=1.2)
        axis.scatter(table[x_name], table[y_name], c=table["epoch"], cmap="viridis", s=70)
        for row in table.itertuples(index=False):
            axis.annotate(f"E{row.epoch}", (getattr(row, x_name), getattr(row, y_name)), xytext=(4, 4), textcoords="offset points", fontsize=9)
        axis.set_xlabel(x_name.replace("_", " "))
        axis.set_ylabel(y_name.replace("_", " "))
        axis.set_title(title)
        axis.grid(alpha=0.25)
    path = REPORTS / "stage_tradeoffs.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return str(path)


def panel(image: np.ndarray, label: str, width: int = 480, height: int = 300) -> np.ndarray:
    shown = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    shown = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(shown, (0, 0), (width, 36), (0, 0, 0), -1)
    cv2.putText(shown, label, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return shown


def save_exposure18_montage(protocol: dict[str, Any], stages: list[int]) -> str:
    raw = read_gray(Path(protocol["development_arms"]["sem_contour"]["optical_inputs"]) / "18.bmp")
    images = [("Raw", raw)] + [
        (f"E{epoch}", read_gray(RESULTS / "reconstructions" / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction" / "18.bmp"))
        for epoch in stages
    ]
    grid = np.vstack([
        np.hstack([panel(image, label) for label, image in images[index:index + 3]])
        for index in range(0, 9, 3)
    ])
    path = REPORTS / "sem_exposure18_stages.png"
    cv2.imwrite(str(path), grid)
    return str(path)


def main() -> int:
    protocol = read_json(PROTOCOL)
    stages = [int(value) for value in protocol["stage_candidates"]]
    audit = audit_inputs(protocol, stages)
    combined = load_acm(stages)
    method_summary, comparisons, exposure_summary = summarize_acm(combined, stages)
    _radial_table, radial_summary = radial_diagnostic(protocol, stages)
    objectives = stage_objectives(stages, method_summary, exposure_summary, radial_summary)
    objectives = pareto_flags(objectives)
    tradeoff_figure = save_tradeoff_figure(objectives)
    exposure_figure = save_exposure18_montage(protocol, stages)
    raw_method = method_summary.set_index("method").loc["Raw"]
    r61_method = method_summary.set_index("method").loc["R61v16"]
    summary = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "audit": audit,
        "reference": {
            "raw_median_iou": float(raw_method["median_iou"]),
            "raw_median_boundary_pitch_pct": float(raw_method["median_mean_boundary_distance_pitch_pct"]),
            "r61_median_iou": float(r61_method["median_iou"]),
            "r61_median_boundary_pitch_pct": float(r61_method["median_mean_boundary_distance_pitch_pct"]),
        },
        "pareto_epochs": [int(value) for value in objectives.loc[objectives["pareto_non_dominated"], "epoch"]],
        "figures": [tradeoff_figure, exposure_figure],
        "selection_status": "objective table complete; freeze one checkpoint only after reviewing the declared safety-first tie breakers",
        "claim_limit": "The fixed real images are appearance diagnostics, SEM supports contour accuracy for the paired 36 pillars, and stored motion metrics are development evidence. Confirmation on all 301 real frames is still required after one checkpoint is frozen.",
    }
    write_json(REPORTS / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
