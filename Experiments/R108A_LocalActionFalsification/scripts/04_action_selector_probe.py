"""Short, non-neural selector falsification using v2 oracle actions.

The probe asks whether a selector trained only on Raw-derived statistics can
choose among a compact representative action set under leave-one-family-out
evaluation.  This avoids spending a full neural run before observability is
established.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.model_selection import LeaveOneGroupOut


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "action_selector_probe"
REPORT = ROOT / "reports" / "04_ACTION_SELECTOR_PROBE.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
METRICS_PATH = ROOT / "results" / "operator_oracle_radiometry_v2" / "per_image_action_metrics.csv"

spec = importlib.util.spec_from_file_location("r108_existing_oracle", ROOT / "scripts" / "01_existing_model_oracle.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load feature extractor")
features_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = features_module
spec.loader.exec_module(features_module)

CANDIDATES = [
    "Raw",
    "denoise_s0.90",
    "wiener_s2.2_b0.03",
    "fixedradiometry_w0.45_d4_g1.50",
    "denoise55_fixedradiometry_w60_g130",
    "localcontrast_s32_g1.50",
    "globalcontrast_g1.40",
    "illum_s16_a0.25",
]
AXES = ["edge_band_mae_gray", "profile_mae", "center_abs_error_px", "width_abs_error_px", "overshoot_mean_gray"]


def spatial_features(path: str | Path) -> dict[str, float]:
    result = features_module.extract_raw_features(path)
    x = features_module.read_gray(path)
    gx = cv2.Sobel(x, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(x, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    gm = np.hypot(gx, gy)
    h, w = x.shape
    for grid in (2, 4):
        for row in range(grid):
            for col in range(grid):
                y0, y1 = row * h // grid, (row + 1) * h // grid
                x0, x1 = col * w // grid, (col + 1) * w // grid
                block = x[y0:y1, x0:x1]
                grad = gm[y0:y1, x0:x1]
                prefix = f"g{grid}_{row}_{col}"
                result[f"{prefix}_mean"] = float(block.mean())
                result[f"{prefix}_std"] = float(block.std())
                result[f"{prefix}_grad"] = float(grad.mean())
    return result


def add_truth_utility(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (suite, image_id), group in frame.groupby(["suite", "image_id"], sort=False):
        group = group.set_index("action").loc[CANDIDATES].reset_index().copy()
        normalized = []
        for axis in AXES:
            values = group[axis].to_numpy(float)
            low = float(np.min(values)); high = float(np.quantile(values, 0.90))
            normalized.append(np.clip((values - low) / max(high - low, 1e-8), 0.0, 5.0))
        group["oracle_utility"] = np.max(np.stack(normalized, axis=1), axis=1)
        rows.append(group)
    return pd.concat(rows, ignore_index=True)


def main() -> int:
    if not METRICS_PATH.exists():
        raise FileNotFoundError(METRICS_PATH)
    long = pd.read_csv(METRICS_PATH)
    missing = sorted(set(CANDIDATES) - set(long["action"]))
    if missing:
        raise RuntimeError(f"Missing candidates: {missing}")
    long = long[long["action"].isin(CANDIDATES)].copy()
    long = add_truth_utility(long)
    key = long[long["action"] == "Raw"][["suite", "image_id", "family", "source"]].copy()
    key["key"] = key["suite"] + "/" + key["image_id"]
    feature_rows = []
    for progress, (_, row) in enumerate(key.iterrows(), start=1):
        values = spatial_features(row["source"])
        values["key"] = row["key"]
        feature_rows.append(values)
        if progress % 25 == 0:
            print(json.dumps({"stage": "selector_features", "done": progress, "total": len(key)}), flush=True)
    feature_frame = pd.DataFrame(feature_rows)
    key = key.merge(feature_frame, on="key", validate="one_to_one")
    utility = long.pivot(index=["suite", "image_id"], columns="action", values="oracle_utility").reset_index()
    key = key.merge(utility, on=["suite", "image_id"], validate="one_to_one")
    metric_pivots = {}
    for axis in AXES:
        metric_pivots[axis] = long.pivot(index=["suite", "image_id"], columns="action", values=axis)

    feature_names = [name for name in feature_frame.columns if name != "key"]
    X = key[feature_names].to_numpy(float)
    y = key[CANDIDATES].to_numpy(float)
    groups = key["family"].to_numpy()
    predictions = []
    importances = np.zeros(len(feature_names))
    for fold, (train, test) in enumerate(LeaveOneGroupOut().split(X, y, groups), start=1):
        model = ExtraTreesRegressor(n_estimators=700, min_samples_leaf=3, max_features=0.85, random_state=108400 + fold, n_jobs=-1)
        model.fit(X[train], y[train])
        pred = model.predict(X[test])
        importances += model.feature_importances_
        global_index = int(np.argmin(np.median(y[train], axis=0)))
        for local, row_index in enumerate(test):
            selected_index = int(np.argmin(pred[local]))
            oracle_index = int(np.argmin(y[row_index]))
            row = {
                "key": key.iloc[row_index]["key"],
                "suite": key.iloc[row_index]["suite"],
                "family": key.iloc[row_index]["family"],
                "selected_action": CANDIDATES[selected_index],
                "oracle_action": CANDIDATES[oracle_index],
                "global_fold_action": CANDIDATES[global_index],
                "selected_utility": float(y[row_index, selected_index]),
                "oracle_utility": float(y[row_index, oracle_index]),
                "global_fold_utility": float(y[row_index, global_index]),
                "top1_correct": bool(selected_index == oracle_index),
            }
            suite = row["suite"]; image_id = key.iloc[row_index]["image_id"]
            for axis in AXES:
                pivot = metric_pivots[axis]
                row[f"selected_{axis}"] = float(pivot.loc[(suite, image_id), CANDIDATES[selected_index]])
                row[f"oracle_{axis}"] = float(pivot.loc[(suite, image_id), CANDIDATES[oracle_index]])
                row[f"global_{axis}"] = float(pivot.loc[(suite, image_id), CANDIDATES[global_index]])
                row[f"raw_{axis}"] = float(pivot.loc[(suite, image_id), "Raw"])
            predictions.append(row)
    pred_frame = pd.DataFrame(predictions)
    pred_frame.to_csv(RESULT / "leave_family_out_predictions.csv", index=False, encoding="utf-8-sig")
    importance_order = np.argsort(importances)[::-1]

    summary = {
        "status": "complete",
        "images": int(len(pred_frame)),
        "families": int(pred_frame["family"].nunique()),
        "candidates": CANDIDATES,
        "top1_accuracy": float(pred_frame["top1_correct"].mean()),
        "selected_action_counts": {str(k): int(v) for k, v in pred_frame["selected_action"].value_counts().to_dict().items()},
        "oracle_action_counts": {str(k): int(v) for k, v in pred_frame["oracle_action"].value_counts().to_dict().items()},
        "utility": {
            "selector_median": float(pred_frame["selected_utility"].median()),
            "oracle_median": float(pred_frame["oracle_utility"].median()),
            "fold_global_median": float(pred_frame["global_fold_utility"].median()),
            "selector_better_than_fold_global_fraction": float((pred_frame["selected_utility"] < pred_frame["global_fold_utility"] - 1e-12).mean()),
            "selector_worse_than_fold_global_fraction": float((pred_frame["selected_utility"] > pred_frame["global_fold_utility"] + 1e-12).mean()),
        },
        "axes": {},
        "feature_importance": [
            {"feature": feature_names[index], "importance": float(importances[index] / pred_frame["family"].nunique())}
            for index in importance_order[:20]
        ],
        "decision_boundary": "This is an image-level observability probe. It does not authorize a neural or formal R108 model by itself.",
    }
    for axis in AXES:
        summary["axes"][axis] = {
            "raw_median": float(pred_frame[f"raw_{axis}"].median()),
            "selector_median": float(pred_frame[f"selected_{axis}"].median()),
            "fold_global_median": float(pred_frame[f"global_{axis}"].median()),
            "oracle_median": float(pred_frame[f"oracle_{axis}"].median()),
            "selector_improves_raw_fraction": float((pred_frame[f"selected_{axis}"] < pred_frame[f"raw_{axis}"] - 1e-12).mean()),
        }
    (RESULT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    REPORT.write_text("\n".join([
        "# R108A Short Action-Selector Probe",
        "",
        f"- Images/families: {summary['images']} / {summary['families']}.",
        f"- Leave-one-family-out exact action accuracy: {100*summary['top1_accuracy']:.1f}%.",
        f"- Selector beats the fold-global action on {100*summary['utility']['selector_better_than_fold_global_fraction']:.1f}% of images and is worse on {100*summary['utility']['selector_worse_than_fold_global_fraction']:.1f}%.",
        f"- Raw edge-band median: {summary['axes']['edge_band_mae_gray']['raw_median']:.3f}; selector: {summary['axes']['edge_band_mae_gray']['selector_median']:.3f}; oracle: {summary['axes']['edge_band_mae_gray']['oracle_median']:.3f} gray.",
        "",
        "A useful selector should improve the global action without creating a worse tail. Failure here means the next experiment should improve local observability/action supervision before building a neural router.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
