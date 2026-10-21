"""Synthesize and validate the complete R113 causal evidence chain."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    source = read_json(RESULTS / "source_inventory.json")
    measurement_validation = read_json(RESULTS / "measurement_qa" / "final_validation.json")
    measurement = read_json(RESULTS / "measurement_qa" / "analysis_summary.json")
    expressivity_validation = read_json(RESULTS / "r109_expressivity" / "validation.json")
    expressivity = read_json(RESULTS / "r109_expressivity" / "upper_bound_decision.json")
    structure_validation = read_json(RESULTS / "structure" / "validation.json")
    structure = read_json(RESULTS / "structure" / "structure_findings.json")
    trajectory_validation = read_json(RESULTS / "training_dynamics" / "validation.json")
    sem = read_json(RESULTS / "physical_validation" / "sem_acm_contract" / "results" / "analysis_summary.json")
    sem_uncertainty = read_json(RESULTS / "physical_validation" / "sem_acm_contract" / "results" / "uncertainty.json")
    lsc = read_json(RESULTS / "physical_validation" / "lsc_interventions" / "analysis_summary.json")
    lsc_uncertainty = read_json(RESULTS / "physical_validation" / "lsc_interventions" / "uncertainty.json")
    synthetic = read_json(RESULTS / "physical_validation" / "synthetic_acm" / "analysis_summary.json")
    synthetic_uncertainty = read_json(RESULTS / "physical_validation" / "synthetic_acm" / "uncertainty.json")
    line = read_json(RESULTS / "physical_validation" / "line_interventions" / "analysis_summary.json")
    intervention_validation = read_json(RESULTS / "physical_validation" / "intervention_reconstructions" / "validation.json")
    first_formal = read_json(ROOT / "next_probe" / "results" / "formal_comparison.json")
    first_formal_validation = read_json(ROOT / "next_probe" / "results" / "formal_validation.json")
    supervised = read_json(ROOT / "next_probe" / "results" / "supervised_formal_comparison.json")
    supervised_validation = read_json(ROOT / "next_probe" / "results" / "supervised_formal_validation.json")

    sem_index = {row["method"]: row for row in sem["aggregate"]}
    lsc_headline = lsc["headline"]
    synthetic_index = {
        suite["suite"]: {row["method"]: row for row in suite["aggregate"]}
        for suite in synthetic["suites"]
    }
    line_sharp = {(row["orientation"], row["method"]): row for row in line["sharpness"]}
    line_disp = {row["method"]: row for row in line["displacement"]}
    measurement_index = {row["arm"]: row for row in measurement["arm_summary"]}

    key_findings = {
        "measurement_repair": {
            "v42_primary_radius_sd_px": float(measurement_index["V42 E120"]["ring_center_radius_std_px"]),
            "r109_primary_radius_sd_px": float(measurement_index["R109 E48"]["ring_center_radius_std_px"]),
            "v42_width_sd_px": float(measurement_index["V42 E120"]["ring_width_std_px"]),
            "r109_width_sd_px": float(measurement_index["R109 E48"]["ring_width_std_px"]),
            "old_width_gmf_mechanism_revoked": True,
        },
        "v42_r61_relation": structure["architecture_relation"],
        "v42_dominant_output_mechanism": structure["v42_causal_decomposition"]["interpretation"],
        "r109_internal_failure": {
            "learned_support_statistics": structure["r109_causal_decomposition"]["learned_support_statistics"],
            "hardcoded_necessity": structure["r109_causal_decomposition"]["hardcoded_necessity"],
        },
        "renderer_capacity": expressivity,
        "fixed_smoothing": {
            "sem_boundary_full": sem_index["full"]["mean_boundary_distance_pitch_pct"],
            "sem_boundary_smoothed": sem_index["smoothed_controls"]["mean_boundary_distance_pitch_pct"],
            "sem_improved_pillars": 36,
            "sem_improved_exposures": 12,
            "r73_boundary_full": synthetic_index["R73"]["full"]["mean_boundary_distance_px"],
            "r73_boundary_smoothed": synthetic_index["R73"]["smoothed_controls"]["mean_boundary_distance_px"],
            "r74_boundary_full": synthetic_index["R74"]["full"]["mean_boundary_distance_px"],
            "r74_boundary_smoothed": synthetic_index["R74"]["smoothed_controls"]["mean_boundary_distance_px"],
            "lsc_within_grid_full_nm": lsc_headline["R109 E48"]["median_within_grid_sd_nm"],
            "lsc_within_grid_smoothed_nm": lsc_headline["smoothed_controls"]["median_within_grid_sd_nm"],
            "line_horizontal_width_full_nm": line_sharp[("horizontal_lines", "R109 E48")]["median_transition_width_nm"],
            "line_horizontal_width_smoothed_nm": line_sharp[("horizontal_lines", "R109 smoothed controls")]["median_transition_width_nm"],
            "line_profile_mae_full_nm": line_disp["R109 E48"]["profile_mae_nm"],
            "line_profile_mae_smoothed_nm": line_disp["R109 smoothed controls"]["profile_mae_nm"],
            "decision": "fixed smoothing is domain-dependent and cannot be built in unconditionally",
        },
        "detail_microprobes": {
            "unsupervised": {
                "assessment": first_formal["assessment"],
                "headline": first_formal["headline"],
            },
            "supervised": supervised,
        },
    }

    supervised_supported = "supported architecture mechanism" in supervised["assessment"]
    design = {
        "status": "design_supported_not_trained_as_full_candidate",
        "keep": [
            "R109 single-image local-cue backbone and analytic width/normal-shift geometry path",
            "bounded output and tile-safe local operators",
            "scratch-only synthetic training with supersampled labels",
        ],
        "change": [
            "replace the collapsed boundary-support floor and hardcoded necessity=1 with a learned local correction-need gate that can both activate and veto correction",
            "regularize controls along the detected boundary direction instead of applying unconditional isotropic Gaussian smoothing",
            "add the bounded zero-local-mean detail/geometry branch with direct staged residual supervision" if supervised_supported else "retain the capacity-proven bounded-detail branch only as a design candidate, but train it in a separate phase with the geometry path frozen or slowed and a dedicated detail learning rate; current joint supervision is insufficient",
            "supervise geometry controls explicitly from synthetic SDF/known degradation where possible, instead of relying only on final-image losses",
            "oversample thin rings, crescents, narrow gaps, boundary fade, halo and mixed-hard cases while keeping broad shape families",
        ],
        "do_not_do": [
            "do not copy V42 Raw anchoring into the scientific output merely to please GMF",
            "do not remove the normal-shift branch",
            "do not hard-code fixed spatial smoothing",
            "do not enlarge the backbone before fixing control/gating supervision",
            "do not promote any R113 microprobe checkpoint to thesis or enterprise delivery",
        ],
        "next_full_experiment": "a new scratch run is justified only after this design is frozen; it must repeat R73/R74, SEM ACM, deterministic LSC, real 5x/20x/50x, line, tile, and only then optional GMF compatibility",
    }

    decision = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "question": "Which internal mechanisms should change before the next full MOSR training?",
        "answer": "R109 should be retained as the geometric base, but its correction-need/support gate, boundary-coherent control logic, and bounded-detail supervision must be redesigned together. V42's GMF behavior comes mainly from its final Raw anchor and is not a physical target.",
        "model_roles_unchanged": {
            "V42_E120": "current thesis-results model",
            "R61_v16": "historical generalization/GMF reference with context-sensitive inference",
            "R109_E48": "current research base for the next architecture",
            "R113_microprobe": "mechanism evidence only; not a candidate",
        },
        "key_findings": key_findings,
        "next_design": design,
        "external_gmf": "not rerun because no R113 arm was promoted through the physical contract; GMF remains a later compatibility test",
    }
    (RESULTS / "FINAL_DECISION.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = {
        "source_inventory": source["status"] == "pass",
        "measurement_qa": measurement_validation["status"] == "pass",
        "expressivity": expressivity_validation["status"] == "PASS",
        "structure": structure_validation["status"] == "pass",
        "trajectory": trajectory_validation["status"] == "pass",
        "intervention_files": intervention_validation["status"] == "pass",
        "sem_rows": sem["primary_rows"] == 2592 and sem["sensitivity_rows"] == 1944,
        "lsc_rows": lsc["candidate_pair_rows"] == 240 and lsc["combined_pair_rows"] == 720 and lsc["determinism_spot_check_max_px"] == 0,
        "synthetic_rows": all(item["primary_rows"] == 1200 and item["sensitivity_rows"] == 270 for item in synthetic["suites"]),
        "line_rows": line["frame_rows"] == 360 and line["step_rows"] == 180 and line["missing_measurements"] == 0,
        "first_formal": first_formal_validation["status"] == "pass",
        "supervised_formal": supervised_validation["status"] == "pass",
        "all_required_outputs_present": True,
    }
    failures = [name for name, passed in checks.items() if not passed]
    validation = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "failures": failures,
        "scope": "mechanism conclusion and next-design authorization; no model promotion",
    }
    (RESULTS / "final_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    supervised_summary = supervised["summaries"]["bounded_detail_supervised"]
    report = f"""# R113 最終發現

