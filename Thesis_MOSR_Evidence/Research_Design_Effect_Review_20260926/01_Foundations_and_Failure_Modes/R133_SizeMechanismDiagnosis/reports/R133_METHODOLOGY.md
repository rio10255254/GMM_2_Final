# R133 固定設計

```json
{
  "utc": "2026-09-14T15:04:43.185107+00:00",
  "question": "Does frozenR129 enlarge known geometry, and which pipeline stage changes size?",
  "arms": [
    "Raw",
    "Optics",
    "Neural",
    "Final",
    "NoOptics",
    "ResidualHP",
    "DirectResidual",
    "MatchedHP",
    "MatchedDirect"
  ],
  "evaluations": {
    "existing_generated_test": "All128parents/256views, nativeimage/gradient error bycategory; no generic shape metric inferred from imageMAE",
    "physical_controls": "64 area-rendered disks with knownradius, zero-noise apartfrom8bitquantization;16/8render sensitivity subset",
    "real": "Three normalSEMfields all36objects eacharm, same16/16guard; primaryFinalreproduceR132"
  },
  "readout": "Same fine-boundary/circle method as realSEM; controls use known common coarse material mask to isolate readout. Report true-radius and clean-target-reader errors separately; not a deployable oracle.",
  "attribution": "Frozen co-adapted checkpoint interventions, not matched retrained architecture. RMSmatched original-output controls are input-only and postclip mismatch is reported.",
  "output_contract": "ResidualHP injects HP(neural-raw), DirectResidual uses neural-raw with samegain andglobalmean; both neutral whenneural=raw. Neither frozen change is automatically adopted.",
  "required": [
    "all128generatedparents",
    "all64controlledcases withtruth/Target/9arms",
    "normalSEM3x36x9",
    "identity/output/lossfixtures",
    "independent readout recomputation",
    "concrete next architecture/data/training plan"
  ],
  "no_training": true,
  "no_old_confirmation_access": true,
  "model_promotion": false
}
```

合成控制的已知遮罩只供共同量測初始化，不提供給模型；區分相對材料幾何與相對乾淨影像讀法的誤差。每種固定權重介入不是從頭訓練的替代架構。
