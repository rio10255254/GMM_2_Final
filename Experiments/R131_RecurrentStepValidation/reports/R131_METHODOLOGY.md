# R131 固定比較方法

{
  "created_utc": "2026-09-14T02:24:17.013668+00:00",
  "question": "Does the current frozen four-step R129 benefit from each recurrent step?",
  "design": "Frozen prefix n=0,1,2,3,4; identical checkpoint, optics, input-derived features, per-step scalars, final anchor and FOV guard. No retraining; not causal proof of separately trained architecture superiority.",
  "primary": [
    "SEM normal13-15 all36: radial, signed diameter, centered shape, MZC",
    "Same locked120LSC; all194within-session pairs and3repositioning separately",
    "Standalone0-4 runtime on same full image"
  ],
  "sources": "Previously used development scenes, never unseen holdout",
  "frames": 201,
  "sem_exposures": [
    13,
    14,
    15
  ],
  "steps": [
    0,
    1,
    2,
    3,
    4
  ],
  "zero_definition": "Skip learned updates; keep optical conditioning and final anchor. Raw is a separate reference.",
  "numerical_tolerance": 1e-06,
  "require_four_step_PNG_parity": true,
  "decision": "Report all endpoints, paired gains and tradeoffs. Fewer steps are supported for further testing only if primary geometry/motion do not worsen meaningfully; no posthoc composite score or automatic adoption. No application equivalence margin is invented.",
  "completion": "Preflight prefix equivalence, all204images*5prefixes,108SEMrows*5,1809LSCcenters*5,all populations, timing, independent saved-point refits and source integrity. Failures retained.",
  "checkpoint": {
    "path": "Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_OpticalHybrid_Standalone_20260912/results/training/r129_long_01/checkpoints/step08192.pth",
    "sha256": "086608339c6418b9dfd650f6809b1f7b45e65b6eb11452afe7df45c5b24ff1fd"
  }
}

相同權重依原順序停止；每個中間狀態經相同最終輸出規則，但最終輸出不回灌下一步。這檢驗現有模型的步數收益，不能證明從零訓練一至三步的能力上限。SEM非圓起伏與平均尺寸分開；固定120對與全部194對分開；不以名義平台步距宣稱絕對真值。既有Raw及四步結果必須重現。
