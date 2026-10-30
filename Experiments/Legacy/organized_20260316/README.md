# organized_20260316

這個目錄承載 2026-03-16 到 2026-03-18 的主實驗批次。

目前這個批次的關鍵脈絡是：

- `Round23`：pairmix abs-center fine-tune 診斷
- `Round24`：single-frame abs-center fine-tune 診斷
- `Round25`：scratch abs-center first external breakthrough
- `Round26`：step recovery，external 升級為 baseline
- `Round27`：internal frontier，external 主戰場未超越 `R26`
- `Round28`：`step_mag < 0.35` downsweep falsification
- `Round29`：`step_mag > 0.35` upper sweep falsification
- `Round30`：architecture breakthrough，external 正式升級 baseline
- `Round31`：B1 hyperparam tuning，external compare 已完成且未形成升級
- `tta_experiment`：`R26 + TTA C2` 驗證
- `analysis`：`D2 internal-external correlation`

附註：

- `round32/` 目錄仍保留在這個 batch 內作為歷史 payload / runtime bridge
- 但 `Round32` 的 canonical 治理面已轉到 `Experiments\R32Sandbox\`

## Recommended Reading Order

1. `..\..\..\PROJECT_STATE.md`
2. `..\..\..\PROJECT_STATE.md`
3. `round30\selected\reports\ROUND30_EXTERNAL_COMPARE.md`
4. `round31\selected\reports\ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
5. `tta_experiment\r26_tta_cross5\reports\TTA_VS_BASELINE_CROSS5_COMPARISON.md`
6. `analysis\INTERNAL_EXTERNAL_CORRELATION.md`

## Legacy Governance Entry Points

For safe legacy-round operations on `Round23`-`Round31`, also use:

1. `MANIFEST.md` — batch identity and scope boundaries
2. `..\..\..\docs\index\LEGACY_ROUNDS_OPERATIONS.md` — canonical operational guide
3. `round23\README.md` through `round31\README.md` — per-round start-here guides
4. `external_compare_*\README.md` — compare-chain guides

These files are additive governance surfaces. They do not replace the original reports.

## Round Roles

### round23
- 角色：pairmix abs-center fine-tune branch
- 結論：diagnostic round，沒有把 best checkpoint 往前推

### round24
- 角色：single-frame abs-center fine-tune branch
- 結論：diagnostic round，沒有把 best checkpoint 往前推

### round25
- 角色：從 scratch 導入 abs-center 的第一個 external breakthrough
- external compare：`external_compare_r18_r22_r25`

### round26
- 角色：step recovery 與 baseline promotion
- external compare：`external_compare_r18_r22_r25_r26`
- 歷史 baseline：`r26_sm035`

### round27
- 角色：latest internal frontier（在 `R26` 時代）
- external compare：`external_compare_r18_r22_r25_r26_r27`
- 結論：external 主戰場 `0.8px` 未超越 `R26`

### round28
- 角色：`step_mag < 0.35` downsweep falsification
- 正式名稱：`step_mag_balance` / `step_mag downsweep`
- external compare：`external_compare_r18_r22_r25_r26_r27_r28`
- 結論：不升級，`R26` 維持 baseline

### round29
- 角色：`step_mag > 0.35` upper sweep falsification
- external compare：`external_compare_r18_r22_r25_r26_r27_r28_r29`
- 結論：internal 通過，但 external 主戰場未擊敗 `R26`

### round30
- 角色：architecture breakthrough
- external compare：`round30\selected\reports\ROUND30_EXTERNAL_COMPARE.md`
- external final winner：`r30_b1_dironly`
- 結論：正式升級為 production baseline

### round31
- 角色：B1 hyperparam tuning on top of `r30_b1_dironly`
- 狀態：**external compare complete / no promotion**
- selected candidate：`r31_eq_prob_up`
- 關鍵事實：
  - 四個候選 internal 指標完全同值
  - measured candidates external 全部退步
  - `r31_eq_combo` 缺 `GMF_score.txt`，屬 artifact missing，不是 measured regression

## Analysis / Side Experiments

### tta_experiment
- 內容：`R26 + TTA C2 / r26_tta_cross5`
- 結論：`0.8px` 惡化，不是升級方向

### analysis
- 內容：`D2 internal-external correlation`
- 結論：`center_err` 是最佳 Tier2 screening 指標，但 external GMF 仍是 final gate

## External Compare Directory Map

- `external_compare_r18_r22_r25`
  - 驗證 `R25` 是否首次超越 `R18 / R22h`
- `external_compare_r18_r22_r25_r26`
  - 驗證 `R26` 是否能正式取代 `R25`
- `external_compare_r18_r22_r25_r26_r27`
  - 驗證 `R27` 是否能取代 `R26`
- `external_compare_r18_r22_r25_r26_r27_r28`
  - 驗證 `R28` downsweep 是否有效；結果為否定
- `external_compare_r18_r22_r25_r26_r27_r28_r29`
  - 驗證 `R29` upper sweep 是否有效；結果為否定
- `round30\selected\reports\ROUND30_EXTERNAL_COMPARE.md`
  - 驗證 `Round30` 三個 architecture candidates；結果為 `r30_b1_dironly` 升級

## Current Verdict

- current production baseline: `Round30 / r30_b1_dironly`
- latest completed legacy follow-up: `Round31 / r31_eq_prob_up`
- latest falsified production side-branch: `Round30 A1/A5/S1 side-directions`
- next governed surface: `Experiments\R32Sandbox\README.md`
