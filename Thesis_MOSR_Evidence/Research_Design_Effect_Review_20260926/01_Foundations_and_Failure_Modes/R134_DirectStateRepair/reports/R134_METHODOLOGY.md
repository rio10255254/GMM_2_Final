# R134 固定短測方法

```json
{
  "model_name": "R134_DirectStateRepair",
  "seeds": [
    1342001,
    1342002
  ],
  "arms": [
    "A",
    "C"
  ],
  "data_root": "D:\\GMM_2_Final\\Thesis_MOSR_Evidence\\LabSystem_MOSR\\Model_Packages\\R129_OpticalHybrid_Standalone_20260912\\training_data",
  "splits": {
    "train": 512,
    "dev": 128,
    "test": 128
  },
  "updates": 512,
  "order_seed": 1344001,
  "noise_seed": 1344002,
  "optimizer": {
    "peak_lr": 0.001,
    "minimum_lr": 1e-05,
    "warmup_updates": 32,
    "weight_decay": 1e-05,
    "gradient_clip": 5
  },
  "loss": {
    "image": 1.0,
    "gradient": 0.2,
    "pair": 0.2
  },
  "dev_steps": [
    0,
    128,
    256,
    512
  ],
  "checkpoint_every": 128,
  "initialization": "Fresh shared initialization withinseed; bothsingleoutputheads zero. No oldneuralweight loaded; this changeshistoricalconstructorinitbutnotarmscomparability.",
  "A": "Original R129 optical-conditioned initialimage/features and finalRaw+HP(neural) output.",
  "C": "Raw-initialized image state, opticalconditioned-minus-current image feature, Rawderivatives and directfinalimage; same7channels/sameweights/shapes/fourupdates/AA.",
  "factor": "Whole image-state/output contract, not a claim isolating one formula",
  "admission": {
    "B": "pending independent material-optical calibration",
    "D": "pending independent material-optical calibration",
    "A": "eligible existing isolated synthetic data",
    "C": "eligible existing isolated synthetic data"
  },
  "screens": {
    "type": "Prospective engineering screening for worthiness of long research training, NOT physical accuracy certification",
    "generated": "Bothseeds devMAE belowRaw; cleanidentity devMAE<=1gray",
    "sem": "Bothseeds C vsA: median paired size andcenteredshape deterioration<=2percent ofmatchedA; at least one ofthese medianpairedimprovement>=5percent. C notworse thanRaw by>2percent onbothsize andcenteredshape. All36valid.",
    "next": "Only a C that passesbothseeds proceeds to12source-fixedfull-fieldmotionpairs vsA andRaw; then fixeddev-selectedseed toall201 againstexistingRaw/R129 references before longtraining package.",
    "motion": "On12pairs C median nominal/within-grid/cross-axis metrics<=1.05 timesmatchedA orRaw(bestbaseline not required); no increase in invalidpairs orwrongdirections. These are provisional research tolerances.",
    "no_posthoc_relaxation": true
  },
  "packages": "Each admitted longtraininggeneration must haveitsownlocalcode/data/weights/calibration/evaluation/manifest/manualstart-pause-resume menu; no mixedgeneration folders.",
  "no_old_confirmation_access": true,
  "no_full_training_until_screened": true
}
```

篩選百分比是新一輪工程判斷，不是已認證物理容差；不能按結果放寬。資料與接口以外的共同條件固定。A/C不是完整A/B/C/D完成宣告。
