"""Measure existing-model complementarity and Raw-only predictability.

This is a falsification analysis.  It reuses completed per-image contour tables
on common truth-backed populations; it does not reconstruct or modify any old
model.  A group-held-out regressor predicts every candidate's boundary error
from Raw image statistics, then chooses the lowest predicted error.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import entropy
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import LeaveOneGroupOut
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "existing_model_oracle"
REPORT = ROOT / "reports" / "01_EXISTING_MODEL_ORACLE.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

EXPERIMENTS = Path(str(PROJECT_ROOT / 'Experiments'))
R73_MANIFEST = EXPERIMENTS / "R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/manifest.json"
R74_MANIFEST = EXPERIMENTS / "R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/manifest.json"
R80_EXTERNAL = EXPERIMENTS / "R80_R79E23vsE100GeneralizationValidation/results/tables/external_acm_primary_combined.csv"
R103_EXTERNAL = {
    "R73": EXPERIMENTS / "R103_RecoverableDetailScratch/results/posttraining_validation/external_acm/R73_novel_shapes/results/tables/raw_r61_r103_metrics.csv",
    "R74": EXPERIMENTS / "R103_RecoverableDetailScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/results/tables/raw_r61_r103_metrics.csv",
}
R104_EXTERNAL = {
    "R73": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/results/tables/raw_r61_r104_metrics.csv",
    "R74": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/results/tables/raw_r61_r104_metrics.csv",
}

R80_SEM = EXPERIMENTS / "R80_R79E23vsE100GeneralizationValidation/results/tables/sem_acm_primary_combined.csv"
R90_SEM = EXPERIMENTS / "R90_ExposureCoherentScratch/results/early_stop_validation/sem_acm/E045/tables/primary_contour_metrics.csv"
R92_SEM = EXPERIMENTS / "R92_PhysicalTransitionBalancedScratch/results/capability_validation_20260812/sem_acm_fp32/E080/tables/primary_contour_metrics.csv"
R103_SEM = EXPERIMENTS / "R103_RecoverableDetailScratch/results/posttraining_validation/sem_contour/results/tables/raw_r61_r103_primary_metrics.csv"
R104_SEM = EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/sem_contour/results/tables/raw_r61_r104_primary_metrics.csv"

EXTERNAL_METHODS = ["Raw", "R61", "R79E23", "R103E48", "R104E48"]
SEM_METHODS = ["Raw", "R61", "R79E23", "R90E45", "R92E80", "R103E48", "R104E48"]
METRICS = ["mean_boundary_distance_px", "iou", "area_error_pct", "roughness_abs_error"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(path: Path, suite: str) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = pd.DataFrame(payload["records"])
    rows["suite"] = suite
    return rows


def read_gray(path: str | Path) -> np.ndarray:
    p = Path(path)
    image = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot decode {p}")
    return image.astype(np.float32) / 255.0


def q(values: np.ndarray, values_q: Iterable[float]) -> list[float]:
    return [float(value) for value in np.quantile(values, list(values_q))]


def extract_raw_features(path: str | Path) -> dict[str, float]:
    x = read_gray(path)
    features: dict[str, float] = {}
    quantiles = q(x, [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
    for name, value in zip(("p01", "p05", "p25", "p50", "p75", "p95", "p99"), quantiles):
        features[name] = value
    features.update({
        "mean": float(x.mean()),
        "std": float(x.std()),
        "robust_range": quantiles[5] - quantiles[1],
        "iqr": quantiles[4] - quantiles[2],
    })

    gx = cv2.Sobel(x, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(x, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    gm = np.hypot(gx, gy)
    for name, value in zip(("grad_p50", "grad_p90", "grad_p99"), q(gm, [0.5, 0.9, 0.99])):
        features[name] = value
    features["grad_mean"] = float(gm.mean())
    features["edge_density_001"] = float((gm > 0.01).mean())
    features["edge_density_003"] = float((gm > 0.03).mean())
    lap = cv2.Laplacian(x, cv2.CV_32F, ksize=3)
    features["lap_abs"] = float(np.abs(lap).mean())
    features["lap_std"] = float(lap.std())

    for sigma in (1.0, 2.0, 4.0, 8.0):
        blur = cv2.GaussianBlur(x, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        high = x - blur
        features[f"hp{sigma:g}_abs"] = float(np.abs(high).mean())
        features[f"hp{sigma:g}_std"] = float(high.std())

    for sigma in (16.0, 32.0):
        field = cv2.GaussianBlur(x, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
        features[f"illum{sigma:g}_std"] = float(field.std())
        features[f"illum{sigma:g}_range"] = float(np.quantile(field, 0.95) - np.quantile(field, 0.05))

    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3.0)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3.0)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3.0)
    coh = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy ** 2 + 1e-12) / (jxx + jyy + 1e-6)
    features["coherence_mean"] = float(coh.mean())
    features["coherence_p90"] = float(np.quantile(coh, 0.9))

    hist, _ = np.histogram(x, bins=64, range=(0, 1), density=False)
    hist = hist.astype(np.float64) / max(hist.sum(), 1)
    features["entropy"] = float(entropy(hist + 1e-12))

    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(x - x.mean()))) ** 2
    h, w = x.shape
    yy, xx = np.ogrid[-0.5:0.5:h*1j, -0.5:0.5:w*1j]
    radius = np.sqrt(xx * xx + yy * yy)
    total = float(spectrum.sum()) + 1e-12
    for lo, hi in ((0.00, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.71)):
        features[f"fft_{lo:.2f}_{hi:.2f}"] = float(spectrum[(radius >= lo) & (radius < hi)].sum() / total)
    return features


def external_table(manifests: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    r80 = pd.read_csv(R80_EXTERNAL)
    r80 = r80[r80["alignment"] == "translation_only"].copy()
    r80 = r80[r80["method"].isin(["Raw", "R79E23"])]
    r80["suite"] = r80["suite"].replace({"R73_expanded_shapes": "R73", "R74_hard_microscopy": "R74"})

    pieces = [r80]
    for suite in ("R73", "R74"):
        r103 = pd.read_csv(R103_EXTERNAL[suite])
        r103 = r103[(r103["alignment"] == "translation_only") & r103["method"].isin(["R61", "R61v16", "R103E48"])].copy()
        r103["method"] = r103["method"].replace({"R61v16": "R61"})
        r103["suite"] = suite
        pieces.append(r103)
        r104 = pd.read_csv(R104_EXTERNAL[suite])
        r104 = r104[(r104["alignment"] == "translation_only") & (r104["method"] == "R104E48")].copy()
        r104["suite"] = suite
        pieces.append(r104)
    long = pd.concat(pieces, ignore_index=True)
    long["key"] = long["suite"] + "/" + long["image_id"]
    long = long.drop_duplicates(["key", "method"], keep="first")

    expected = 200 * len(EXTERNAL_METHODS)
    if len(long) != expected:
        counts = long.groupby("method")["key"].nunique().to_dict()
        raise RuntimeError(f"External common population incomplete: rows={len(long)}, counts={counts}")
    if long.groupby("key")["method"].nunique().min() != len(EXTERNAL_METHODS):
        raise RuntimeError("Not every external image has every method")

    base = manifests[["suite", "image_id", "family", "src"]].copy()
    base["key"] = base["suite"] + "/" + base["image_id"]
    if base["key"].nunique() != 200:
        raise RuntimeError("Manifest keys are not unique")

    for metric in METRICS:
        wide = long.pivot(index="key", columns="method", values=metric)
        for method in EXTERNAL_METHODS:
            base[f"{metric}__{method}"] = base["key"].map(wide[method])
    boundary_cols = [f"mean_boundary_distance_px__{m}" for m in EXTERNAL_METHODS]
    values = base[boundary_cols].to_numpy(float)
    order = np.argsort(values, axis=1)
    base["oracle_method"] = np.asarray(EXTERNAL_METHODS, dtype=object)[order[:, 0]]
    base["oracle_boundary"] = values[np.arange(len(base)), order[:, 0]]
    base["second_boundary"] = values[np.arange(len(base)), order[:, 1]]
    base["oracle_margin"] = base["second_boundary"] - base["oracle_boundary"]

    feature_rows = []
    for index, row in base.iterrows():
        features = extract_raw_features(row["src"])
        features["key"] = row["key"]
        feature_rows.append(features)
        if (index + 1) % 25 == 0:
            print(json.dumps({"stage": "raw_features", "done": index + 1, "total": len(base)}), flush=True)
    feature_frame = pd.DataFrame(feature_rows)
    base = base.merge(feature_frame, on="key", validate="one_to_one")

    metadata_names = [
        "area_fraction", "background_level", "contrast_abs", "blur_sigma_px", "noise_sigma",
        "motion_length_px", "texture_amplitude", "illumination_amplitude", "fade_strength", "halo_strength", "contrast_scale",
    ]
    metadata = manifests.copy()
    metadata["key"] = metadata["suite"] + "/" + metadata["image_id"]
    for name in metadata_names:
        if name not in metadata:
            metadata[name] = 0.0
        metadata[name] = pd.to_numeric(metadata[name], errors="coerce").fillna(0.0)
    base = base.merge(metadata[["key", *metadata_names]], on="key", suffixes=("", "_meta"), validate="one_to_one")

    raw_feature_names = [name for name in feature_frame.columns if name != "key"]
    target_columns = boundary_cols
    y = base[target_columns].to_numpy(float)
    groups = base["family"].to_numpy()
    logo = LeaveOneGroupOut()
    prediction_rows = []
    importances = {"raw": np.zeros(len(raw_feature_names)), "metadata": np.zeros(len(metadata_names))}
    feature_sets = {"raw": raw_feature_names, "metadata": metadata_names}
    for feature_kind, names in feature_sets.items():
        X = base[names].to_numpy(float)
        for fold, (train, test) in enumerate(logo.split(X, y, groups), start=1):
            model = ExtraTreesRegressor(
                n_estimators=500,
                min_samples_leaf=3,
                max_features=0.85,
                random_state=108001 + fold,
                n_jobs=-1,
            )
            model.fit(X[train], y[train])
            pred = model.predict(X[test])
            importances[feature_kind] += model.feature_importances_
            train_global_index = np.argmin(np.median(y[train], axis=0))
            for local_index, row_index in enumerate(test):
                choice = int(np.argmin(pred[local_index]))
                actual = float(y[row_index, choice])
                oracle_index = int(np.argmin(y[row_index]))
                prediction_rows.append({
                    "feature_kind": feature_kind,
                    "key": base.iloc[row_index]["key"],
                    "family": base.iloc[row_index]["family"],
                    "predicted_method": EXTERNAL_METHODS[choice],
                    "actual_selected_boundary": actual,
                    "oracle_method": EXTERNAL_METHODS[oracle_index],
                    "oracle_boundary": float(y[row_index, oracle_index]),
                    "oracle_margin": float(base.iloc[row_index]["oracle_margin"]),
                    "global_train_method": EXTERNAL_METHODS[train_global_index],
                    "global_train_boundary": float(y[row_index, train_global_index]),
                    "top1_correct": bool(choice == oracle_index),
                    "regret": actual - float(y[row_index, oracle_index]),
                })
    pred_frame = pd.DataFrame(prediction_rows)
    pred_frame.to_csv(RESULT / "cross_family_predictions.csv", index=False, encoding="utf-8-sig")
    base.to_csv(RESULT / "external_common_population.csv", index=False, encoding="utf-8-sig")

    summary: dict[str, object] = {
        "images": int(len(base)),
        "families": int(base["family"].nunique()),
        "methods": EXTERNAL_METHODS,
        "global_methods": {},
        "oracle": {},
        "predictability": {},
        "winner_counts": {str(k): int(v) for k, v in base["oracle_method"].value_counts().to_dict().items()},
        "winner_counts_by_family": {
            family: {str(k): int(v) for k, v in rows["oracle_method"].value_counts().to_dict().items()}
            for family, rows in base.groupby("family")
        },
    }
    for method in EXTERNAL_METHODS:
        values_m = base[f"mean_boundary_distance_px__{method}"].to_numpy(float)
        summary["global_methods"][method] = {
            "median_boundary_px": float(np.median(values_m)),
            "mean_boundary_px": float(np.mean(values_m)),
            "p90_boundary_px": float(np.quantile(values_m, 0.9)),
        }
    global_best = min(EXTERNAL_METHODS, key=lambda m: summary["global_methods"][m]["median_boundary_px"])
    oracle_values = base["oracle_boundary"].to_numpy(float)
    global_values = base[f"mean_boundary_distance_px__{global_best}"].to_numpy(float)
    summary["oracle"] = {
        "global_best_method": global_best,
        "global_best_median_boundary_px": float(np.median(global_values)),
        "per_image_oracle_median_boundary_px": float(np.median(oracle_values)),
        "per_image_oracle_mean_boundary_px": float(np.mean(oracle_values)),
        "per_image_oracle_p90_boundary_px": float(np.quantile(oracle_values, 0.9)),
        "median_improvement_vs_global_best_px": float(np.median(global_values - oracle_values)),
        "mean_improvement_vs_global_best_px": float(np.mean(global_values - oracle_values)),
        "improved_fraction_vs_global_best": float(np.mean(oracle_values < global_values - 1e-9)),
        "median_decision_margin_px": float(np.median(base["oracle_margin"])),
    }
    for feature_kind, rows in pred_frame.groupby("feature_kind"):
        decisive = rows["oracle_margin"] >= rows["oracle_margin"].median()
        summary["predictability"][feature_kind] = {
            "median_selected_boundary_px": float(rows["actual_selected_boundary"].median()),
            "mean_selected_boundary_px": float(rows["actual_selected_boundary"].mean()),
            "p90_selected_boundary_px": float(rows["actual_selected_boundary"].quantile(0.9)),
            "median_regret_px": float(rows["regret"].median()),
            "mean_regret_px": float(rows["regret"].mean()),
            "top1_accuracy": float(rows["top1_correct"].mean()),
            "decisive_half_top1_accuracy": float(rows.loc[decisive, "top1_correct"].mean()),
            "better_than_fold_global_fraction": float((rows["actual_selected_boundary"] < rows["global_train_boundary"] - 1e-9).mean()),
            "median_gain_vs_fold_global_px": float((rows["global_train_boundary"] - rows["actual_selected_boundary"]).median()),
        }
    importance_payload = {}
    for kind, names in feature_sets.items():
        values_i = importances[kind] / len(np.unique(groups))
        order_i = np.argsort(values_i)[::-1]
        importance_payload[kind] = [{"feature": names[i], "importance": float(values_i[i])} for i in order_i[:15]]
    summary["feature_importance"] = importance_payload
    return base, summary


def sem_table() -> tuple[pd.DataFrame, dict[str, object]]:
    pieces = []
    r80 = pd.read_csv(R80_SEM)
    pieces.append(r80[r80["method"].isin(["Raw", "R79E23"])].copy())
    r103 = pd.read_csv(R103_SEM)
    r103 = r103[r103["method"].isin(["R61v16", "R103E48"])].copy()
    r103["method"] = r103["method"].replace({"R61v16": "R61"})
    pieces.append(r103)
    r104 = pd.read_csv(R104_SEM)
    pieces.append(r104[r104["method"] == "R104E48"].copy())
    r90 = pd.read_csv(R90_SEM); r90["method"] = "R90E45"; pieces.append(r90)
    r92 = pd.read_csv(R92_SEM); r92["method"] = "R92E80"; pieces.append(r92)
    long = pd.concat(pieces, ignore_index=True)
    long = long.drop_duplicates(["exposure", "pillar_id", "method"], keep="first")
    metric = "mean_boundary_distance_pitch_pct"
    pivot = long.pivot(index=["exposure", "pillar_id"], columns="method", values=metric)
    pivot = pivot[SEM_METHODS].dropna().reset_index()
    if len(pivot) != 432:
        raise RuntimeError(f"SEM common rows {len(pivot)} != 432")
    values = pivot[SEM_METHODS].to_numpy(float)
    order = np.argsort(values, axis=1)
    pivot["oracle_method"] = np.asarray(SEM_METHODS, dtype=object)[order[:, 0]]
    pivot["oracle_boundary_pitch_pct"] = values[np.arange(len(pivot)), order[:, 0]]
    pivot["second_boundary_pitch_pct"] = values[np.arange(len(pivot)), order[:, 1]]
    pivot.to_csv(RESULT / "sem_common_population.csv", index=False, encoding="utf-8-sig")

    method_summary = {
        method: {
            "median_boundary_pitch_pct": float(pivot[method].median()),
            "mean_boundary_pitch_pct": float(pivot[method].mean()),
            "p90_boundary_pitch_pct": float(pivot[method].quantile(0.9)),
        }
        for method in SEM_METHODS
    }
    global_best = min(SEM_METHODS, key=lambda m: method_summary[m]["median_boundary_pitch_pct"])
    oracle = pivot["oracle_boundary_pitch_pct"].to_numpy(float)
    global_values = pivot[global_best].to_numpy(float)

    pillar_choices = []
    for pillar, rows in pivot.groupby("pillar_id"):
        medians = rows[SEM_METHODS].median()
        choice = str(medians.idxmin())
        pillar_choices.append({
            "pillar_id": int(pillar),
            "selected_method": choice,
            "selected_median_boundary_pitch_pct": float(medians[choice]),
            "global_best_median_boundary_pitch_pct": float(medians[global_best]),
        })
    pillar_frame = pd.DataFrame(pillar_choices)
    pillar_frame.to_csv(RESULT / "sem_per_pillar_oracle.csv", index=False, encoding="utf-8-sig")
    exposure_choices = []
    for exposure, rows in pivot.groupby("exposure"):
        medians = rows[SEM_METHODS].median()
        choice = str(medians.idxmin())
        exposure_choices.append({
            "exposure": int(exposure),
            "selected_method": choice,
            "selected_median_boundary_pitch_pct": float(medians[choice]),
            "global_best_median_boundary_pitch_pct": float(medians[global_best]),
        })
    pd.DataFrame(exposure_choices).to_csv(RESULT / "sem_per_exposure_oracle.csv", index=False, encoding="utf-8-sig")

    summary = {
        "observations": int(len(pivot)),
        "physical_pillars": int(pivot["pillar_id"].nunique()),
        "exposures": int(pivot["exposure"].nunique()),
        "methods": SEM_METHODS,
        "global_methods": method_summary,
        "global_best_method": global_best,
        "per_observation_oracle_median_boundary_pitch_pct": float(np.median(oracle)),
        "per_observation_oracle_p90_boundary_pitch_pct": float(np.quantile(oracle, 0.9)),
        "median_improvement_vs_global_best_pitch_pct": float(np.median(global_values - oracle)),
        "improved_fraction_vs_global_best": float(np.mean(oracle < global_values - 1e-12)),
        "winner_counts": {str(k): int(v) for k, v in pivot["oracle_method"].value_counts().to_dict().items()},
        "per_pillar_selected_method_counts": {str(k): int(v) for k, v in pillar_frame["selected_method"].value_counts().to_dict().items()},
        "per_pillar_oracle_median": float(pillar_frame["selected_median_boundary_pitch_pct"].median()),
        "per_pillar_global_best_median": float(pillar_frame["global_best_median_boundary_pitch_pct"].median()),
        "per_exposure_choices": exposure_choices,
    }
    return pivot, summary


def make_figures(external: pd.DataFrame, external_summary: dict, sem: pd.DataFrame) -> None:
    methods = EXTERNAL_METHODS
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    counts = external["oracle_method"].value_counts().reindex(methods, fill_value=0)
    axes[0].bar(counts.index, counts.values, color="#3973ac")
    axes[0].set_title("External truth: per-image boundary winner")
    axes[0].set_ylabel("images")
    axes[0].tick_params(axis="x", rotation=30)
    sem_counts = sem["oracle_method"].value_counts().reindex(SEM_METHODS, fill_value=0)
    axes[1].bar(sem_counts.index, sem_counts.values, color="#c7662e")
    axes[1].set_title("SEM: per-observation boundary winner")
    axes[1].set_ylabel("pillar-exposure observations")
    axes[1].tick_params(axis="x", rotation=35)
    fig.savefig(RESULT / "winner_counts.png", dpi=180)
    plt.close(fig)

    pred = pd.read_csv(RESULT / "cross_family_predictions.csv")
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    labels, data = ["oracle", "fold global", "Raw features", "metadata"] , [
        external["oracle_boundary"].to_numpy(),
        pred[pred["feature_kind"] == "raw"]["global_train_boundary"].to_numpy(),
        pred[pred["feature_kind"] == "raw"]["actual_selected_boundary"].to_numpy(),
        pred[pred["feature_kind"] == "metadata"]["actual_selected_boundary"].to_numpy(),
    ]
    ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_ylabel("mean boundary distance (px)")
    ax.set_title("Leave-one-family-out selection")
    fig.savefig(RESULT / "predictability_boxplot.png", dpi=180)
    plt.close(fig)


def write_report(summary: dict[str, object]) -> None:
    ext = summary["external"]
    sem = summary["sem"]
    raw_pred = ext["predictability"]["raw"]
    meta_pred = ext["predictability"]["metadata"]
    lines = [
        "# R108A Existing-Model Oracle and Predictability",
        "",
        "## External truth-backed shapes",
        "",
        f"- Common images: {ext['images']} across {ext['families']} held-out families.",
        f"- Global best method: {ext['oracle']['global_best_method']} with median boundary distance {ext['oracle']['global_best_median_boundary_px']:.4f} px.",
        f"- Per-image oracle median: {ext['oracle']['per_image_oracle_median_boundary_px']:.4f} px.",
        f"- Oracle improves over the global best on {100*ext['oracle']['improved_fraction_vs_global_best']:.1f}% of images; median gain {ext['oracle']['median_improvement_vs_global_best_px']:.4f} px.",
        "",
        "## Can Raw alone predict the useful model?",
        "",
        f"- Leave-one-family-out Raw-feature selector top-1 accuracy: {100*raw_pred['top1_accuracy']:.1f}%.",
        f"- On the decisive half of cases: {100*raw_pred['decisive_half_top1_accuracy']:.1f}%.",
        f"- Median selected boundary distance: {raw_pred['median_selected_boundary_px']:.4f} px; median regret to oracle: {raw_pred['median_regret_px']:.4f} px.",
        f"- Generator-metadata selector top-1 accuracy: {100*meta_pred['top1_accuracy']:.1f}% (diagnostic upper context, not deployable input).",
        "",
        "## SEM repeated observations",
        "",
        f"- Common observations: {sem['observations']} from {sem['physical_pillars']} physical pillars and {sem['exposures']} exposures.",
        f"- Global best method: {sem['global_best_method']}.",
        f"- Global-best median boundary distance: {sem['global_methods'][sem['global_best_method']]['median_boundary_pitch_pct']:.4f}% pitch.",
        f"- Per-observation oracle median: {sem['per_observation_oracle_median_boundary_pitch_pct']:.4f}% pitch.",
        f"- Per-pillar fixed-choice median: {sem['per_pillar_oracle_median']:.4f}% pitch versus {sem['per_pillar_global_best_median']:.4f}% for the global best.",
        "",
        "## Interpretation rule",
        "",
        "Large oracle gain plus successful Raw-only prediction supports conditional local action selection. Large oracle gain without Raw-only predictability indicates a single-image information limit. Small oracle gain indicates that recombining existing behavior is not enough and a new optical action is required.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    required = [R73_MANIFEST, R74_MANIFEST, R80_EXTERNAL, R80_SEM, R90_SEM, R92_SEM, R103_SEM, R104_SEM, *R103_EXTERNAL.values(), *R104_EXTERNAL.values()]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(missing)
    manifests = pd.concat([load_manifest(R73_MANIFEST, "R73"), load_manifest(R74_MANIFEST, "R74")], ignore_index=True)
    external, external_summary = external_table(manifests)
    sem, sem_summary = sem_table()
    summary = {
        "status": "complete",
        "experiment": "R108A_existing_model_oracle",
        "selection_input_contract": "Raw image statistics only; no model output or truth feature is used by the deployable-feature predictor.",
        "external": external_summary,
        "sem": sem_summary,
        "source_hashes": {str(path): sha256(path) for path in required},
        "limitations": [
            "R73 and R74 are development truth suites, not sealed future-device holdouts.",
            "The selector is image-level and diagnostic; the proposed final model would make local decisions.",
            "SEM oracle choices use truth and are an upper bound, not a deployable selection result.",
        ],
    }
    (RESULT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    make_figures(external, external_summary, sem)
    write_report(summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

