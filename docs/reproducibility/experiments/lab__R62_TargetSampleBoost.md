# lab/R62_TargetSampleBoost 研究與重做紀錄

[Lab逐輪必要來源與代表模型核對](<../round_source_reviews/LAB_SYSTEM_20261023.md>)

[直接查看這一輪的檔案分工](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [LabSystem：校正、資料與專屬模型](../routes/lab.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

實體目標增補與保守原圖參考輸出

多版模型與固定後處理分開；相位位移恢復不等於所有局部圓心更準

## 必要來源

以R61v16及目標樣品來源作多版增補；保存各版真實裁切、數學位移、老師答案、SEM及原圖參考混合設定。anchor_detail035等後處理與各版網路分開，不能把較好相位位移等同全部局部圓心更準。

## 影像保存理由

同FOV呈現不同倍率、位移保護、正常／暗曝光與老師來源，明記網路版本及後處理；較好相位位移不能代表全部圓心與尺寸更準。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：Anchor Detail035 Decision 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/ANCHOR_DETAIL035_DECISION_20260706.md>)
- [原始報告：Anchor Fusion Decision 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/ANCHOR_FUSION_DECISION_20260706.md>)
- [原始報告：Best Current Thesis Reconstruction Decision 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/BEST_CURRENT_THESIS_RECON_DECISION_20260706.md>)
- [原始報告：R62 self-shift training decision, 2026-07-05](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_SELFSHIFT_TRAINING_DECISION_20260705.md>)
- [原始報告：R62 sequence/motion training audit, 2026-07-05](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_SEQGEOM_MOTION_AUDIT_20260705.md>)
- [原始報告：R62 Target-Boost Audit 20260705](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_TARGET_BOOST_AUDIT_20260705.md>)
- [原始報告：R62 V11 motion-clean GMF summary (2026-07-06)](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_V11_motion_clean_GMF_summary_20260706_TW.md>)
- [原始報告：R62 V12/V13 GMF 探針摘要](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_V12_V13_GMF_probe_summary_20260706_TW.md>)
- [原始報告：R62 V8 GMF / Pairwise Displacement Progress - 2026-07-06](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/R62_V8_GMF_PAIRWISE_PROGRESS_20260706.md>)
- [原始報告：V23/V24 Anchor-Teacher Decision 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/V23_V24_ANCHOR_TEACHER_DECISION_20260706.md>)
- [原始報告：V25 safe shape-anchor readout](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/V25_SAFE_SHAPE_ANCHOR_READOUT_20260706.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/fixedroi_anchor_modes_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/fixedroi_anchor_modes_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_all_complete_candidates_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_all_complete_candidates_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_all_plus_v19_stepaware_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_all_plus_v19e1_sweep_stepaware_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_candidate_scoring_v17_v18_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_own_algorithm_edge_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_own_algorithm_intensity_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_own_algorithm_single_edge_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/gmf_like_own_algorithm_single_intensity_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：Measurement Method Research Readout 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/METHOD_RESEARCH_READOUT_20260706.md>)
- [原始報告：Shape-Aware Edge Anchor Implementation Readout 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/SHAPE_EDGE_ANCHOR_IMPLEMENTATION_READOUT_20260706.md>)
- [原始報告：Shape-Edge Raw Failure Analysis 20260706](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/SHAPE_EDGE_RAW_FAILURE_ANALYSIS_20260706.md>)
- [原始報告：Shape-Edge Control Suite Readout 20260707](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/control_suite_20260707/SHAPE_EDGE_CONTROL_SUITE_READOUT_20260707.md>)
- [原始報告：Cross-Validation and Synthetic Truth Readout 20260707](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/measurement_method_research_20260706/cross_validation_and_synthetic_truth_20260707/CROSS_VALIDATION_AND_SYNTHETIC_TRUTH_READOUT_20260707.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_edge_v20_v24_v26_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_fusion_sweep_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v20_family_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v20_v24_v26_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v27_latest_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v27mix_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v28_multimagraw_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v29_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v30_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v31_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v32_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/own_gmf_fit_intensity_v33_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：R62 no-AMP candidate validation](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_noamp_candidate_displacement_eval_20260705/R62_NOAMP_CANDIDATE_VALIDATION.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v17_native_anchor_e3_mtb300_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v17_native_anchor_probe30_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v18_native_anchor_conservative_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_e1_sweep_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_e1_sweep_gmf_scoring_stepaware_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_e3_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_e3_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_smoke_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_smoke_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_edge_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_edge_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_edge_scoring_stepaware_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v19_variants_gmf_scoring_stepaware_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v20_gmfroi_e1_mtb200_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v20_gmfroi_e1_mtb200_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v22_dualroi_latest_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v22_dualroi_latest_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：R62 target-sample-boost validation readout](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v2_targetboost_displacement_eval/R62_TARGETBOOST_VALIDATION_READOUT.md>)
- [原始報告：R62 target-sample-boost validation readout](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v7_seqgeom_displacement_eval_20260706/R62_TARGETBOOST_VALIDATION_READOUT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/shape_aware_square_anchor_modes_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/shape_aware_square_anchor_modes_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/shape_aware_square_gmf_gate_formal_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/shape_aware_square_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/shape_aware_square_gmf_scoring_formal_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：Thesis displacement stability validation - R62 V7 short candidate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_displacement_stability_v7_20260706/THESIS_DISPLACEMENT_STABILITY_V7_READOUT_20260706.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_edge_gmf_pairwise_gate_v11_latest_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_fit_fresh_edge_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_fit_fresh_intensity_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_fit_fresh_pairwise_edge_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_fit_fresh_pairwise_intensity_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_like_fixed_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_like_fixed_gate_v8_probe_mtb120_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_like_fixed_gate_v8_smoke_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like displacement readout - R62 V7 short candidate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_like_v7_eval_20260706/final_summary/GMF_LIKE_V7_READOUT_20260706.md>)
- [原始報告：GMF-like method audit for thesis displacement data](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_like_v7_method_audit_20260706/GMF_LIKE_METHOD_AUDIT_20260706.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_pairwise_gate_v11_latest_motionclean_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_pairwise_gate_v11_motionclean_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/thesis_gmf_pairwise_gate_v8_probe_mtb120_20260706_full/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_edge_signal_v36_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_fusion_sweep_v20_v28_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_preprocess_sweep_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v20_v24_v26_v28_v31_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v34_lr5e8_mtb500_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v34_smoke_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v35_aggressive_e4_best_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v35_aggressive_mtb500_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v36_v20shape_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v37_measurement_view_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v38_wide_measurement_view_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v39_middle_measurement_guard_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v40_safe_measurement_guard_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/tools_gmf_template_v41_v20_safe_measurement_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v17e3_output_adapter_sweep_gmf_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v17e3_output_adapter_sweep_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v23_anchor_teacher_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v23_anchor_teacher_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v23_anchor_teacher_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v23_anchor_teacher_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v24_builtin_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v24_builtin_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v24_builtin_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v24_builtin_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_e3_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_e3_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_e3_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_e3_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25_safe_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_fixedroi_primarysafe_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v25mix_shapeaware_primarysafe_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v26_primarysafe_fixedroi_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v26_primarysafe_fixedroi_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)
- [原始報告：GMF-like thesis displacement gate](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v26_primarysafe_shapeaware_gmf_gate_20260706/GMF_LIKE_THESIS_GATE_REPORT.md>)
- [原始報告：GMF-like candidate score report](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/v26_primarysafe_shapeaware_gmf_scoring_20260706/GMF_LIKE_CANDIDATE_SCORE_REPORT.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次完成保存與完整檔案內容核對，沒有重跑本輪全部歷史訓練；原成功、失敗、中止及限制照原報告保留。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/LAB_SYSTEM.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。


---

[上一個閱讀入口：lab/R61_BoundaryGeneralizationUniversal](lab__R61_BoundaryGeneralizationUniversal.md) · [回本分區](../routes/lab.md) · [下一個閱讀入口：lab/Subpixel_Translation_Equivariance_20260720](lab__Subpixel_Translation_Equivariance_20260720.md)
