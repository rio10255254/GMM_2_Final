"""Synthesize the full R113 deep audit and validate its evidence chain."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PARENT = ROOT.parent


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    data = load(RESULTS / "data_profile" / "analysis_summary.json")
    recoverability = load(RESULTS / "degradation_recoverability" / "analysis_summary.json")
    training = load(RESULTS / "training_contract" / "analysis_summary.json")
    model = load(RESULTS / "model_internals" / "analysis_summary.json")
    gradients = load(RESULTS / "loss_gradients" / "analysis_summary.json")
    clear_conflict = load(RESULTS / "loss_gradients" / "clear_degraded_conflict_summary.json")
    domain = load(RESULTS / "domain_gap" / "analysis_summary.json")
    detectability = load(RESULTS / "boundary_detectability" / "analysis_summary.json")
    r113 = load(PARENT / "results" / "FINAL_DECISION.json")

    checkpoint_final = model["checkpoint_dynamics"][-1]
    challenge = {row["challenge"]: row for row in recoverability["challenge_summary"]}
    real_gap = domain["distance_analysis"]["real_domains"]
    total_conflict = {row["parameter_group"]: row for row in clear_conflict["total_gradient_conflict"]}
    family_boundary = pd.read_csv(RESULTS / "training_contract" / "family_effective_boundary_weight.csv")
    dense = family_boundary.set_index("family").loc["dense_array"]
    gradient_budget = pd.read_csv(RESULTS / "loss_gradients" / "pooled_loss_gradient_summary.csv")
    width_top = gradient_budget.loc[gradient_budget.parameter_group.eq("width_head")].sort_values("effective_gradient_norm", ascending=False).iloc[0]
    renderer_top = gradient_budget.loc[gradient_budget.parameter_group.eq("renderer_backbone")].sort_values("effective_gradient_norm", ascending=False).iloc[0]

    root_causes = [
        {
            "rank": 1,
            "category": "control_and_loss",
            "confidence": "very high",
            "finding": "The learned boundary/correction-support branch is dead and the necessity path was never trained.",
            "evidence": {
                "boundary_auc": checkpoint_final["boundary_auc"],
                "boundary_average_precision": checkpoint_final["boundary_average_precision"],
                "positive_fraction": checkpoint_final["target_boundary_fraction"],
                "boundary_spatial_std": checkpoint_final["boundary_spatial_std"],
                "boundary_input_gradient_total": model["effective_receptive_field"]["fields"]["boundary"]["gradient_total"],
                "necessity_hardcoded": r113["key_findings"]["r109_internal_failure"]["hardcoded_necessity"],
                "detector_frozen_renderer_epochs": training["detector_stage"]["frozen_for_renderer_epochs"],
                "simple_cue_classifier_test_auc": detectability["overall"]["test_auc"],
            },
            "implication": "Replace the detector objective and train correction confidence jointly with the renderer; increasing backbone capacity cannot repair a zero-gradient gate.",
        },
        {
            "rank": 2,
            "category": "data_weighting",
            "confidence": "very high",
            "finding": "Record counts look balanced, but dense arrays dominate the boundary objective.",
            "evidence": {
                "dense_array_record_share": float(dense.record_share),
                "dense_array_edge_weight_share": float(dense.edge_weight_share),
                "dense_array_perimeter_share": float(dense.perimeter_share),
                "dense_array_boundary_probe_auc_median": next(row["auc_median"] for row in detectability["family_results"] if row["family"] == "dense_array"),
            },
            "implication": "Normalize boundary losses per scene/object and cap dense-array edge mass; do not balance only by record count.",
        },
        {
            "rank": 3,
            "category": "loss_conflict",
            "confidence": "very high",
            "finding": "The scalar width target and paired-clear samples dominate or oppose the geometry objectives.",
            "evidence": {
                "renderer_top_gradient_loss": str(renderer_top.loss),
                "renderer_top_gradient_norm_fraction": float(renderer_top.gradient_norm_over_total),
                "width_head_top_gradient_loss": str(width_top.loss),
                "width_head_top_gradient_norm_fraction": float(width_top.gradient_norm_over_total),
                "clear_shift_total_over_degraded": total_conflict["shift_head"]["clear_over_degraded_norm"],
                "clear_shift_vs_degraded_cosine": total_conflict["shift_head"]["clear_vs_degraded_cosine"],
                "effective_clear_identity_fraction": training["training_samples"]["effective_clear_identity_fraction"],
                "width_gain_drop_from_peak_pct": training["renderer_stage"]["width_gain_drop_from_peak_pct"],
            },
            "implication": "Stop broadcasting one Gaussian-derived width target and stop pairing a clear copy with every record. Use staged, spatial geometry supervision and balanced clear batches.",
        },
        {
            "rank": 4,
            "category": "information_limit",
            "confidence": "high",
            "finding": "A substantial part of mixed-hard supervision asks a single image to recover information that is no longer observable.",
            "evidence": {
                "mixed_hard_threshold_iou_median": challenge["mixed_hard"]["source_threshold_iou_median"],
                "mixed_hard_boundary_visibility_median": challenge["mixed_hard"]["boundary_visibility_median"],
                "mixed_hard_target_aligned_highfrequency_gain": challenge["mixed_hard"]["target_aligned_highfrequency_gain_median"],
                "mixed_hard_near_source_ambiguity_fraction": recoverability["source_ambiguity"]["mixed_hard"]["ambiguity_fraction_within_nearest_5pct"],
                "shape_observations_threshold_iou_below_0p5": recoverability["hard_visibility"]["threshold_iou_below_0p5"],
            },
            "implication": "Predict recoverability/uncertainty and avoid exact high-frequency supervision where the forward degradation erased the evidence.",
        },
        {
            "rank": 5,
            "category": "domain_gap",
            "confidence": "medium-high",
            "finding": "Synthetic degraded images contain mostly white-like high-frequency noise and simplified targets, unlike real multiscale microscopy texture.",
            "evidence": {
                "real_5x_distance_ratio": real_gap["real_5x"]["distance_over_synthetic_self_median"],
                "real_20x_distance_ratio": real_gap["real_20x"]["distance_over_synthetic_self_median"],
                "real_50x_distance_ratio": real_gap["real_50x"]["distance_over_synthetic_self_median"],
                "junhua_distance_ratio": real_gap["junhua_ring"]["distance_over_synthetic_self_median"],
                "sem_distance_ratio": real_gap["sem_optical"]["distance_over_synthetic_self_median"],
                "synthetic_standard_spectral_slope": next(row["spectral_slope"] for row in domain["domain_medians"] if row["domain"] == "synthetic_standard"),
                "real_50x_spectral_slope": next(row["spectral_slope"] for row in domain["domain_medians"] if row["domain"] == "real_50x"),
            },
            "implication": "Generate correlated multiscale optical texture/noise and structured dense scenes without using real SEM as labels.",
        },
        {
            "rank": 6,
            "category": "renderer_capacity",
            "confidence": "high",
            "finding": "The width/shift renderer handles most geometry but cannot express the hardest thin-ring/crescent/gap cases.",
            "evidence": r113["key_findings"]["renderer_capacity"],
            "implication": "Keep geometry controls but add a bounded residual path only after fixing support, uncertainty, and staged optimization.",
        },
    ]

    next_design = {
        "data": [
            "Keep roughly the current 5k scale, but sample by shape and boundary complexity rather than record count alone.",
            "Move dense arrays into an explicit quota/stratum so their boundary pixels cannot dominate every mixed batch.",
            "Do not append a clear copy to every record. Use dedicated clear/identity batches at a substantially lower, scheduled share.",
            "Add synthetic correlated multiscale microscopy texture, row/column structure, colored noise, and 5x-like dense patterns; retain supersampled labels.",
            "Attach a recoverability map from known degradation and do not demand exact fine detail in locally irrecoverable regions.",
        ],
        "model": [
            "Replace the boundary classifier with joint SDF/normal/boundary-confidence/recoverability heads.",
            "Remove the saturating detector tower behavior and the unconditional max(source edge, learned floor) support rule.",
            "Use a multiplicative correction gate that can both activate and veto correction; raw gradient is an input cue, never a mandatory floor.",
            "Keep width and normal shift, add boundary-tangent coherence conditioned on confidence, and retain a bounded zero-local-mean detail candidate.",
            "Preserve local operators and tile-safe inference; larger patch size alone is not a solution because 90% ERF radius is about 42 px and 99% about 56 px.",
        ],
        "training": [
            "Stage 1: train geometry/confidence heads with per-scene normalized SDF, normal, boundary and visibility losses; verify the head is spatially alive before proceeding.",
            "Stage 2: train width/shift with spatial targets derived from known degradation and SDF; keep the detector trainable at lower learning rate.",
            "Stage 3: freeze or slow geometry and train bounded detail only on recoverable target-aligned residuals with a dedicated optimizer/learning rate.",
            "Stage 4: short joint refinement using gradient conflict control or alternating objectives instead of one static weighted sum.",
            "Normalize translation/exposure constraints by gradient scale if they matter; the current sparse terms contribute almost nothing. Keep tile parity as validation because its training loss is already exactly zero.",
        ],
        "first_microprobe": "Before a full run, retrain only the new geometry/confidence head on the frozen 5,512-scene package with edge-mass normalization and reduced clear pairing. If it cannot beat the simple fixed-cue boundary probe across dense and non-dense families, do not start the full model.",
    }

    decision = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "answer": "The main bottleneck is not model size. R109 is conservative because its boundary/necessity controller is dead, the training distribution is edge-mass imbalanced, width and shift receive conflicting gradients, more than half of samples are clear/identity-like, and a subset of hard labels is not recoverable from one image.",
        "root_causes": root_causes,
        "next_design": next_design,
        "what_not_to_do": [
            "Do not simply increase patch size, batch size, epochs, or backbone channels.",
            "Do not preserve the current balanced-BCE plus Dice boundary objective; it admits the observed constant 0.5 solution.",
            "Do not keep the globally broadcast Gaussian width target.",
            "Do not force exact texture reconstruction in ambiguous mixed-hard regions.",
            "Do not use GMF or visual sharpness to tune these internal mechanisms.",
        ],
        "model_status": "No new candidate is promoted. This audit authorizes a small boundary/confidence microprobe, not a full training run.",
    }
    (RESULTS / "FINAL_DEEP_AUDIT.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# R113 模型與訓練影像超深度剖析

## 最終答案

R109 的主要瓶頸不是模型太小，也不是 patch 不夠大。真正原因是：邊界／修正需求控制器已經死亡、資料以邊界像素計算時嚴重失衡、width/shift 同時收到互相衝突的訊號、超過一半訓練樣本在要求保持原圖，而部分 mixed-hard 標籤從單張輸入本來就不可辨識。

## 最重要發現

1. 正式 boundary AUC 僅 {checkpoint_final['boundary_auc']:.3f}，輸出固定在 {checkpoint_final['boundary_mean']:.3f}；簡單固定特徵分類器卻能達到 {detectability['overall']['test_auc']:.3f}。因此是訓練失敗，不是輸入沒資訊。
2. dense array只佔 {dense.record_share*100:.1f}% 記錄，卻佔 {dense.edge_weight_share*100:.1f}% 邊界權重；它本身又是最難辨認的family。
3. 展開資料後，clear/identity實際佔 {training['training_samples']['effective_clear_identity_fraction']*100:.1f}%；clear樣本在shift head上的總梯度是退化樣本的 {total_conflict['shift_head']['clear_over_degraded_norm']:.2f} 倍，而且方向相反。
4. width target在width head與renderer backbone都是最大梯度來源；contour與gradient在width head上的方向餘弦達 -0.982，代表兩者幾乎正面衝突。
5. mixed-hard即使使用真實midpoint與polarity，來源輪廓IoU中位仍只有 {challenge['mixed_hard']['source_threshold_iou_median']:.3f}；可對齊的真實高頻只剩 {challenge['mixed_hard']['target_aligned_highfrequency_gain_median']*100:.1f}% 左右。
6. 90%有效視野半徑約 {model['effective_receptive_field']['fields']['delta']['radius_90pct_px']:.1f}px、99%約 {model['effective_receptive_field']['fields']['delta']['radius_99pct_px']:.1f}px；放大patch不會根治控制器與loss問題。

## 下一步

先做一個小型 boundary/SDF/confidence microprobe：重新正規化每張影像的邊界權重、降低clear pairing、把dense array獨立配額化，並讓controller在renderer階段持續更新。只有這個controller確實學出空間分離與跨退化穩定性，才值得啟動完整新模型。
"""
    (ROOT / "DEEP_AUDIT_FINDINGS_ZH.md").write_text(report, encoding="utf-8")

    checks = {
        "data_records_5512": len(pd.read_csv(RESULTS / "data_profile" / "per_record_profile.csv")) == 5512,
        "data_no_combined_cross_split_duplicates": data["exact_combined_duplicate_groups_cross_split"] == 0,
        "all_structural_masks_antialiased": int((pd.read_csv(RESULTS / "data_profile" / "per_record_profile.csv").query("role != 'flat_negative'").antialias_fraction == 0).sum()) == 0,
        "degradation_rows_33072": recoverability["observation_rows"] == 33072,
        "training_contract_complete": training["status"] == "complete",
        "model_internal_checkpoints_12": len(model["checkpoint_dynamics"]) == 12,
        "boundary_erf_zero_verified": model["effective_receptive_field"]["fields"]["boundary"]["gradient_total"] == 0,
        "gradient_pooled_rows": len(pd.read_csv(RESULTS / "loss_gradients" / "pooled_loss_gradient_summary.csv")) == 65,
        "gradient_pairwise_rows": len(pd.read_csv(RESULTS / "loss_gradients" / "pooled_pairwise_gradient_cosines.csv")) == 234,
        "representative_strata_rows": len(pd.read_csv(RESULTS / "loss_gradients" / "stratum_gradient_norms.csv")) == 140,
        "clear_degraded_rows": len(pd.read_csv(RESULTS / "loss_gradients" / "clear_degraded_gradient_conflict.csv")) == 21,
        "domain_gap_complete": domain["status"] == "complete",
        "boundary_probe_complete": detectability["status"] == "complete",
        "all_source_hashes_unchanged": (
            sha256(Path(PROJECT_ROOT / json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["sources"]["data_package"]) / "manifest.json")
            == json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["sources"]["data_manifest_sha256"]
            and sha256(Path(PROJECT_ROOT / json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["sources"]["r109_checkpoint"]))
            == json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["sources"]["r109_checkpoint_sha256"]
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    validation = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "failures": failures,
        "scope": "deep causal diagnosis and microprobe authorization; no full model promotion",
    }
    (RESULTS / "final_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"decision": str(RESULTS / "FINAL_DEEP_AUDIT.json"), "report": str(ROOT / "DEEP_AUDIT_FINDINGS_ZH.md"), "validation": validation}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
