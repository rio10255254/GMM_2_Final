# R132 固定方法

```json
{
  "utc": "2026-09-14T13:38:34.705798+00:00",
  "question": "Is the fixed80px Raw retention necessary, overly broad, or masking underlying size bias?",
  "widths": [
    80,
    64,
    32,
    16,
    0
  ],
  "transition": 16,
  "zero_means": "No retention and no transition: exact pre-guard output",
  "checkpoint": {
    "path": "D:\\GMM_2_Final\\Thesis_MOSR_Evidence\\LabSystem_MOSR\\Model_Packages\\R129_OpticalHybrid_Standalone_20260912\\results\\training\\r129_long_01\\checkpoints\\step08192.pth",
    "sha256": "086608339c6418b9dfd650f6809b1f7b45e65b6eb11452afe7df45c5b24ff1fd"
  },
  "steps": 4,
  "training_updates": 0,
  "populations": {
    "normal_SEM": "exposures13/14/15, same36 pillars; outer20 and inner16 from source grid",
    "motion": "all201frames; locked120 and all194within-session;3repositionings retained",
    "crop_context": "same centralpillar16, left crop measurement-window margins0/16/32/64/96 for each of3 exposures; original fullfield reference retained"
  },
  "crop_limit": "Crop tests change actual FOV and therefore global optical/quality statistics too; they test operational context sensitivity, not only neural padding. No independent new physical sample.",
  "metrics": [
    "same fineSEM+signed size and centered shape",
    "same LSC+worst pairs and source-defined edge windows",
    "same-object cropped-vs-full appearance andSEM"
  ],
  "decision": "No composite score or invented application tolerance. Prefer complete object treatment; do not declare all pixel borders safe from pillars tens of pixels inside. Existing model unchanged until evidence interpreted. Report all tradeoffs.",
  "required": {
    "whole_SEM_rows": 540,
    "crop_SEM_rows": 75,
    "motion_centers": 9045,
    "frames_per_width": 201
  }
}
```

舊80像素版本必須逐像素重現；原模型不改。中央16與外圍20是來源位置分組，均不能替換36顆主結果。失敗保留；裁切測試若不足以支持最外側安全，必須明列。
