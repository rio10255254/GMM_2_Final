"""Quantify the R107 supervision imbalance and frequency direction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "r107_data_contract_audit"
REPORT = ROOT / "reports" / "03_R107_DATA_CONTRACT_AUDIT.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
R107 = Path(r"D:\GMM_2_Final\Experiments\R107A_SingleImageEdgeGeometryProbe")
sys.path.insert(0, str(R107 / "training"))
from r107_dataset import R107Dataset  # noqa: E402


def highpass(x: np.ndarray, sigma: float) -> np.ndarray:
    return x - cv2.GaussianBlur(x, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    aa = a.ravel().astype(np.float64); bb = b.ravel().astype(np.float64)
    aa -= aa.mean(); bb -= bb.mean()
    denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
    return float(np.dot(aa, bb) / denom) if denom > 1e-12 else 0.0


def main() -> int:
    dataset = R107Dataset("validation", epoch=0)
    rows = []
    for index in range(len(dataset)):
        sample = dataset[index]
        source = sample["source"][0, 0].numpy()
        target = sample["target"][0, 0].numpy()
        edge = sample["edge_target"][0, 0].numpy()
        reliability = sample["reliability_target"][0, 0].numpy()
        hp_source = highpass(source, 1.0); hp_target = highpass(target, 1.0)
        hp_source2 = highpass(source, 2.0); hp_target2 = highpass(target, 2.0)
        gx_s = cv2.Sobel(source, cv2.CV_32F, 1, 0, ksize=3); gy_s = cv2.Sobel(source, cv2.CV_32F, 0, 1, ksize=3)
        gx_t = cv2.Sobel(target, cv2.CV_32F, 1, 0, ksize=3); gy_t = cv2.Sobel(target, cv2.CV_32F, 0, 1, ksize=3)
        gm_s = np.hypot(gx_s, gy_s); gm_t = np.hypot(gx_t, gy_t)
        edge_weight = edge / max(float(edge.sum()), 1e-8)
        source_energy = float(np.sqrt(np.mean(hp_source * hp_source)))
        target_energy = float(np.sqrt(np.mean(hp_target * hp_target)))
        source_energy2 = float(np.sqrt(np.mean(hp_source2 * hp_source2)))
        target_energy2 = float(np.sqrt(np.mean(hp_target2 * hp_target2)))
        rows.append({
            "scene_index": int(sample["scene_index"]),
            "role": sample["role"],
            "family": sample["family"],
            "reliability_mean": float(reliability.mean()),
            "reliability_positive_fraction_001": float((reliability > 0.01).mean()),
            "reliability_positive_fraction_010": float((reliability > 0.10).mean()),
            "edge_target_mean": float(edge.mean()),
            "edge_positive_fraction_001": float((edge > 0.01).mean()),
            "reliability_mass_over_edge_mass": float(reliability.sum() / max(edge.sum(), 1e-8)),
            "width_scale_target": float(sample["width_scale_target"][0]),
            "source_target_mae_gray": float(np.mean(np.abs(source - target)) * 255.0),
            "hp1_source_rms_gray": source_energy * 255.0,
            "hp1_target_rms_gray": target_energy * 255.0,
            "hp1_target_over_source": target_energy / max(source_energy, 1e-8),
            "hp1_phase_correlation": correlation(hp_source, hp_target),
            "hp2_target_over_source": target_energy2 / max(source_energy2, 1e-8),
            "edge_gradient_source": float((gm_s * edge_weight).sum()),
            "edge_gradient_target": float((gm_t * edge_weight).sum()),
            "edge_gradient_target_over_source": float((gm_t * edge_weight).sum() / max((gm_s * edge_weight).sum(), 1e-8)),
        })
        if (index + 1) % 64 == 0:
            print(json.dumps({"stage": "audit", "done": index + 1, "total": len(dataset)}), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(RESULT / "per_scene.csv", index=False, encoding="utf-8-sig")

    summary = {
        "status": "complete",
        "scenes": int(len(frame)),
        "roles": {},
        "overall": {
            "median_reliability_mean": float(frame["reliability_mean"].median()),
            "median_reliability_positive_fraction_001": float(frame["reliability_positive_fraction_001"].median()),
            "median_reliability_positive_fraction_010": float(frame["reliability_positive_fraction_010"].median()),
            "median_edge_positive_fraction_001": float(frame["edge_positive_fraction_001"].median()),
            "median_reliability_mass_over_edge_mass": float(frame["reliability_mass_over_edge_mass"].median()),
            "median_hp1_target_over_source": float(frame["hp1_target_over_source"].median()),
            "median_hp1_phase_correlation": float(frame["hp1_phase_correlation"].median()),
            "median_edge_gradient_target_over_source": float(frame["edge_gradient_target_over_source"].median()),
            "sharpen_required_fraction": float(((frame["hp1_target_over_source"] > 1.05) & (frame["hp1_phase_correlation"] > 0.30)).mean()),
            "denoise_dominant_fraction": float((frame["hp1_target_over_source"] < 0.95).mean()),
        },
        "training_pixel_balance": {
            "each_scene_has_degraded_and_identity_view": True,
            "identity_view_fraction": 0.5,
            "interpretation": "The reliability loss is averaged over all pixels and both degraded/identity views; positive edge-transition support is a tiny minority unless explicitly rebalanced.",
        },
    }
    for role, group in frame.groupby("role"):
        summary["roles"][str(role)] = {
            "scenes": int(len(group)),
            "median_reliability_mean": float(group["reliability_mean"].median()),
            "median_positive_fraction_001": float(group["reliability_positive_fraction_001"].median()),
            "median_hp1_target_over_source": float(group["hp1_target_over_source"].median()),
            "median_phase_correlation": float(group["hp1_phase_correlation"].median()),
            "median_edge_gradient_target_over_source": float(group["edge_gradient_target_over_source"].median()),
        }
    (RESULT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    o = summary["overall"]
    REPORT.write_text("\n".join([
        "# R107 Data-Contract Audit",
        "",
        f"- Validation scenes: {summary['scenes']}.",
        f"- Median reliability target mean: {o['median_reliability_mean']:.8f}.",
        f"- Median fraction above 0.01: {100*o['median_reliability_positive_fraction_001']:.4f}%.",
        f"- Identity views are exactly 50% of training views.",
        f"- Sharpen-required fraction with phase support: {100*o['sharpen_required_fraction']:.1f}%.",
        f"- Denoise-dominant fraction: {100*o['denoise_dominant_fraction']:.1f}%.",
        "",
        "The audit distinguishes a genuine lack of recoverable high-frequency supervision from gate-label mass imbalance.  Both must be repaired before another formal run.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

