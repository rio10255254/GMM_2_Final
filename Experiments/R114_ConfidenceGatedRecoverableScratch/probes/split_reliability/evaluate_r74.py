"""Sealed R74 qualification for a frozen split-reliability controller."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from scipy.stats import spearmanr
import torch
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model.r114_split_profile_model import build_split_profile_model
from training.split_profile_targets import build_split_profile_targets
PROJECT_ROOT = Path(__file__).resolve().parents[4]


R74 = Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val'))


def read(path: str | Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image.astype(np.float32) / 255.0


def signed_distance(mask: np.ndarray) -> np.ndarray:
    inside = mask >= 0.5
    return (
        cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
        - cv2.distanceTransform((~inside).astype(np.uint8), cv2.DIST_L2, 5)
    ).astype(np.float32)


def rank(target: np.ndarray, prediction: np.ndarray) -> float:
    if target.std() < 1e-8 or prediction.std() < 1e-8:
        return 0.0
    return float(spearmanr(target, prediction).statistic)


def auc(target: np.ndarray, prediction: np.ndarray) -> float:
    keep = (target <= 0.15) | (target >= 0.40)
    truth = (target[keep] >= 0.40).astype(np.uint8)
    if truth.size < 8 or np.unique(truth).size < 2:
        return 0.0
    return float(roc_auc_score(truth, prediction[keep]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    checkpoint = sorted((run_dir / "weights").glob("epoch_*.pth"))[-1]
    payload = torch.load(checkpoint, map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError("checkpoint violates scratch contract")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = build_split_profile_model()
    model.load_state_dict(payload["model"], strict=True)
    model = model.to(device).eval()
    manifest = json.loads((R74 / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    width_truth_all, width_pred_all, shift_truth_all, shift_pred_all = [], [], [], []
    with torch.inference_mode():
        for row in manifest["records"]:
            source_np = read(row["src"])
            target_np = read(row["lbl"])
            mask_np = read(row["mask"])
            sdf_np = signed_distance(mask_np)
            source = torch.from_numpy(source_np)[None, None].to(device)
            target = torch.from_numpy(target_np)[None, None].to(device)
            sdf = torch.from_numpy(sdf_np)[None, None].to(device)
            flag = torch.tensor([False], device=device)
            predicted = model.controller(source)
            truth = build_split_profile_targets(source, target, sdf, flag, flag)
            support = (truth.boundary_band[0, 0] > 0.5).cpu().numpy()
            wt = truth.width_reliability[0, 0].cpu().numpy()[support]
            wp = predicted.width_reliability[0, 0].cpu().numpy()[support]
            st = truth.shift_reliability[0, 0].cpu().numpy()[support]
            sp = predicted.shift_reliability[0, 0].cpu().numpy()[support]
            if wt.size > 4000:
                take = np.linspace(0, wt.size - 1, 4000).round().astype(int)
                wt, wp, st, sp = wt[take], wp[take], st[take], sp[take]
            width_truth_all.append(wt); width_pred_all.append(wp)
            shift_truth_all.append(st); shift_pred_all.append(sp)
            rows.append({
                "image_id": row["image_id"],
                "family": row["family"],
                "width_target_mean": float(wt.mean()),
                "width_predicted_mean": float(wp.mean()),
                "width_spearman": rank(wt, wp),
                "width_auc": auc(wt, wp),
                "shift_target_mean": float(st.mean()),
                "shift_predicted_mean": float(sp.mean()),
                "shift_spearman": rank(st, sp),
                "shift_auc": auc(st, sp),
            })
    wt = np.concatenate(width_truth_all); wp = np.concatenate(width_pred_all)
    st = np.concatenate(shift_truth_all); sp = np.concatenate(shift_pred_all)
    families = {}
    for family in sorted({row["family"] for row in rows}):
        subset = [row for row in rows if row["family"] == family]
        families[family] = {
            key: float(np.median([row[key] for row in subset]))
            for key in (
                "width_target_mean", "width_predicted_mean", "width_spearman", "width_auc",
                "shift_target_mean", "shift_predicted_mean", "shift_spearman", "shift_auc",
            )
        }
    aggregate = {
        "width_point_spearman": rank(wt, wp),
        "width_point_auc": auc(wt, wp),
        "width_calibration_mae": float(np.mean(np.abs(wt - wp))),
        "shift_point_spearman": rank(st, sp),
        "shift_point_auc": auc(st, sp),
        "shift_calibration_mae": float(np.mean(np.abs(st - sp))),
        "points": int(wt.size),
    }
    low = families["low_contrast"]
    uneven = families["uneven_illumination"]
    halo = families["asymmetric_blur_halo"]
    fade = families["boundary_fade"]
    evidence = {
        "width_tracks_r74_oracle": aggregate["width_point_spearman"] > 0.30 and aggregate["width_point_auc"] > 0.70,
        "shift_tracks_r74_oracle": aggregate["shift_point_spearman"] > 0.30 and aggregate["shift_point_auc"] > 0.75,
        "low_contrast_shift_below_uneven": low["shift_predicted_mean"] < uneven["shift_predicted_mean"],
        "low_contrast_shift_below_halo": low["shift_predicted_mean"] < halo["shift_predicted_mean"],
        "fade_has_spatial_shift_ranking": fade["shift_auc"] > 0.65,
    }
    decision = "advance_to_split_profile_probe" if all(evidence.values()) else "stop_and_repair_r74_reliability"
    result = {
        "status": "complete",
        "decision": decision,
        "evidence_bundle": evidence,
        "aggregate": aggregate,
        "families": families,
        "checkpoint": str(checkpoint),
        "scratch_verified": True,
    }
    output = run_dir / "r74_reliability_qualification.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if decision == "advance_to_split_profile_probe" else 2


if __name__ == "__main__":
    raise SystemExit(main())
