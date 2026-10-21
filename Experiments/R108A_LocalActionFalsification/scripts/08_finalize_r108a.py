"""Cross-check and finalize the R108A falsification evidence package."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "R108A_RESULTS_ZH.md"
FINAL = ROOT / "results" / "final_decision.json"
SUMMARIES = {
    "existing_model_oracle": ROOT / "results/existing_model_oracle/summary.json",
    "operator_oracle_v1": ROOT / "results/operator_oracle/summary.json",
    "operator_oracle_v2": ROOT / "results/operator_oracle_radiometry_v2/summary.json",
    "r107_data_audit": ROOT / "results/r107_data_contract_audit/summary.json",
    "action_selector": ROOT / "results/action_selector_probe/summary.json",
    "system_identification": ROOT / "results/system_identification/summary.json",
    "profile_observability": ROOT / "results/local_profile_observability/summary.json",
    "staged_selector": ROOT / "results/staged_profile_selector/summary.json",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_all() -> dict[str, dict]:
    payload = {}
    for name, path in SUMMARIES.items():
        if not path.exists():
            raise FileNotFoundError(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("status") != "complete":
            raise RuntimeError(f"{name} is not complete")
        payload[name] = value
    return payload


def validate_counts() -> dict[str, int]:
    counts = {
        "existing_external_rows": len(pd.read_csv(ROOT / "results/existing_model_oracle/external_common_population.csv")),
        "existing_sem_rows": len(pd.read_csv(ROOT / "results/existing_model_oracle/sem_common_population.csv")),
        "operator_v1_rows": len(pd.read_csv(ROOT / "results/operator_oracle/per_image_action_metrics.csv")),
        "operator_v2_rows": len(pd.read_csv(ROOT / "results/operator_oracle_radiometry_v2/per_image_action_metrics.csv")),
        "action_selector_rows": len(pd.read_csv(ROOT / "results/action_selector_probe/leave_family_out_predictions.csv")),
        "r107_audit_rows": len(pd.read_csv(ROOT / "results/r107_data_contract_audit/per_scene.csv")),
        "system_edge_rows": len(pd.read_csv(ROOT / "results/system_identification/edge_response.csv")),
        "system_frequency_rows": len(pd.read_csv(ROOT / "results/system_identification/frequency_response.csv")),
    }
    expected = {
        "existing_external_rows": 200,
        "existing_sem_rows": 432,
        "operator_v1_rows": 200 * 33,
        "operator_v2_rows": 200 * 56,
        "action_selector_rows": 200,
        "r107_audit_rows": 512,
        "system_edge_rows": 87 * 5,
        "system_frequency_rows": 81 * 5,
    }
    if counts != expected:
        raise RuntimeError({"actual": counts, "expected": expected})
    system = ROOT / "results/system_identification"
    output_folders = [
        ROOT / "data/system_identification_probes/input",
        system / "inference_runs/R61_full/reconstruct_progress_best_tradeoff_in_input_20260623_200020/R61_full",
        system / "inference_runs/R61_zero_optics/reconstruct_progress_best_tradeoff_in_input_20260623_200020/R61_zero_optics",
        system / "outputs/R79E23",
        system / "outputs/R79E100",
    ]
    for folder in output_folders:
        if len(list(folder.glob("*.bmp"))) != 196:
            raise RuntimeError(f"Incomplete controlled probe output: {folder}")
    return counts


def build_decision(data: dict[str, dict], counts: dict[str, int]) -> dict:
    existing = data["existing_model_oracle"]
    audit = data["r107_data_audit"]["overall"]
    selector = data["action_selector"]
    system = data["system_identification"]
    direct = data["profile_observability"]["arms"]["direct_parameter"]["severe_heldout"]
    joint_gate = data["profile_observability"]["arms"]["gated_parameter"]["severe_heldout"]
    staged = data["staged_selector"]["severe_heldout"]
    decision = {
        "status": "complete",
        "experiment": "R108A_LocalActionFalsification",
        "verdict": "CURRENT_GLOBAL_SELECTOR_REJECTED_STAGED_PARALLEL_EXPERT_DIRECTION_SUPPORTED",
        "full_r108_training_authorized": False,
        "old_weights_used_for_training": False,
        "old_models_role": "frozen diagnostic system probes only",
        "validated_counts": counts,
        "findings": {
            "existing_model_complementarity": {
                "external_global_best": existing["external"]["oracle"]["global_best_method"],
                "external_global_best_median_boundary_px": existing["external"]["oracle"]["global_best_median_boundary_px"],
                "external_oracle_median_boundary_px": existing["external"]["oracle"]["per_image_oracle_median_boundary_px"],
                "external_oracle_improved_fraction": existing["external"]["oracle"]["improved_fraction_vs_global_best"],
                "raw_feature_selector_top1": existing["external"]["predictability"]["raw"]["top1_accuracy"],
                "raw_feature_selector_tail_warning": "Median improves modestly, but mean/p90 remain worse than the R61 global choice on cross-family tests.",
                "sem_global_best": existing["sem"]["global_best_method"],
                "sem_wins": existing["sem"]["winner_counts"],
                "sem_per_pillar_choice": existing["sem"]["per_pillar_selected_method_counts"],
            },
            "current_data_contract": {
                "r107_denoise_dominant_fraction": audit["denoise_dominant_fraction"],
                "r107_phase_supported_sharpen_fraction": audit["sharpen_required_fraction"],
                "r107_reliability_positive_pixel_fraction": audit["median_reliability_positive_fraction_001"],
                "identity_view_fraction": data["r107_data_audit"]["training_pixel_balance"]["identity_view_fraction"],
            },
            "global_action_selector": {
                "top1_accuracy": selector["top1_accuracy"],
                "better_than_global_fraction": selector["utility"]["selector_better_than_fold_global_fraction"],
                "worse_than_global_fraction": selector["utility"]["selector_worse_than_fold_global_fraction"],
                "decision": "reject_as_next_full_model",
            },
            "frozen_transfer_behavior": {
                model: {
                    "edge_width_ratio": system["models"][model]["edge"]["median_width_ratio"],
                    "edge_center_p95_px": system["models"][model]["edge"]["p95_abs_center_shift_px"],
                    "off_transition_artifact_std_gray": system["models"][model]["edge"]["median_off_transition_artifact_std_gray"],
                    "subpixel_median_abs_error_px": system["models"][model]["subpixel_translation"]["median_absolute_error_px"],
                    "noise_std_ratio": system["models"][model]["flat"]["noise_std_ratio_median"],
                }
                for model in ("R61_full", "R79E23", "R79E100")
            },
            "local_profile_mechanism": {
                "direct_proposal_raw_mae_gray": direct["profile_mae_gray"]["raw"],
                "direct_proposal_mae_gray": direct["profile_mae_gray"]["model"],
                "direct_width_error_px": direct["width_abs_error_px"]["model"],
                "joint_gate_final_mean": joint_gate["gate"]["overall_mean"],
                "joint_gate_result": "collapsed_to_identity",
                "staged_selector_raw_mae_gray": staged["raw"]["profile_mae_gray"],
                "staged_selector_proposal_mae_gray": staged["proposal"]["profile_mae_gray"],
                "staged_selector_learned_mae_gray": staged["learned_selector"]["profile_mae_gray"],
                "staged_selector_oracle_mae_gray": staged["oracle_selector"]["profile_mae_gray"],
                "staged_selector_improved_fraction": staged["learned_selector"]["profile_improved_fraction"],
                "staged_selector_alpha_auc": staged["alpha"]["identity_vs_degraded_auc"],
            },
        },
        "revised_model_direction": {
            "name": "R108B_StagedParallelOpticalExperts",
            "single_image_inference": True,
            "scratch_only": True,
            "checkpoint_teacher_or_pseudolabel": False,
            "structure": [
                "Local explicit edge-profile expert predicts center, transition width and endpoint levels and renders at supersampled resolution.",
                "Parallel phase-supported texture expert targets the R79E23 6-16 pixel band behavior without spatial normalization or image-extent dependence.",
                "Independent denoise expert uses paired independent observations during training but one image at inference.",
                "Low-frequency radiometry/illumination expert cannot move edge geometry.",
                "Experts are calibrated first; adoption factors are learned afterward from direct counterfactual improvement targets while expert weights are frozen.",
                "Final composition is parallel/ordered and additive by responsibility, not one global winner and not proposal times an unsupervised gate.",
                "No global pooling, spatial normalization, free image residual or global signed-distance renderer.",
            ],
            "training_data_repairs": [
                "Generate source and target from the same continuous high-resolution scene and sensor integration.",
                "Track structural phase separately from random noise so high-frequency noise cannot make a sharp target look spectrally weaker.",
                "Balance update units by edge, texture, denoise, illumination, identity and unrecoverable roles rather than by raw pixel mass.",
                "Render all labels and added texture above native resolution before area integration.",
                "Use real microscope information only as aggregate optical statistics and validation; no real structure or SEM pixels enter training truth.",
            ],
            "numerical_repairs": [
                "Use BF16 or FP32 rather than FP16 for the learned trunk.",
                "Use FP32 for optical parameters, rendering and adoption targets.",
                "Use residual scaling and finite-value guards through long-horizon probes.",
            ],
        },
        "next_experiment": {
            "name": "R108B_full_image_microprobe",
            "scope": "64-128 continuous scenes, independent held-out degradation families, 600-1000 updates per arm",
            "arms": [
                "edge expert proposal calibration only",
                "frozen edge expert plus outcome-supervised adoption",
                "parallel edge plus texture experts",
                "parallel experts plus denoise/radiometry, translation and overlap consistency",
            ],
            "decision_style": "Inspect continuous trajectories and worst cases; immediate stops only for identity collapse, invented topology, non-finite values or extent-dependent output.",
        },
        "not_authorized": [
            "full 40-60 epoch R108 training",
            "ONNX packaging",
            "replacement of COMBO, R61, R79 or R103",
            "use of R108A profile checkpoints as image-model weights",
        ],
    }
    return decision


def write_report(decision: dict) -> None:
    f = decision["findings"]
    transfer = f["frozen_transfer_behavior"]
    local = f["local_profile_mechanism"]
    lines = [
        "# R108A 完整短實驗結果",
        "",
        "## 最終判定",
        "",
        "目前的全圖模型選擇器與共同信心開關都被否決；先校準各修復專家，再凍結候選並用實際改善比例訓練採用程度，獲得正向機制證據。尚不啟動完整 R108。",
        "",
        "## 現有模型互補性",
        "",
        f"- R73/R74 全局最佳是 {f['existing_model_complementarity']['external_global_best']}，中位邊界 {f['existing_model_complementarity']['external_global_best_median_boundary_px']:.4f} px；逐張理想選擇可到 {f['existing_model_complementarity']['external_oracle_median_boundary_px']:.4f} px。",
        f"- 理想選擇在 {100*f['existing_model_complementarity']['external_oracle_improved_fraction']:.1f}% 影像勝過全局最佳，但 Raw 特徵跨類別精確選對只有 {100*f['existing_model_complementarity']['raw_feature_selector_top1']:.1f}%。",
        f"- SEM 432 次觀察中，勝次為 {json.dumps(f['existing_model_complementarity']['sem_wins'], ensure_ascii=False)}；36 顆 pillar 的固定選擇全部是 R79E23。",
        "",
        "## 資料與開關根因",
        "",
        f"- R107 有 {100*f['current_data_contract']['r107_denoise_dominant_fraction']:.1f}% 場景在整體高頻上獎勵去噪，只有 {100*f['current_data_contract']['r107_phase_supported_sharpen_fraction']:.1f}% 同時要求增強且有相位支撐。",
        f"- 修正正樣本中位只占 {100*f['current_data_contract']['r107_reliability_positive_pixel_fraction']:.3f}% 像素，另有 50% identity 視圖。",
        f"- 即使改成平衡局部剖面資料，共同未監督開關仍降到 {local['joint_gate_final_mean']:.8f}，確認關閉輸出是結構性捷徑。",
        "",
        "## 凍結模型作用",
        "",
        f"- R61：寬度倍率 {transfer['R61_full']['edge_width_ratio']:.3f}，外圍假變化 {transfer['R61_full']['off_transition_artifact_std_gray']:.3f} 灰階。",
        f"- R79E23：寬度倍率 {transfer['R79E23']['edge_width_ratio']:.3f}，外圍假變化 {transfer['R79E23']['off_transition_artifact_std_gray']:.3f} 灰階。",
        f"- R79E100：寬度倍率 {transfer['R79E100']['edge_width_ratio']:.3f}，外圍假變化升到 {transfer['R79E100']['off_transition_artifact_std_gray']:.3f} 灰階。",
        "- R61 主要銳化局部單調邊界並壓低 4-8 px 週期；R79 保留/增強 6-16 px 紋理，但帶入影像範圍依賴。",
        "",
        "## 分階段選擇證據",
        "",
        f"- 嚴重未見退化：Raw {local['staged_selector_raw_mae_gray']:.3f} 灰階；候選單獨使用 {local['staged_selector_proposal_mae_gray']:.3f}；學得採用比例後 {local['staged_selector_learned_mae_gray']:.3f}；真值上限 {local['staged_selector_oracle_mae_gray']:.3f}。",
        f"- 學得選擇讓 {100*local['staged_selector_improved_fraction']:.1f}% 剖面變好，沒有關死。",
        "",
        "## 下一步",
        "",
        "建立 R108B 小型完整影像探針：邊界、紋理、去噪、亮度分成平行專家；先學好候選，再凍結候選訓練採用比例。只有小型探針跨未見退化、真實影像、位移與分塊都成立，才準備正式約 5,000 場景資料與完整 scratch 訓練。",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_manifest() -> None:
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name != "FILE_MANIFEST_SHA256.csv")
    rows = []
    for path in files:
        rows.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    with (ROOT / "FILE_MANIFEST_SHA256.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"]); writer.writeheader(); writer.writerows(rows)


def main() -> int:
    data = load_all(); counts = validate_counts(); decision = build_decision(data, counts)
    FINAL.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    write_report(decision)
    state = {
        "status": "complete",
        "experiment": "R108A_LocalActionFalsification",
        "formal_model_trained": False,
        "full_r108_authorized": False,
        "verdict": decision["verdict"],
        "final_decision": "results/final_decision.json",
        "human_report": "reports/R108A_RESULTS_ZH.md",
        "next_experiment": decision["next_experiment"]["name"],
    }
    (ROOT / "EXPERIMENT_STATE.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    write_manifest()
    print(json.dumps(state, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