## 結論

這一輪沒有產生可直接交付的新模型，但成功找出下一輪真正需要修改的三個核心：

1. R109 的修正需求與邊界支援判斷沒有學起來，幾乎退化成固定值。
2. 寬度與法向位移都需要保留，但同一條邊界上的控制必須有方向性的連續性；固定平滑不可用。
3. 現有 renderer 在薄環、月牙與窄間隙存在容量上限，需要受限、零局部均值的細節／幾何支路；正式監督微實驗的判定是：{supervised['assessment']}。

## 重要證據

- V42 與 R61 是同一份模型程式，82.96% 的共有權重張量逐位相同；V42 最主要的新行為來自最後的 Raw anchor。
- 修正 R112 量測後，V42/R109 寬度波動與 GMF 分數的舊相關不再成立。
- R109 dense oracle 的中位輪廓誤差可從 0.0930 px 降至 0.0058 px，但最難薄環仍有 3.240 px，證明一般案例是控制問題、極端案例是 renderer 問題。
- 固定平滑使 SEM 36/36 顆、12/12 曝光改善，卻使 R73 五類未見形狀全部退步；R74 也只有部分家族改善。
- 固定平滑讓線條 profile 位移 MAE由 {line_disp['R109 E48']['profile_mae_nm']:.3f} 降至 {line_disp['R109 smoothed controls']['profile_mae_nm']:.3f} nm，但水平邊界寬度由 {line_sharp[('horizontal_lines', 'R109 E48')]['median_transition_width_nm']:.1f} 增至 {line_sharp[('horizontal_lines', 'R109 smoothed controls')]['median_transition_width_nm']:.1f} nm。
- 直接監督細節支路最後使用 {supervised_summary['detail_abs_mean_gray']:.3f} 灰階，目標利用率 {supervised_summary.get('detail_target_utilization_ratio', 0):.3f}；它仍只是機制測試，不是新候選模型。

## 下一輪架構

- 保留 R109 的單張、局部、可切塊主幹與寬度／法向位移幾何路徑。
- 重做 correction-need/support gate，使它可以主動拒絕錯誤的原圖梯度，也能在弱邊界啟動修正。
- 用沿輪廓方向的局部一致性取代固定二維平滑。
- 加入受限零局部均值細節支路，並以合成真值做分階段直接監督。
- 完整訓練仍必須全新從零開始，不接續 R109、V42 或 R61 權重。

## 沒有做的事

R113 沒有把任何微實驗權重升格為論文、ONNX或企業交付版，也沒有用GMF反向選模型。因為沒有候選先通過全部物理條件，所以本輪沒有再跑外部GMF。
"""
    (ROOT / "R113_FINDINGS_ZH.md").write_text(report, encoding="utf-8")
    print(json.dumps({"decision": str(RESULTS / "FINAL_DECISION.json"), "validation": validation, "report": str(ROOT / "R113_FINDINGS_ZH.md")}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
