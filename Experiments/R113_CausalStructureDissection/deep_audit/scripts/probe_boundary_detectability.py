"""Test whether fixed local cues contain boundary information independent of R109 training."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(PROJECT_ROOT / CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "boundary_detectability"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R109 / "model"))
sys.path.insert(0, str(R109 / "training"))
from r109_model import build_model
from r109_dataset import R109Dataset


FEATURE_NAMES = [
    "raw", "blur_0p8", "blur_1p6", "blur_3p2", "blur_6p4",
    "highpass_0p8", "highpass_1p6", "highpass_3p2", "highpass_6p4",
    "grad_x", "grad_y", "grad_magnitude", "local_mean", "local_scale", "normalized",
]


def sample_pixels(features: np.ndarray, edge: np.ndarray, rng: np.random.Generator, count: int = 64) -> tuple[np.ndarray, np.ndarray]:
    positive = np.flatnonzero(edge.ravel() > .5)
    negative = np.flatnonzero(edge.ravel() < .05)
    if not len(positive) or not len(negative):
        return np.empty((0, features.shape[0]), np.float32), np.empty(0, np.uint8)
    positive = rng.choice(positive, size=count, replace=len(positive) < count)
    negative = rng.choice(negative, size=count, replace=len(negative) < count)
    indices = np.concatenate([positive, negative])
    values = features.reshape(features.shape[0], -1)[:, indices].T.astype(np.float32)
    labels = np.concatenate([np.ones(count, np.uint8), np.zeros(count, np.uint8)])
    return values, labels


def main() -> int:
    torch.set_num_threads(min(8, torch.get_num_threads()))
    datasets = {epoch: R109Dataset("validation", epoch=epoch) for epoch in range(6)}
    model = build_model().eval()
    split_scene = int(np.quantile([int(row["scene_index"]) for row in datasets[0].records], .7))
    features_by_split = defaultdict(list)
    labels_by_split = defaultdict(list)
    meta_rows = []
    rng = np.random.default_rng(113411)
    with torch.no_grad():
        for epoch, dataset in datasets.items():
            for start in range(0, len(dataset), 8):
                items = [dataset[index] for index in range(start, min(start + 8, len(dataset)))]
                source = torch.cat([item["source"][0:1] for item in items], 0)
                cues = model.cues(source)["features"].cpu().numpy()
                for local, item in enumerate(items):
                    scene_index = int(item["scene_index"])
                    role = str(item["role"])
                    if role == "flat_negative":
                        continue
                    edge = item["edge"][0, 0].numpy()
                    values, labels = sample_pixels(cues[local], edge, rng)
                    if not len(labels):
                        continue
                    split = "train" if scene_index <= split_scene else "test"
                    features_by_split[split].append(values)
                    labels_by_split[split].append(labels)
                    meta_rows.extend({
                        "split": split,
                        "scene_index": scene_index,
                        "challenge": str(item["challenge"]),
                        "family": str(item["family"]),
                        "rows": len(labels),
                    } for _ in [0])
            print(json.dumps({"epoch": epoch}), flush=True)
    x_train = np.concatenate(features_by_split["train"])
    y_train = np.concatenate(labels_by_split["train"])
    x_test = np.concatenate(features_by_split["test"])
    y_test = np.concatenate(labels_by_split["test"])
    scaler = StandardScaler().fit(x_train)
    classifier = LogisticRegression(max_iter=300, class_weight="balanced", n_jobs=1, C=.5, solver="lbfgs").fit(scaler.transform(x_train), y_train)
    train_score = classifier.predict_proba(scaler.transform(x_train))[:, 1]
    test_score = classifier.predict_proba(scaler.transform(x_test))[:, 1]
    overall = {
        "train_auc": float(roc_auc_score(y_train, train_score)),
        "test_auc": float(roc_auc_score(y_test, test_score)),
        "train_average_precision": float(average_precision_score(y_train, train_score)),
        "test_average_precision": float(average_precision_score(y_test, test_score)),
        "train_pixels": len(y_train),
        "test_pixels": len(y_test),
    }

    test_meta = [row for row in meta_rows if row["split"] == "test"]
    rows = []
    offset = 0
    for meta in test_meta:
        count = int(meta["rows"])
        score = test_score[offset : offset + count]
        labels = y_test[offset : offset + count]
        rows.append({**meta, "auc": float(roc_auc_score(labels, score)), "average_precision": float(average_precision_score(labels, score))})
        offset += count
    per_image = pd.DataFrame(rows)
    per_image.to_csv(OUTPUT / "per_image_results.csv", index=False, encoding="utf-8-sig")
    by_challenge = per_image.groupby("challenge", as_index=False).agg(images=("scene_index", "size"), auc_median=("auc", "median"), auc_p05=("auc", lambda value: value.quantile(.05)), ap_median=("average_precision", "median"))
    by_family = per_image.groupby("family", as_index=False).agg(images=("scene_index", "size"), auc_median=("auc", "median"), auc_p05=("auc", lambda value: value.quantile(.05)), ap_median=("average_precision", "median"))
    by_challenge.to_csv(OUTPUT / "challenge_results.csv", index=False, encoding="utf-8-sig")
    by_family.to_csv(OUTPUT / "family_results.csv", index=False, encoding="utf-8-sig")
    coefficients = pd.DataFrame({"feature": FEATURE_NAMES, "standardized_coefficient": classifier.coef_[0]}).sort_values("standardized_coefficient", key=abs, ascending=False)
    coefficients.to_csv(OUTPUT / "feature_coefficients.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "model": "scene-disjoint logistic regression on frozen analytic LocalCues",
        "overall": overall,
        "challenge_results": by_challenge.to_dict(orient="records"),
        "family_results": by_family.to_dict(orient="records"),
        "top_features": coefficients.head(8).to_dict(orient="records"),
        "current_r109_boundary_auc_reference": 0.4962337939465492,
        "interpretation_boundary": "This probe proves detectability in fixed cues, not that a one-layer classifier is the preferred deployed boundary model.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
